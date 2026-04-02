# -*- coding: utf-8 -*-
"""
TCM Knowledge Base with Neo4j Graph RAG
中医知识库 - 基于 Neo4j 图数据库的 RAG 检索系统

Features:
- Neo4j 图数据库存储（实体-关系）
- 向量语义检索（通过 Neo4j 的向量索引）
- 图遍历查询
- 路径推理
"""
import json
import re
import os
from typing import List, Dict, Any, Optional, Tuple, Set
from pydantic import BaseModel

from loguru import logger

# 导入 Neo4j 存储后端
try:
    from graphrag.graphrag_lite.neo4j_store import Neo4jStore
except ImportError:
    Neo4jStore = None


class TCMEntity(BaseModel):
    """中医实体模型"""
    id: str
    name: str
    type: str  # herb, syndrome, acupuncture, disease, organ, etc.
    aliases: List[str] = []
    description: str = ""
    properties: Dict[str, Any] = {}
    
    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()
    
    @classmethod
    def from_neo4j_dict(cls, data: Dict[str, Any]) -> "TCMEntity":
        """从 Neo4j 返回的字典创建实体"""
        properties = data.get("properties", {})
        return cls(
            id=data.get("name", ""),
            name=data.get("name", ""),
            type=data.get("type", ""),
            description=data.get("description", ""),
            properties={}  # Neo4j 中 properties 存储在 description 中
        )


