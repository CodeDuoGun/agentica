# -*- coding: utf-8 -*-
"""
TCM Knowledge Base with Graph RAG
中医知识图谱 + RAG 检索系统

Features:
- 知识图谱存储（实体-关系）
- 向量语义检索
- 图遍历查询
- 路径推理
"""
import json
import re
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
from pydantic import BaseModel

import networkx as nx


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


class TCMRelation(BaseModel):
    """中医关系模型"""
    source: str
    target: str
    relation_type: str  # treats, causes, belongs_to, contraindicated_with, etc.
    weight: float = 1.0
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class TCMKnowledgeGraph:
    """中医知识图谱"""
    
    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.entity_index: Dict[str, TCMEntity] = {}
        self.type_index: Dict[str, Set[str]] = defaultdict(set)
        self.alias_index: Dict[str, str] = {}  # alias -> entity_id
    
    def add_entity(self, entity: TCMEntity) -> None:
        """添加实体"""
        self.graph.add_node(entity.id, **entity.to_dict())
        self.entity_index[entity.id] = entity
        self.type_index[entity.type].add(entity.id)
        
        for alias in entity.aliases:
            self.alias_index[alias.lower()] = entity.id
    
    def add_relation(self, relation: TCMRelation) -> None:
        """添加关系"""
        self.graph.add_edge(
            relation.source,
            relation.target,
            relation_type=relation.relation_type,
            weight=relation.weight,
            description=relation.description
        )
    
    def get_entity(self, entity_id: str) -> Optional[TCMEntity]:
        """获取实体"""
        return self.entity_index.get(entity_id)
    
    def find_entity_by_name(self, name: str) -> Optional[TCMEntity]:
        """通过名称查找实体"""
        entity_id = self.alias_index.get(name.lower())
        if entity_id:
            return self.entity_index.get(entity_id)
        
        for entity in self.entity_index.values():
            if entity.name == name or name in entity.aliases:
                return entity
        return None
    
    def get_related_entities(
        self, 
        entity_id: str, 
        relation_types: Optional[List[str]] = None,
        depth: int = 1
    ) -> List[Tuple[TCMEntity, str, float]]:
        """获取相关实体 (实体, 关系类型, 权重)"""
        results = []
        
        if depth == 1:
            edges = self.graph.out_edges(entity_id, data=True)
            for source, target, data in edges:
                if relation_types is None or data.get('relation_type') in relation_types:
                    entity = self.entity_index.get(target)
                    if entity:
                        results.append((
                            entity,
                            data.get('relation_type', ''),
                            data.get('weight', 1.0)
                        ))
        else:
            paths = list(nx.single_source_shortest_path_length(
                self.graph, entity_id, cutoff=depth
            ).keys())
            paths.remove(entity_id)
            
            for path_id in paths:
                try:
                    shortest_path = nx.shortest_path(self.graph, entity_id, path_id)
                    if len(shortest_path) <= depth + 1:
                        entity = self.entity_index.get(path_id)
                        if entity:
                            weight = 1.0 / (len(shortest_path) - 1)
                            results.append((entity, 'path', weight))
                except nx.NetworkXNoPath:
                    continue
        
        return results
    
    def get_entities_by_type(self, entity_type: str) -> List[TCMEntity]:
        """获取指定类型的所有实体"""
        entity_ids = self.type_index.get(entity_type, set())
        return [self.entity_index[eid] for eid in entity_ids if eid in self.entity_index]
    
    def find_paths(
        self,
        source_name: str,
        target_name: str,
        max_length: int = 3
    ) -> List[List[str]]:
        """查找两个实体之间的路径"""
        source_entity = self.find_entity_by_name(source_name)
        target_entity = self.find_entity_by_name(target_name)
        
        if not source_entity or not target_entity:
            return []
        
        try:
            paths = list(nx.all_simple_paths(
                self.graph,
                source_entity.id,
                target_entity.id,
                cutoff=max_length
            ))
            return paths
        except nx.NetworkXNoPath:
            return []
    
    def to_dict(self) -> Dict[str, Any]:
        """导出为字典"""
        return {
            "entities": [e.to_dict() for e in self.entity_index.values()],
            "relations": [
                {"source": u, "target": v, **d}
                for u, v, d in self.graph.edges(data=True)
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TCMKnowledgeGraph":
        """从字典加载"""
        kg = cls()
        for entity_data in data.get("entities", []):
            entity = TCMEntity(**entity_data)
            kg.add_entity(entity)
        for rel_data in data.get("relations", []):
            relation = TCMRelation(**rel_data)
            kg.add_relation(relation)
        return kg


class TCMKnowledgeBase:
    """
    中医知识库 - 结合知识图谱和向量检索
    
    Features:
    - 知识图谱存储和查询
    - 向量语义检索
    - 混合检索策略
    - 内置中医知识数据
    """
    
    def __init__(
        self,
        embedding_model: Any = None,
        vector_db: Any = None,
        kg: Optional[TCMKnowledgeGraph] = None
    ):
        self.embedding_model = embedding_model
        self.vector_db = vector_db
        self.kg = kg or TCMKnowledgeGraph()
        self.documents: List[Dict[str, Any]] = []
        self._initialized = False
    
    def initialize(self) -> None:
        """初始化知识库"""
        if self._initialized:
            return
        
        self._load_default_knowledge()
        self._initialized = True
    
    def _load_default_knowledge(self) -> None:
        """加载默认中医知识"""
        default_kg = self._build_default_tcm_graph()
        for entity in default_kg:
            self.kg.add_entity(TCMEntity(**entity))
        
        for relation in self._get_default_relations():
            self.kg.add_relation(TCMRelation(**relation))
    
    def _build_default_tcm_graph(self) -> List[Dict[str, Any]]:
        """构建默认中医知识图谱"""
        entities = [
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
                "id": "lycium",
                "name": "枸杞子",
                "type": "herb",
                "aliases": ["枸杞", "甘枸杞"],
                "description": "滋补肝肾，益精明目",
                "properties": {
                    "taste": ["甘", "平"],
                    "channel_entering": ["肝", "肾"],
                    "functions": ["滋补肝肾", "益精明目"],
                    "dosage": "6-12g",
                    "contraindications": ["脾虚泄泻", "实热"]
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
                "id": "atractylodes",
                "name": "白术",
                "type": "herb",
                "aliases": ["於术", "冬术"],
                "description": "健脾益气，燥湿利水，止汗，安胎",
                "properties": {
                    "taste": ["甘", "苦", "温"],
                    "channel_entering": ["脾", "胃"],
                    "functions": ["健脾益气", "燥湿利水", "止汗", "安胎"],
                    "dosage": "6-12g",
                    "contraindications": ["阴虚内热", "津伤口渴"]
                }
            },
            {
                "id": "chinese_cinchona",
                "name": "柴胡",
                "type": "herb",
                "aliases": ["北柴胡", "南柴胡", "醋柴胡"],
                "description": "疏散退热，疏肝解郁，升举阳气",
                "properties": {
                    "taste": ["苦", "辛", "微寒"],
                    "channel_entering": ["肝", "胆"],
                    "functions": ["疏散退热", "疏肝解郁", "升举阳气"],
                    "dosage": "3-10g",
                    "contraindications": ["阴虚阳亢", "肝风内动"]
                }
            },
            {
                "id": "peony",
                "name": "白芍",
                "type": "herb",
                "aliases": ["杭芍", "川芍", "炒白芍", "酒白芍"],
                "description": "养血敛阴，柔肝止痛，平抑肝阳",
                "properties": {
                    "taste": ["苦", "酸", "微寒"],
                    "channel_entering": ["肝", "脾"],
                    "functions": ["养血敛阴", "柔肝止痛", "平抑肝阳"],
                    "dosage": "6-15g",
                    "contraindications": ["虚寒证", "阳衰寒盛"]
                }
            },
            {
                "id": "cinnamon",
                "name": "肉桂",
                "type": "herb",
                "aliases": ["玉桂", "官桂"],
                "description": "补火助阳，散寒止痛，温经通脉",
                "properties": {
                    "taste": ["辛", "甘", "大热"],
                    "channel_entering": ["肾", "脾", "心", "肝"],
                    "functions": ["补火助阳", "散寒止痛", "温经通脉"],
                    "dosage": "1-5g",
                    "contraindications": ["阴虚火旺", "里有实热"]
                }
            },
            {
                "id": "ginger",
                "name": "干姜",
                "type": "herb",
                "aliases": ["淡干姜", "泡姜"],
                "description": "温中散寒，回阳通脉，温肺化饮",
                "properties": {
                    "taste": ["辛", "热"],
                    "channel_entering": ["脾", "胃", "肾", "心", "肺"],
                    "functions": ["温中散寒", "回阳通脉", "温肺化饮"],
                    "dosage": "3-10g",
                    "contraindications": ["阴虚内热", "血热妄行"]
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
                "id": "eight_precious_decoction",
                "name": "八珍汤",
                "type": "prescription",
                "aliases": ["八珍"],
                "description": "益气补血，主治气血两虚证",
                "properties": {
                    "composition": ["四君子汤", "四物汤"],
                    "indication": "气血两虚证：面色苍白或萎黄，头晕目眩，气短懒言",
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
                "id": "baxiang_san",
                "name": "八珍散",
                "type": "prescription",
                "aliases": [],
                "description": "益气补血，主治气血两虚证",
                "properties": {
                    "composition": ["人参", "白术", "茯苓", "甘草", "熟地黄", "当归", "白芍", "川芎"],
                    "indication": "气血两虚证",
                    "usage": "水煎服"
                }
            },
            {
                "id": "liujunzi_decoction",
                "name": "六君子汤",
                "type": "prescription",
                "aliases": [],
                "description": "益气健脾，燥湿化痰，主治脾胃气虚兼痰湿证",
                "properties": {
                    "composition": ["人参", "白术", "茯苓", "甘草", "半夏", "陈皮"],
                    "indication": "脾胃气虚兼痰湿证：食少便溏，痰多色白",
                    "usage": "水煎服"
                }
            },
            {
                "id": "yinchen_decoction",
                "name": "茵陈蒿汤",
                "type": "prescription",
                "aliases": [],
                "description": "清热利湿退黄，主治湿热黄疸",
                "properties": {
                    "composition": ["茵陈", "栀子", "大黄"],
                    "indication": "湿热黄疸：身目发黄，黄色鲜明，小便短赤",
                    "usage": "水煎服"
                }
            },
            {
                "id": "liver_channel",
                "name": "肝经",
                "type": "meridian",
                "aliases": ["足厥阴肝经"],
                "description": "足厥阴肝经，循行于胁肋部，与肝胆疾病密切相关",
                "properties": {
                    "route": "足大趾→下肢内侧→腹部→胁肋→目系→巅顶",
                    "related_organs": ["肝", "胆"],
                    "main_points": ["太冲", "期门", "肝俞"]
                }
            },
            {
                "id": " spleen_channel",
                "name": "脾经",
                "type": "meridian",
                "aliases": ["足太阴脾经"],
                "description": "足太阴脾经，循行于下肢内侧后缘，与消化系统密切相关",
                "properties": {
                    "route": "足大趾→下肢内侧→腹部→胸部",
                    "related_organs": ["脾", "胃"],
                    "main_points": ["三阴交", "阴陵泉", "足三里"]
                }
            },
            {
                "id": "hegu",
                "name": "合谷",
                "type": "acupoint",
                "aliases": ["虎口"],
                "description": "手阳明大肠经穴，主治头痛、牙痛、面口疾病",
                "properties": {
                    "location": "手背第1、2掌骨间，当第2掌骨桡侧的中点处",
                    "channel": "手阳明大肠经",
                    "indications": ["头痛", "牙痛", "面口疾病", "发热", "汗证"]
                }
            },
            {
                "id": "taichong",
                "name": "太冲",
                "type": "acupoint",
                "aliases": [],
                "description": "足厥阴肝经穴，主治头痛、眩晕、胁痛、情志疾病",
                "properties": {
                    "location": "足背第1、2跖骨结合部前方凹陷中",
                    "channel": "足厥阴肝经",
                    "indications": ["头痛", "眩晕", "胁痛", "情志疾病", "月经不调"]
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
                "id": "sanyinjiao",
                "name": "三阴交",
                "type": "acupoint",
                "aliases": [],
                "description": "足太阴脾经穴，主治妇科、泌尿、生殖系统疾病",
                "properties": {
                    "location": "小腿内侧，内踝尖上3寸，胫骨内侧缘后际",
                    "channel": "足太阴脾经",
                    "indications": ["月经不调", "痛经", "不孕", "失眠", "眩晕"]
                }
            },
            {
                "id": "neiguan",
                "name": "内关",
                "type": "acupoint",
                "aliases": [],
                "description": "手厥阴心包经穴，主治心悸、胸闷、胃痛、呕吐",
                "properties": {
                    "location": "前臂前区，腕掌侧远端横纹上2寸，掌长肌腱与桡侧腕屈肌腱之间",
                    "channel": "手厥阴心包经",
                    "indications": ["心悸", "胸闷", "胃痛", "呕吐", "失眠"]
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
            }
        ]
        return entities
    
    def _get_default_relations(self) -> List[Dict[str, Any]]:
        """获取默认关系"""
        return [
            {"source": "qi_deficiency", "target": "spleen_qi_sinking", "relation_type": "may_cause", "weight": 0.8},
            {"source": "qi_deficiency", "target": "lung_qi_deficiency", "relation_type": "may_cause", "weight": 0.8},
            {"source": "yin_deficiency", "target": "kidney_yin_deficiency", "relation_type": "includes", "weight": 1.0},
            {"source": "yang_deficiency", "target": "kidney_yang_deficiency", "relation_type": "includes", "weight": 1.0},
            {"source": "yin_deficiency", "target": "heart_fire", "relation_type": "may_cause", "weight": 0.6},
            {"source": "qi_stagnation", "target": "liver_fire", "relation_type": "may_cause", "weight": 0.7},
            {"source": "spleen_qi_sinking", "target": "four_gentleman_decoction", "relation_type": "treated_by", "weight": 1.0},
            {"source": "qi_deficiency", "target": "four_gentleman_decoction", "relation_type": "treated_by", "weight": 1.0},
            {"source": "blood_deficiency", "target": "four_suben_decoction", "relation_type": "treated_by", "weight": 1.0},
            {"source": "qi_deficiency", "target": "blood_deficiency", "relation_type": "may_cause", "weight": 0.5},
            {"source": "qi_deficiency", "target": "eight_precious_decoction", "relation_type": "treated_by", "weight": 1.0},
            {"source": "blood_deficiency", "target": "eight_precious_decoction", "relation_type": "treated_by", "weight": 1.0},
            {"source": "kidney_yin_deficiency", "target": "liuwei_dehuang_decoction", "relation_type": "treated_by", "weight": 1.0},
            {"source": "qi_stagnation", "target": "xiaoyao_decoction", "relation_type": "treated_by", "weight": 1.0},
            {"source": "blood_deficiency", "target": "xiaoyao_decoction", "relation_type": "treated_by", "weight": 0.7},
            {"source": "phlegm_damp", "target": "liujunzi_decoction", "relation_type": "treated_by", "weight": 1.0},
            {"source": "ginseng", "target": "four_gentleman_decoction", "relation_type": "component_of", "weight": 1.0},
            {"source": "astragalus", "target": "four_gentleman_decoction", "relation_type": "component_of", "weight": 1.0},
            {"source": "poria", "target": "four_gentleman_decoction", "relation_type": "component_of", "weight": 1.0},
            {"source": "licorice", "target": "four_gentleman_decoction", "relation_type": "component_of", "weight": 1.0},
            {"source": "rehmannia", "target": "four_suben_decoction", "relation_type": "component_of", "weight": 1.0},
            {"source": "rehmannia", "target": "liuwei_dehuang_decoction", "relation_type": "component_of", "weight": 1.0},
            {"source": "ginseng", "target": "eight_precious_decoction", "relation_type": "component_of", "weight": 1.0},
            {"source": "liver_fire", "target": "taichong", "relation_type": "treated_by_acupoint", "weight": 1.0},
            {"source": "qi_stagnation", "target": "taichong", "relation_type": "treated_by_acupoint", "weight": 1.0},
            {"source": "qi_deficiency", "target": "zusanli", "relation_type": "treated_by_acupoint", "weight": 1.0},
            {"source": "poor_appetite", "target": "zusanli", "relation_type": "treated_by_acupoint", "weight": 1.0},
            {"source": "insomnia", "target": "sanyinjiao", "relation_type": "treated_by_acupoint", "weight": 1.0},
            {"source": "insomnia", "target": "neiguan", "relation_type": "treated_by_acupoint", "weight": 1.0},
            {"source": "fatigue", "target": "qi_deficiency", "relation_type": "related_to", "weight": 0.9},
            {"source": "poor_appetite", "target": "qi_deficiency", "relation_type": "related_to", "weight": 0.9},
            {"source": "headache", "target": "liver_fire", "relation_type": "may_cause", "weight": 0.7},
            {"source": "headache", "target": "blood_deficiency", "relation_type": "may_cause", "weight": 0.6},
        ]
    
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
            entity = self.kg.find_entity_by_name(symptom)
            if entity:
                related = self.kg.get_related_entities(
                    entity.id,
                    relation_types=["may_cause", "related_to"],
                    depth=2
                )
                
                for rel_entity, rel_type, weight in related:
                    if rel_entity.type == "syndrome":
                        syndrome_info = self._get_syndrome_info(rel_entity)
                        treatment = self._find_treatment_for_syndrome(rel_entity.id)
                        
                        results.append({
                            "symptom": symptom,
                            "syndrome": syndrome_info,
                            "treatment": treatment,
                            "confidence": weight,
                            "source": "knowledge_graph"
                        })
        
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:max_results]
    
    def _get_syndrome_info(self, syndrome_entity: TCMEntity) -> Dict[str, Any]:
        """获取证型详细信息"""
        related_entities = self.kg.get_related_entities(
            syndrome_entity.id,
            depth=1
        )
        
        related_herbs = []
        related_prescriptions = []
        related_acupoints = []
        
        for entity, rel_type, weight in related_entities:
            if entity.type == "herb":
                related_herbs.append({
                    "name": entity.name,
                    "description": entity.description,
                    "relation": rel_type
                })
            elif entity.type == "prescription":
                related_prescriptions.append({
                    "name": entity.name,
                    "description": entity.description,
                    "composition": entity.properties.get("composition", []),
                    "indication": entity.properties.get("indication", ""),
                    "relation": rel_type
                })
            elif entity.type == "acupoint":
                related_acupoints.append({
                    "name": entity.name,
                    "location": entity.properties.get("location", ""),
                    "indications": entity.properties.get("indications", []),
                    "relation": rel_type
                })
        
        return {
            "name": syndrome_entity.name,
            "description": syndrome_entity.description,
            "category": syndrome_entity.properties.get("category", ""),
            "related_organs": syndrome_entity.properties.get("related_organs", []),
            "common_symptoms": syndrome_entity.properties.get("common_symptoms", []),
            "related_herbs": related_herbs,
            "related_prescriptions": related_prescriptions,
            "related_acupoints": related_acupoints
        }
    
    def _find_treatment_for_syndrome(self, syndrome_id: str) -> Optional[Dict[str, Any]]:
        """查找证型的治疗方案"""
        related = self.kg.get_related_entities(
            syndrome_id,
            relation_types=["treated_by", "treated_by_acupoint"],
            depth=1
        )
        
        treatment = {
            "herbal_prescriptions": [],
            "acupoints": []
        }
        
        for entity, rel_type, weight in related:
            if entity.type == "prescription":
                treatment["herbal_prescriptions"].append({
                    "name": entity.name,
                    "composition": entity.properties.get("composition", []),
                    "indication": entity.properties.get("indication", ""),
                    "modifications": entity.properties.get("modifications", {})
                })
            elif entity.type == "acupoint":
                treatment["acupoints"].append({
                    "name": entity.name,
                    "location": entity.properties.get("location", ""),
                    "indications": entity.properties.get("indications", [])
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
        entity = self.kg.find_entity_by_name(name)
        if not entity:
            return {"error": f"未找到实体: {name}"}
        
        result = {
            "entity": entity.to_dict(),
            "type": entity.type
        }
        
        if include_related:
            related = self.kg.get_related_entities(entity.id, depth=1)
            result["related"] = [
                {
                    "entity": r[0].to_dict(),
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
        
        for entity in self.kg.entity_index.values():
            if entity_types and entity.type not in entity_types:
                continue
            
            score = 0.0
            
            if query.lower() in entity.name.lower():
                score += 0.5
            
            for alias in entity.aliases:
                if query.lower() in alias.lower():
                    score += 0.3
            
            if keywords:
                for keyword in keywords:
                    if keyword in entity.description:
                        score += 0.2
                    for symptom in entity.properties.get("common_symptoms", []):
                        if keyword in symptom:
                            score += 0.3
            
            if score > 0:
                results.append({
                    "entity": entity.to_dict(),
                    "score": min(score, 1.0)
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
        entity = self.kg.find_entity_by_name(syndrome_name)
        if not entity or entity.type != "syndrome":
            return {"error": f"未找到证型: {syndrome_name}"}
        
        syndrome_info = self._get_syndrome_info(entity)
        treatment = self._find_treatment_for_syndrome(entity.id)
        
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
        syndrome: TCMEntity,
        patient_info: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        """生成生活建议"""
        advice_list = []
        
        if "虚" in syndrome.properties.get("category", ""):
            advice_list.extend([
                "注意休息，避免过度劳累",
                "适当进行轻度运动，如散步、太极拳",
                "保持充足睡眠"
            ])
        
        if "热" in syndrome.name or "火" in syndrome.name:
            advice_list.extend([
                "保持情绪稳定，避免急躁易怒",
                "避免辛辣刺激性食物",
                "多饮水，保持大便通畅"
            ])
        
        if "郁" in syndrome.name or "气滞" in syndrome.name:
            advice_list.extend([
                "保持心情舒畅，适当进行放松训练",
                "多参加户外活动",
                "避免长时间处于压抑情绪中"
            ])
        
        return advice_list
    
    def _generate_diet_advice(self, syndrome: TCMEntity) -> List[str]:
        """生成饮食建议"""
        advice_list = []
        
        if "yin" in syndrome.id or "阴虚" in syndrome.name:
            advice_list.extend([
                "宜食用滋阴润燥的食物，如银耳、百合、梨等",
                "少吃辛辣刺激性食物",
                "避免油炸、烧烤类食物"
            ])
        elif "yang" in syndrome.id or "阳虚" in syndrome.name:
            advice_list.extend([
                "宜食用温补食物，如羊肉、核桃、桂圆等",
                "少吃生冷寒凉食物",
                "可适当食用姜、葱、蒜等温性调料"
            ])
        elif "qi" in syndrome.id or "气虚" in syndrome.name:
            advice_list.extend([
                "宜食用补气食物，如山药、黄芪、红枣等",
                "少吃耗气食物，如萝卜、莱菔子等",
                "避免过度思虑"
            ])
        elif "痰湿" in syndrome.name or "湿" in syndrome.name:
            advice_list.extend([
                "宜食用清淡易消化的食物",
                "少吃甜腻、油腻、生冷食物",
                "可适当食用薏苡仁、冬瓜、赤小豆等利湿食物"
            ])
        
        return advice_list
    
    def _generate_precautions(self, syndrome: TCMEntity) -> List[str]:
        """生成注意事项"""
        precautions = []
        
        if "虚" in syndrome.properties.get("category", ""):
            precautions.append("避免过度劳累和剧烈运动")
        
        if "热" in syndrome.name or "火" in syndrome.name:
            precautions.append("避免情绪激动和高温环境")
        
        precautions.extend([
            "遵医嘱服药，不可擅自停药或换药",
            "如症状加重或出现新症状，请及时就医"
        ])
        
        return precautions