class TCMRelation(BaseModel):
    """中医关系模型"""
    source: str
    target: str
    relation_type: str  # treats, causes, belongs_to, contraindicated_with, etc.
    weight: float = 1.0
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class TCMKnowledgeBase:
    """
    中医知识库 - 基于 Neo4j 图数据库
    
    Features:
    - Neo4j 图数据库存储和查询
    - 向量语义检索
    - 混合检索策略
    - 内置中医知识数据
    """
    
    # Neo4j 配置
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
    NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")
    
    def __init__(
        self,
        embedding_model: Any = None,
        vector_db: Any = None,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None
    ):
        """
        初始化知识库
        
        Args:
            embedding_model: 嵌入模型（用于向量检索）
            vector_db: 向量数据库
            uri: Neo4j URI
            user: Neo4j 用户名
            password: Neo4j 密码
            database: Neo4j 数据库名
        """
        self.embedding_model = embedding_model
        self.vector_db = vector_db
        self._neo4j_store: Optional[Neo4jStore] = None
        
        # Neo4j 连接配置
        self._neo4j_uri = uri or self.NEO4J_URI
        self._neo4j_user = user or self.NEO4J_USER
        self._neo4j_password = password or self.NEO4J_PASSWORD
        self._neo4j_database = database or self.NEO4J_DATABASE
        
        self._initialized = False
        self._connection_failed = False
    
    def _get_neo4j_store(self) -> Optional[Neo4jStore]:
        """获取 Neo4j 存储实例（延迟初始化）"""
        if self._connection_failed:
            return None
        
        if self._neo4j_store is None:
            try:
                if Neo4jStore is None:
                    logger.warning("Neo4jStore 未安装，请使用 mock 模式")
                    return None
                
                self._neo4j_store = Neo4jStore(
                    uri=self._neo4j_uri,
                    user=self._neo4j_user,
                    password=self._neo4j_password,
                    database=self._neo4j_database
                )
                # 测试连接
                stats = self._neo4j_store.get_stats()
                logger.info(f"[Neo4j] 连接成功，统计: {stats}")
            except Exception as e:
                logger.warning(f"[Neo4j] 连接失败: {e}，将使用 mock 模式")
                self._connection_failed = True
                self._neo4j_store = None
                return None
        
        return self._neo4j_store
    
    def close(self):
        """关闭 Neo4j 连接"""
        if self._neo4j_store:
            self._neo4j_store.close()
            self._neo4j_store = None
    
    def initialize(self) -> None:
        """初始化知识库"""
        if self._initialized:
            return
        
        # 尝试连接 Neo4j
        neo4j_store = self._get_neo4j_store()
        
        if neo4j_store is not None:
            # 检查是否已有数据
            stats = neo4j_store.get_stats()
            if stats["entities"] == 0:
                logger.info("[Neo4j] 数据库为空，开始加载默认知识...")
                self._load_default_knowledge_to_neo4j()
            else:
                logger.info(f"[Neo4j] 数据库已有 {stats['entities']} 个实体")
        else:
            # 使用 mock 模式
            logger.info("[Mock] 使用内存模式存储知识")
            self._mock_mode = True
            self._mock_entities: Dict[str, Dict] = {}
            self._mock_relations: List[Dict] = []
            self._load_default_knowledge_mock()
        
        self._initialized = True
    
    # ==================== Neo4j 存储操作 ====================
    
    def _upsert_entity_neo4j(self, entity: TCMEntity) -> None:
        """向 Neo4j 插入或更新实体"""
        store = self._get_neo4j_store()
        if store is None:
            return
        
        description = entity.description
        if entity.properties:
            description = json.dumps({
                "description": entity.description,
                "properties": entity.properties,
                "aliases": entity.aliases
            }, ensure_ascii=False)
        
        store.upsert_entity(
            name=entity.name,
            entity_type=entity.type,
            description=description,
            embedding=None
        )
    
    def _upsert_relation_neo4j(self, relation: TCMRelation) -> None:
        """向 Neo4j 插入或更新关系"""
        store = self._get_neo4j_store()
        if store is None:
            return
        
        store.upsert_relation(
            src=relation.source,
            tgt=relation.target,
            keywords=relation.relation_type,
            description=relation.description,
            embedding=None
        )
    
    def _get_entity_neo4j(self, name: str) -> Optional[Dict]:
        """从 Neo4j 获取实体"""
        store = self._get_neo4j_store()
        if store is None:
            return None
        
        return store.get_entity(name)
    
    def _get_relations_by_entity_neo4j(self, name: str) -> List[Dict]:
        """从 Neo4j 获取实体的关联关系"""
        store = self._get_neo4j_store()
        if store is None:
            return []
        
        return store.get_relations_by_entity(name)
    
    def _list_entities_neo4j(self, entity_type: Optional[str] = None) -> List[Dict]:
        """从 Neo4j 列出实体"""
        store = self._get_neo4j_store()
        if store is None:
            return []
        
        entities = store.list_entities()
        if entity_type:
            entities = [e for e in entities if e.get("type") == entity_type]
        return entities
    
    # ==================== Mock 模式存储操作 ====================
    
    def _load_default_knowledge_mock(self) -> None:
        """加载默认知识到 mock 模式"""
        for entity_data in self._build_default_tcm_graph():
            self._mock_entities[entity_data["name"]] = entity_data
        
        for relation in self._get_default_relations():
            self._mock_relations.append(relation)
    
    def _find_mock_entity(self, name: str) -> Optional[Dict]:
        """在 mock 模式中查找实体"""
        # 直接匹配
        if name in self._mock_entities:
            return self._mock_entities[name]
        
        # 别名匹配
        for entity in self._mock_entities.values():
            if name in entity.get("aliases", []):
                return entity
        
        # 部分匹配
        for entity in self._mock_entities.values():
            if name in entity.get("name", ""):
                return entity
        
        return None
    
    # ==================== 知识加载 ====================
    
    def _load_default_knowledge_to_neo4j(self) -> None:
        """加载默认中医知识到 Neo4j"""
        # 加载实体
        for entity_data in self._build_default_tcm_graph():
            entity = TCMEntity(**entity_data)
            self._upsert_entity_neo4j(entity)
        
        # 加载关系
        for relation_data in self._get_default_relations():
            relation = TCMRelation(**relation_data)
            self._upsert_relation_neo4j(relation)
        
        logger.info("[Neo4j] 默认知识加载完成")
    
    def _build_default_tcm_graph(self) -> List[Dict[str, Any]]:
        """构建默认中医知识图谱"""
        return [
            {
                "id": "yin_deficiency",
                "name": "阴虚",
                "type": "syndrome",
                "aliases": ["阴虚证", "阴虚体质"],
                "description": "阴液不足，不能制阳，以五心烦热、潮热盗汗、舌红少津、脉细数等为常见症的证候",
                "properties": {
                    "category": "虚证",
                    "related_organs": ["肾", "肺", "肝"],
                    "common_symptoms": ["五心烦热", "盗汗", "口干", "舌红少苔", "脉细数"]
                }
            },
            {
                "id": "yang_deficiency",
                "name": "阳虚",
                "type": "syndrome",
                "aliases": ["阳虚证", "阳虚体质", "肾阳虚", "脾阳虚"],
                "description": "阳气不足，不能制阴，以畏寒肢冷、面色苍白、舌淡苔白、脉沉迟等为常见症的证候",
                "properties": {
                    "category": "虚证",
                    "related_organs": ["肾", "脾"],
                    "common_symptoms": ["畏寒肢冷", "面色苍白", "夜尿多", "舌淡苔白", "脉沉迟"]
                }
            },
            {
                "id": "qi_deficiency",
                "name": "气虚",
                "type": "syndrome",
                "aliases": ["气虚证", "气虚体质", "脾气虚", "肺气虚", "肾气虚"],
                "description": "元气不足，以神疲乏力、少气懒言、舌淡、脉虚等为常见症的证候",
                "properties": {
                    "category": "虚证",
                    "related_organs": ["脾", "肺", "肾"],
                    "common_symptoms": ["神疲乏力", "少气懒言", "自汗", "舌淡", "脉虚"]
                }
            },
            {
                "id": "blood_deficiency",
                "name": "血虚",
                "type": "syndrome",
                "aliases": ["血虚证", "血虚体质", "肝血虚", "心血虚"],
                "description": "血液亏虚，以面色萎黄、头晕眼花、心悸失眠、舌淡脉细等为常见症的证候",
                "properties": {
                    "category": "虚证",
                    "related_organs": ["肝", "心"],
                    "common_symptoms": ["面色萎黄", "头晕眼花", "心悸失眠", "舌淡", "脉细"]
                }
            },
            {
                "id": "phlegm_damp",
                "name": "痰湿",
                "type": "syndrome",
                "aliases": ["痰湿证", "痰湿体质", "湿痰", "脾虚痰湿"],
                "description": "痰湿内蕴，以形体肥胖、苔腻、脉滑等为常见症的证候",
                "properties": {
                    "category": "实证",
                    "related_organs": ["脾", "肺"],
                    "common_symptoms": ["形体肥胖", "胸闷", "痰多", "苔白腻", "脉滑"]
                }
            },
            {
                "id": "qi_stagnation",
                "name": "气郁",
                "type": "syndrome",
                "aliases": ["气郁证", "气郁体质", "肝气郁结", "气滞"],
                "description": "气机郁滞，以情志抑郁、胸胁胀痛、脉弦等为常见症的证候",
                "properties": {
                    "category": "实证",
                    "related_organs": ["肝", "脾"],
                    "common_symptoms": ["情志抑郁", "胸胁胀痛", "善太息", "脉弦"]
                }
            },
            {
                "id": "blood_stasis",
                "name": "血瘀",
                "type": "syndrome",
                "aliases": ["血瘀证", "血瘀体质", "瘀血", "瘀血证"],
                "description": "瘀血内阻，以疼痛、肿块、出血、舌紫、脉涩等为常见症的证候",
                "properties": {
                    "category": "实证",
                    "related_organs": ["肝", "心"],
                    "common_symptoms": ["疼痛固定", "肿块", "舌紫暗", "脉涩", "面色黧黑"]
                }
            },
            {
                "id": "heart_fire",
                "name": "心火亢盛",
                "type": "syndrome",
                "aliases": ["心火", "心火旺", "心经热盛"],
                "description": "心火内炽，以心烦失眠、舌疮、尿赤、脉数等为常见症的证候",
                "properties": {
                    "category": "热证",
                    "related_organs": ["心"],
                    "common_symptoms": ["心烦失眠", "舌疮", "口舌生疮", "尿赤", "脉数"]
                }
            },
            {
                "id": "liver_fire",
                "name": "肝火上炎",
                "type": "syndrome",
                "aliases": ["肝火", "肝火旺", "肝经火盛"],
                "description": "肝火炽盛，以头晕胀痛、面红目赤、口苦、尿黄、脉弦数等为常见症的证候",
                "properties": {
                    "category": "热证",
                    "related_organs": ["肝"],
                    "common_symptoms": ["头晕胀痛", "面红目赤", "口苦", "尿黄", "脉弦数", "急躁易怒"]
                }
            },
            {
                "id": "kidney_yin_deficiency",
                "name": "肾阴虚",
                "type": "syndrome",
                "aliases": ["肾阴不足", "肾阴亏虚"],
                "description": "肾阴亏损，以腰膝酸软、眩晕耳鸣、失眠多梦、舌红少苔、脉细数等为常见症的证候",
                "properties": {
                    "category": "虚证",
                    "related_organs": ["肾"],
                    "common_symptoms": ["腰膝酸软", "眩晕耳鸣", "失眠多梦", "遗精", "舌红少苔", "脉细数"]
                }
            },
            {
                "id": "kidney_yang_deficiency",
                "name": "肾阳虚",
                "type": "syndrome",
                "aliases": ["肾阳不足", "命门火衰"],
                "description": "肾阳虚衰，以腰膝酸冷、畏寒肢冷、性欲减退、夜尿多、舌淡苔白、脉沉弱等为常见症的证候",
                "properties": {
                    "category": "虚证",
                    "related_organs": ["肾"],
                    "common_symptoms": ["腰膝酸冷", "畏寒肢冷", "性欲减退", "夜尿多", "舌淡苔白", "脉沉弱"]
                }
            },
            {
                "id": "ginseng",
                "name": "人参",
                "type": "herb",
                "aliases": ["野山参", "园参", "红参", "生晒参"],
                "description": "大补元气，补脾益肺，生津养血，安神益智",
                "properties": {
                    "taste": ["甘", "微苦", "微温"],
                    "channel_entering": ["脾", "肺", "心", "肾"],
                    "functions": ["大补元气", "补脾益肺", "生津养血", "安神益智"],
                    "dosage": "3-9g",
                    "contraindications": ["实证、热证", "阴虚火旺"]
                }
            },
            {
                "id": "ginseng_zy",
                "name": "党参",
                "type": "herb",
                "aliases": ["潞党参", "台党参"],
                "description": "补中益气，健脾益肺，养血生津",
                "properties": {
                    "taste": ["甘", "平"],
                    "channel_entering": ["脾", "肺"],
                    "functions": ["补中益气", "健脾益肺", "养血生津"],
                    "dosage": "9-30g",
                    "contraindications": ["气滞", "热证"]
                }
            },
            {
                "id": "astragalus",
                "name": "黄芪",
                "type": "herb",
                "aliases": ["绵黄芪", "北芪"],
                "description": "补气升阳，固表止汗，利水消肿，生津养血，行滞通痹，托毒排脓，敛疮生肌",
                "properties": {
                    "taste": ["甘", "微温"],
                    "channel_entering": ["脾", "肺"],
                    "functions": ["补气升阳", "固表止汗", "利水消肿", "生津养血"],
                    "dosage": "9-30g",
                    "contraindications": ["表实邪盛", "阴虚阳亢"]
                }
            },
            {
                "id": "licorice",
                "name": "甘草",
                "type": "herb",
                "aliases": ["粉甘草", "炙甘草", "生甘草"],
                "description": "补脾益气，清热解毒，祛痰止咳，缓急止痛，调和诸药",
                "properties": {
                    "taste": ["甘", "平"],
                    "channel_entering": ["心", "肺", "脾", "胃"],
                    "functions": ["补脾益气", "清热解毒", "祛痰止咳", "缓急止痛", "调和诸药"],
                    "dosage": "2-10g",
                    "contraindications": ["湿盛胀满", "水肿"]
                }
            },
            {
                "id": "rehmannia",
                "name": "熟地黄",
                "type": "herb",
                "aliases": ["熟地"],
                "description": "补血滋阴，益精填髓",
                "properties": {
                    "taste": ["甘", "微温"],
                    "channel_entering": ["肝", "肾"],
                    "functions": ["补血滋阴", "益精填髓"],
                    "dosage": "9-15g",
                    "contraindications": ["脾胃虚弱", "气滞痰多"]
                }
            },
            {
                "id": "poria",
                "name": "茯苓",
                "type": "herb",
                "aliases": ["云苓", "白茯苓", "赤茯苓"],
                "description": "利水渗湿，健脾宁心",
                "properties": {
                    "taste": ["甘", "淡", "平"],
                    "channel_entering": ["心", "肺", "脾", "肾"],
                    "functions": ["利水渗湿", "健脾宁心"],
                    "dosage": "10-30g",
                    "contraindications": ["阴虚津伤"]
                }
            },
            {
                "id": "four_gentleman_decoction",
                "name": "四君子汤",
                "type": "prescription",
                "aliases": ["四君子"],
                "description": "益气健脾，主治脾胃气虚证",
                "properties": {
                    "composition": ["人参", "白术", "茯苓", "甘草"],
                    "indication": "脾胃气虚证：面色萎白，语气低微，食少便溏",
                    "usage": "水煎服",
                    "modifications": {
                        "气虚甚": "加黄芪",
                        "兼痰湿": "加半夏、陈皮"
                    }
                }
            },
            {
                "id": "four_suben_decoction",
                "name": "四物汤",
                "type": "prescription",
                "aliases": ["四物"],
                "description": "补血调血，主治营血虚滞证",
                "properties": {
                    "composition": ["熟地黄", "当归", "川芎", "白芍"],
                    "indication": "营血虚滞证：头晕心悸，面色无华，舌淡，脉细",
                    "usage": "水煎服"
                }
            },
            {
                "id": "liuwei_dehuang_decoction",
                "name": "六味地黄丸",
                "type": "prescription",
                "aliases": ["六味地黄", "地黄丸"],
                "description": "滋阴补肾，主治肾阴虚证",
                "properties": {
                    "composition": ["熟地黄", "山茱萸", "山药", "泽泻", "茯苓", "丹皮"],
                    "indication": "肾阴虚证：腰膝酸软，头晕耳鸣，遗精盗汗，舌红少苔，脉细数",
                    "usage": "水煎服或制丸剂"
                }
            },
            {
                "id": "xiaoyao_decoction",
                "name": "逍遥散",
                "type": "prescription",
                "aliases": ["逍遥丸"],
                "description": "疏肝解郁，养血健脾，主治肝郁血虚脾弱证",
                "properties": {
                    "composition": ["柴胡", "白芍", "当归", "茯苓", "白术", "甘草", "薄荷", "生姜"],
                    "indication": "肝郁血虚脾弱证：两胁作痛，头痛目眩，口燥咽干，神疲食少",
                    "usage": "水煎服"
                }
            },
            {
                "id": "zusanli",
                "name": "足三里",
                "type": "acupoint",
                "aliases": ["下陵", "三里"],
                "description": "足阳明胃经穴，主治胃痛、消化不良、虚劳诸证",
                "properties": {
                    "location": "小腿外侧，犊鼻下3寸，犊鼻与解溪连线上",
                    "channel": "足阳明胃经",
                    "indications": ["胃痛", "消化不良", "虚劳", "失眠", "高血压"]
                }
            },
            {
                "id": "insomnia",
                "name": "失眠",
                "type": "disease",
                "aliases": ["不寐", "不得卧", "目不瞑"],
                "description": "常见病症，表现为入睡困难、睡眠浅或早醒",
                "properties": {
                    "common_types": ["心肾不交", "心脾两虚", "肝郁化火", "痰热内扰", "心胆气虚"],
                    "related_organs": ["心", "肝", "脾", "肾"]
                }
            },
            {
                "id": "fatigue",
                "name": "疲劳",
                "type": "symptom",
                "aliases": ["乏力", "疲倦", "倦怠", "神疲"],
                "description": "常见症状，表现为精神不振、身体乏力",
                "properties": {
                    "common_types": ["气虚疲劳", "血虚疲劳", "阴虚疲劳", "阳虚疲劳", "湿困疲劳"],
                    "related_organs": ["脾", "肾", "心"]
                }
            },
            {
                "id": "poor_appetite",
                "name": "食欲不振",
                "type": "symptom",
                "aliases": ["纳呆", "不思饮食", "食少"],
                "description": "常见症状，表现为不想吃饭或进食量减少",
                "properties": {
                    "common_types": ["脾胃气虚", "脾胃湿热", "肝气犯胃", "食积"],
                    "related_organs": ["脾", "胃", "肝"]
                }
            },
            {
                "id": "headache",
                "name": "头痛",
                "type": "disease",
                "aliases": ["头疼", "头风"],
                "description": "常见症状，可由多种原因引起",
                "properties": {
                    "common_types": ["风寒头痛", "风热头痛", "风湿头痛", "肝阳头痛", "血虚头痛", "痰浊头痛", "肾虚头痛"],
                    "related_channels": ["肝经", "胆经", "膀胱经"]
                }
            },
            {
                "id": "spleen_qi_sinking",
                "name": "脾气下陷",
                "type": "syndrome",
                "aliases": ["中气下陷", "脾虚下陷", "气虚下陷"],
                "description": "脾气虚弱，升举无力，以脘腹坠胀、久泻脱肛、脉弱等为常见症的证候",
                "properties": {
                    "category": "虚证",
                    "related_organs": ["脾"],
                    "common_symptoms": ["脘腹坠胀", "久泻脱肛", "头晕", "脉弱"]
                }
            },
            {
                "id": "lung_qi_deficiency",
                "name": "肺气虚",
                "type": "syndrome",
                "aliases": ["肺气不足", "肺虚"],
                "description": "肺气虚弱，以咳喘无力、少气懒言、声音低怯、自汗易感等为常见症的证候",
                "properties": {
                    "category": "虚证",
                    "related_organs": ["肺"],
                    "common_symptoms": ["咳喘无力", "少气懒言", "声音低怯", "自汗", "易感"]
                }
            },
        ]
    
    def _get_default_relations(self) -> List[Dict[str, Any]]:
        """获取默认关系"""
        return [
            {"source": "阴虚", "target": "肾阴虚", "relation_type": "includes", "weight": 1.0},
            {"source": "阳虚", "target": "肾阳虚", "relation_type": "includes", "weight": 1.0},
            {"source": "阴虚", "target": "心火亢盛", "relation_type": "may_cause", "weight": 0.6},
            {"source": "气郁", "target": "肝火上炎", "relation_type": "may_cause", "weight": 0.7},
            {"source": "气虚", "target": "脾气下陷", "relation_type": "may_cause", "weight": 0.8},
            {"source": "气虚", "target": "肺气虚", "relation_type": "may_cause", "weight": 0.8},
            {"source": "脾气下陷", "target": "四君子汤", "relation_type": "treated_by", "weight": 1.0},
            {"source": "气虚", "target": "四君子汤", "relation_type": "treated_by", "weight": 1.0},
            {"source": "血虚", "target": "四物汤", "relation_type": "treated_by", "weight": 1.0},
            {"source": "气虚", "target": "血虚", "relation_type": "may_cause", "weight": 0.5},
            {"source": "肾阴虚", "target": "六味地黄丸", "relation_type": "treated_by", "weight": 1.0},
            {"source": "气郁", "target": "逍遥散", "relation_type": "treated_by", "weight": 1.0},
            {"source": "血虚", "target": "逍遥散", "relation_type": "treated_by", "weight": 0.7},
            {"source": "人参", "target": "四君子汤", "relation_type": "component_of", "weight": 1.0},
            {"source": "气虚", "target": "人参", "relation_type": "treated_by", "weight": 1.0},
            {"source": "气虚", "target": "黄芪", "relation_type": "treated_by", "weight": 1.0},
            {"source": "气虚", "target": "党参", "relation_type": "treated_by", "weight": 1.0},
            {"source": "气虚", "target": "足三里", "relation_type": "treated_by_acupoint", "weight": 1.0},
            {"source": "食欲不振", "target": "足三里", "relation_type": "treated_by_acupoint", "weight": 1.0},
            {"source": "失眠", "target": "心火亢盛", "relation_type": "related_to", "weight": 0.8},
            {"source": "失眠", "target": "肾阴虚", "relation_type": "related_to", "weight": 0.8},
            {"source": "疲劳", "target": "气虚", "relation_type": "related_to", "weight": 0.9},
            {"source": "疲劳", "target": "血虚", "relation_type": "related_to", "weight": 0.8},
            {"source": "食欲不振", "target": "气虚", "relation_type": "related_to", "weight": 0.9},
            {"source": "头痛", "target": "肝火上炎", "relation_type": "may_cause", "weight": 0.7},
            {"source": "头痛", "target": "血虚", "relation_type": "may_cause", "weight": 0.6},
        ]
    
    # ==================== 查询接口 ====================
    
    def query_by_symptoms(
        self,
        symptoms: List[str],
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        根据症状查询可能的证型和治疗方案
        
        Args:
            symptoms: 症状列表
            max_results: 最大返回结果数
            
        Returns:
            相关证型和治疗方案列表
        """
        results = []
        
        for symptom in symptoms:
            # 查找症状实体
            symptom_entity = self._find_entity(symptom)
            if not symptom_entity:
                continue
            
            # 查找相关实体
            related = self._get_related_entities(
                symptom_entity["name"],
                relation_types=["may_cause", "related_to", "treated_by"]
            )
            
            for rel_entity, rel_type, weight in related:
                if rel_entity.get("type") == "syndrome":
                    syndrome_info = self._get_syndrome_info(rel_entity)
                    treatment = self._find_treatment_for_syndrome(rel_entity["name"])
                    
                    results.append({
                        "symptom": symptom,
                        "syndrome": syndrome_info,
                        "treatment": treatment,
                        "confidence": weight,
                        "source": "knowledge_graph"
                    })
        
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:max_results]
    
    def _find_entity(self, name: str) -> Optional[Dict]:
        """查找实体"""
        # 尝试 Neo4j
        entity = self._get_entity_neo4j(name)
        if entity:
            return entity
        
        # 尝试 Mock 模式
        if hasattr(self, "_mock_mode") and self._mock_mode:
            return self._find_mock_entity(name)
        
        return None
    
    def _get_related_entities(
        self,
        name: str,
        relation_types: Optional[List[str]] = None,
        depth: int = 1
    ) -> List[Tuple[Dict, str, float]]:
        """获取相关实体"""
        results = []
        
        # 从 Neo4j 获取
        relations = self._get_relations_by_entity_neo4j(name)
        
        for rel in relations:
            src = rel.get("src", "")
            tgt = rel.get("tgt", "")
            rel_type = rel.get("keywords", "")
            
            # 确定要获取的实体名称
            related_name = tgt if src == name else src
            
            # 过滤关系类型
            if relation_types and rel_type not in relation_types:
                continue
            
            # 获取实体
            related_entity = self._get_entity_neo4j(related_name)
            if related_entity:
                results.append((related_entity, rel_type, rel.get("weight", 1.0)))
        
        # 从 Mock 获取
        if hasattr(self, "_mock_mode") and self._mock_mode:
            for rel in self._mock_relations:
                src = rel.get("source", "")
                tgt = rel.get("target", "")
                rel_type = rel.get("relation_type", "")
                
                if src == name or tgt == name:
                    if relation_types and rel_type not in relation_types:
                        continue
                    
                    related_name = tgt if src == name else src
                    related_entity = self._find_mock_entity(related_name)
                    
                    if related_entity:
                        results.append((related_entity, rel_type, rel.get("weight", 1.0)))
        
        return results
    
    def _get_syndrome_info(self, syndrome_entity: Dict) -> Dict[str, Any]:
        """获取证型详细信息"""
        related = self._get_related_entities(syndrome_entity.get("name", ""), depth=1)
        
        related_herbs = []
        related_prescriptions = []
        related_acupoints = []
        
        for entity, rel_type, weight in related:
            entity_type = entity.get("type", "")
            
            if entity_type == "herb":
                related_herbs.append({
                    "name": entity.get("name", ""),
                    "description": entity.get("description", ""),
                    "relation": rel_type
                })
            elif entity_type == "prescription":
                # 尝试解析 properties
                props = {}
                try:
                    if "properties" in entity:
                        if isinstance(entity["properties"], str):
                            props = json.loads(entity["properties"])
                        else:
                            props = entity.get("properties", {})
                except:
                    pass
                
                related_prescriptions.append({
                    "name": entity.get("name", ""),
                    "description": entity.get("description", ""),
                    "composition": props.get("composition", []),
                    "indication": props.get("indication", ""),
                    "relation": rel_type
                })
            elif entity_type == "acupoint":
                related_acupoints.append({
                    "name": entity.get("name", ""),
                    "description": entity.get("description", ""),
                    "relation": rel_type
                })
        
        # 解析 properties
        props = {}
        try:
            if "properties" in syndrome_entity:
                if isinstance(syndrome_entity["properties"], str):
                    props = json.loads(syndrome_entity["properties"])
                else:
                    props = syndrome_entity.get("properties", {})
        except:
            pass
        
        return {
            "name": syndrome_entity.get("name", ""),
            "description": syndrome_entity.get("description", ""),
            "category": props.get("category", ""),
            "related_organs": props.get("related_organs", []),
            "common_symptoms": props.get("common_symptoms", []),
            "related_herbs": related_herbs,
            "related_prescriptions": related_prescriptions,
            "related_acupoints": related_acupoints
        }
    
    def _find_treatment_for_syndrome(self, syndrome_name: str) -> Optional[Dict[str, Any]]:
        """查找证型的治疗方案"""
        related = self._get_related_entities(
            syndrome_name,
            relation_types=["treated_by", "treated_by_acupoint", "treated_by"]
        )
        
        treatment = {
            "herbal_prescriptions": [],
            "acupoints": []
        }
        
        for entity, rel_type, weight in related:
            entity_type = entity.get("type", "")
            
            if entity_type == "prescription":
                props = {}
                try:
                    if "properties" in entity:
                        if isinstance(entity["properties"], str):
                            props = json.loads(entity["properties"])
                        else:
                            props = entity.get("properties", {})
                except:
                    pass
                
                treatment["herbal_prescriptions"].append({
                    "name": entity.get("name", ""),
                    "composition": props.get("composition", []),
                    "indication": props.get("indication", ""),
                    "modifications": props.get("modifications", {})
                })
            elif entity_type == "acupoint":
                props = {}
                try:
                    if "properties" in entity:
                        if isinstance(entity["properties"], str):
                            props = json.loads(entity["properties"])
                        else:
                            props = entity.get("properties", {})
                except:
                    pass
                
                treatment["acupoints"].append({
                    "name": entity.get("name", ""),
                    "location": props.get("location", ""),
                    "indications": props.get("indications", [])
                })
        
        return treatment if treatment["herbal_prescriptions"] or treatment["acupoints"] else None
    
    def query_by_entity_name(
        self,
        name: str,
        include_related: bool = True
    ) -> Dict[str, Any]:
        """
        根据名称查询实体及其相关信息
        
        Args:
            name: 实体名称
            include_related: 是否包含关联实体
            
        Returns:
            实体详情和关联信息
        """
        entity = self._find_entity(name)
        if not entity:
            return {"error": f"未找到实体: {name}"}
        
        result = {
            "entity": entity,
            "type": entity.get("type", "")
        }
        
        if include_related:
            related = self._get_related_entities(entity.get("name", ""), depth=1)
            result["related"] = [
                {
                    "entity": r[0],
                    "relation": r[1],
                    "weight": r[2]
                }
                for r in related
            ]
        
        return result
    
    def search_similar(
        self,
        query: str,
        entity_types: Optional[List[str]] = None,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        语义搜索相似的实体
        
        Args:
            query: 查询文本
            entity_types: 限定实体类型
            max_results: 最大结果数
            
        Returns:
            相似实体列表
        """
        keywords = self._extract_keywords(query)
        results = []
        
        # 从 Neo4j 获取所有实体
        all_entities = self._list_entities_neo4j()
        
        # 从 Mock 获取实体
        if hasattr(self, "_mock_mode") and self._mock_mode:
            for entity in self._mock_entities.values():
                if entity not in all_entities:
                    all_entities.append(entity)
        
        for entity in all_entities:
            entity_type = entity.get("type", "")
            
            if entity_types and entity_type not in entity_types:
                continue
            
            score = 0.0
            entity_name = entity.get("name", "")
            
            # 名称匹配
            if query.lower() in entity_name.lower():
                score += 0.5
            
            # 别名匹配
            aliases = []
            try:
                if "aliases" in entity:
                    if isinstance(entity["aliases"], str):
                        aliases = json.loads(entity["aliases"])
                    else:
                        aliases = entity.get("aliases", [])
            except:
                pass
            
            for alias in aliases:
                if query.lower() in alias.lower():
                    score += 0.3
                    break
            
            # 关键词匹配
            if keywords:
                description = entity.get("description", "")
                
                # 尝试解析 properties
                props = {}
                try:
                    if "properties" in entity:
                        if isinstance(entity["properties"], str):
                            props = json.loads(entity["properties"])
                        else:
                            props = entity.get("properties", {})
                except:
                    pass
                
                for keyword in keywords:
                    if keyword in description:
                        score += 0.2
                    
                    # 匹配 common_symptoms
                    for symptom in props.get("common_symptoms", []):
                        if keyword in symptom:
                            score += 0.3
            
            if score > 0:
                results.append({
                    "entity": entity,
                    "score": min(score, 1.0),
                    "content": entity.get("description", "")
                })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]
    
    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        stop_words = {"的", "了", "是", "在", "有", "和", "与", "或", "等", "症状"}
        words = re.findall(r'[\u4e00-\u9fa5]+', text)
        return [w for w in words if w not in stop_words and len(w) > 1]
    
    def get_treatment_recommendations(
        self,
        syndrome_name: str,
        patient_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        获取治疗建议
        
        Args:
            syndrome_name: 证型名称
            patient_info: 患者信息（年龄、性别、体质等）
            
        Returns:
            个性化治疗建议
        """
        entity = self._find_entity(syndrome_name)
        if not entity or entity.get("type") != "syndrome":
            return {"error": f"未找到证型: {syndrome_name}"}
        
        syndrome_info = self._get_syndrome_info(entity)
        treatment = self._find_treatment_for_syndrome(entity.get("name", ""))
        
        recommendations = {
            "syndrome_analysis": syndrome_info,
            "treatment_plan": treatment,
            "lifestyle_advice": self._generate_lifestyle_advice(entity, patient_info),
            "diet_advice": self._generate_diet_advice(entity),
            "precautions": self._generate_precautions(entity)
        }
        
        return recommendations
    
    def _generate_lifestyle_advice(
        self,
        syndrome: Dict,
        patient_info: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """生成生活建议"""
        advice_list = []
        
        # 解析 properties
        props = {}
        try:
            if "properties" in syndrome:
                if isinstance(syndrome["properties"], str):
                    props = json.loads(syndrome["properties"])
                else:
                    props = syndrome.get("properties", {})
        except:
            pass
        
        category = props.get("category", "")
        name = syndrome.get("name", "")
        
        if "虚" in category:
            advice_list.extend([
                "注意休息，避免过度劳累",
                "适当进行轻度运动，如散步、太极拳",
                "保持充足睡眠"
            ])
        
        if "热" in name or "火" in name:
            advice_list.extend([
                "保持情绪稳定，避免急躁易怒",
                "避免辛辣刺激性食物",
                "多饮水，保持大便通畅"
            ])
        
        if "郁" in name or "气滞" in name:
            advice_list.extend([
                "保持心情舒畅，适当进行放松训练",
                "多参加户外活动",
                "避免长时间处于压抑情绪中"
            ])
        
        return advice_list
    
    def _generate_diet_advice(self, syndrome: Dict) -> List[str]:
        """生成饮食建议"""
        advice_list = []
        
        name = syndrome.get("name", "")
        
        if "阴虚" in name:
            advice_list.extend([
                "宜食用滋阴润燥的食物，如银耳、百合、梨等",
                "少吃辛辣刺激性食物",
                "避免油炸、烧烤类食物"
            ])
        elif "阳虚" in name:
            advice_list.extend([
                "宜食用温补食物，如羊肉、核桃、桂圆等",
                "少吃生冷寒凉食物",
                "可适当食用姜、葱、蒜等温性调料"
            ])
        elif "气虚" in name:
            advice_list.extend([
                "宜食用补气食物，如山药、黄芪、红枣等",
                "少吃耗气食物，如萝卜、莱菔子等",
                "避免过度思虑"
            ])
        elif "痰湿" in name or "湿" in name:
            advice_list.extend([
                "宜食用清淡易消化的食物",
                "少吃甜腻、油腻、生冷食物",
                "可适当食用薏苡仁、冬瓜、赤小豆等利湿食物"
            ])
        
        return advice_list
    
    def _generate_precautions(self, syndrome: Dict) -> List[str]:
        """生成注意事项"""
        precautions = []
        
        props = {}
        try:
            if "properties" in syndrome:
                if isinstance(syndrome["properties"], str):
                    props = json.loads(syndrome["properties"])
                else:
                    props = syndrome.get("properties", {})
        except:
            pass
        
        category = props.get("category", "")
        name = syndrome.get("name", "")
        
        if "虚" in category:
            precautions.append("避免过度劳累和剧烈运动")
        
        if "热" in name or "火" in name:
            precautions.append("避免情绪激动和高温环境")
        
        precautions.extend([
            "遵医嘱服药，不可擅自停药或换药",
            "如症状加重或出现新症状，请及时就医"
        ])
        
        return precautions
    
    # ==================== CRUD 操作接口 ====================
    
    def add_entity(self, entity: TCMEntity) -> None:
        """添加实体到知识库"""
        self._upsert_entity_neo4j(entity)
        
        if hasattr(self, "_mock_mode") and self._mock_mode:
            self._mock_entities[entity.name] = entity.to_dict()
    
    def add_relation(self, relation: TCMRelation) -> None:
        """添加关系到知识库"""
        self._upsert_relation_neo4j(relation)
        
        if hasattr(self, "_mock_mode") and self._mock_mode:
            self._mock_relations.append(relation.to_dict())
    
    def delete_entity(self, name: str) -> bool:
        """删除实体"""
        store = self._get_neo4j_store()
        if store:
            result = store.delete_entity(name)
            if result and hasattr(self, "_mock_mode") and self._mock_mode:
                self._mock_entities.pop(name, None)
            return result
        
        if hasattr(self, "_mock_mode") and self._mock_mode:
            self._mock_entities.pop(name, None)
            return True
        
        return False
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        store = self._get_neo4j_store()
        if store:
            return store.get_stats()
        
        if hasattr(self, "_mock_mode") and self._mock_mode:
            return {
                "entities": len(self._mock_entities),
                "relations": len(self._mock_relations),
                "mode": "mock"
            }
        
        return {"mode": "unknown"}
    
    def clear_all(self) -> None:
        """清空所有数据"""
        store = self._get_neo4j_store()
        if store:
            store.clear_all()
        
        if hasattr(self, "_mock_mode") and self._mock_mode:
            self._mock_entities.clear()
            self._mock_relations.clear()
        
        logger.info("知识库已清空")
