# -*- coding: utf-8 -*-
"""
TCM Agent Data Models
中医问诊系统的数据模型定义
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class IntentionCategory(str, Enum):
    """意图大类"""
    DOCTOR_SPECIFIC_MEDICAL = "doctor_specific_medical"  # 医生指定领域的医疗问题咨询
    NODOCTOR_SPECIFIC_MEDICAL = "nodoctor_specific_medical"  # 非医生指定领域的普通医疗问题咨询
    CONSULTATION = "consultation"             # 问诊咨询（多轮问答收集信息）
    OTHER = "other"                          # 其他问题处理
    UNKNOWN = "unknown"                       # 未知


class ConsultationVisitType(str, Enum):
    """就诊类型"""
    FIRST_VISIT = "first_visit"              # 初诊
    FOLLOW_UP_VISIT = "follow_up_visit"      # 复诊


class ConsultationPhase(str, Enum):
    """问诊阶段"""
    WELCOME = "welcome"                       # 欢迎阶段
    CONSULTATION = "consultation"             # 问诊阶段
    SUPPLEMENTARY = "supplementary"           # 补充信息阶段
    COMPLETE = "complete"                    # 完成阶段


class SymptomLocation(str, Enum):
    """症状部位"""
    HEAD = "head"
    FACE = "face"
    NECK = "neck"
    CHEST = "chest"
    ABDOMEN = "abdomen"
    BACK = "back"
    LIMBS = "limbs"
    SKIN = "skin"
    WHOLE_BODY = "whole_body"
    OTHER = "other"


class TongueType(str, Enum):
    """舌象类型"""
    PALE_RED = "pale_red"           # 淡红舌
    RED = "red"                     # 红舌
    DARK_RED = "dark_red"           # 绛舌
    PURPLE = "purple"               # 紫舌
    PALE = "pale"                   # 淡白舌
    OTHER = "other"


class TongueCoating(str, Enum):
    """舌苔类型"""
    THIN_WHITE = "thin_white"       # 薄白苔
    THICK_WHITE = "thick_white"     # 厚白苔
    THIN_YELLOW = "thin_yellow"     # 薄黄苔
    THICK_YELLOW = "thick_yellow"   # 厚黄苔
    GREASY = "greasy"               # 腻苔
    PEELING = "peeling"             # 剥苔
    OTHER = "other"


class PulseType(str, Enum):
    """脉象类型"""
    FLOATING = "floating"           # 浮脉
    DEEP = "deep"                   # 沉脉
    SLOW = "slow"                   # 迟脉
    RAPID = "rapid"                 # 数脉
    WEAK = "weak"                   # 弱脉
    STRING = "string"               # 弦脉
    SLIPPERY = "slippery"           # 滑脉
    CHOPPY = "choppy"               # 涩脉
    OTHER = "other"


class PatientInfo(BaseModel):
    """患者基本信息"""
    name: Optional[str] = Field(None, description="姓名", validation_alias="name")
    age: Optional[int] = Field(None, description="年龄", validation_alias="age")
    gender: Optional[str] = Field(None, description="性别", validation_alias="gender")

    model_config = ConfigDict(populate_by_name=True)


class PhysicalInfo(BaseModel):
    """体格检查信息"""
    tongue_type: Optional[TongueType] = Field(None, description="舌质")
    tongue_coating: Optional[TongueCoating] = Field(None, description="舌苔")
    pulse_type: Optional[PulseType] = Field(None, description="脉象")
    temperature: Optional[str] = Field(None, description="体温")
    blood_pressure: Optional[str] = Field(None, description="血压")
    heart_rate: Optional[str] = Field(None, description="心率")
    breathing_rate: Optional[str] = Field(None, description="呼吸频率")
    
    class Config:
        use_enum_values = True


class AllergyInfo(BaseModel):
    """过敏史"""
    has_allergy: bool = Field(False, description="是否有过敏史")
    allergen: Optional[str] = Field(None, description="过敏原")
    reaction: Optional[str] = Field(None, description="过敏反应")
    
    class Config:
        use_enum_values = True


class MedicalHistory(BaseModel):
    """病史信息"""
    present_illness: Optional[str] = Field(None, description="现病史")
    past_history: Optional[str] = Field(None, description="既往史")
    personal_history: Optional[str] = Field(None, description="个人史")
    family_history: Optional[str] = Field(None, description="家族史")
    marriage_history: Optional[str] = Field(None, description="婚育史")
    menstruation_history: Optional[str] = Field(None, description="月经史")
    
    class Config:
        use_enum_values = True


class DiagnosisInfo(BaseModel):
    """诊断信息"""
    syndrome_type: Optional[str] = Field(None, description="中医证型")
    tcm_diagnosis: Optional[str] = Field(None, description="中医证名")
    analysis: Optional[str] = Field(None, description="辨证分析")
    prescription_recommendation: Optional[str] = Field(None, description="处方建议")
    
    class Config:
        use_enum_values = True


class TreatmentPrinciple(BaseModel):
    """治疗原则"""
    principle: Optional[str] = Field(None, description="治法")
    prescription: Optional[str] = Field(None, description="方剂")
    herbal_formula: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="中药组成")
    dosage: Optional[str] = Field(None, description="用量")
    usage: Optional[str] = Field(None, description="用法")
    
    class Config:
        use_enum_values = True


class HealthAdvice(BaseModel):
    """养生建议"""
    diet: Optional[str] = Field(None, description="饮食建议")
    lifestyle: Optional[str] = Field(None, description="生活方式建议")
    emotional: Optional[str] = Field(None, description="情志调节")
    exercise: Optional[str] = Field(None, description="运动建议")
    other: Optional[str] = Field(None, description="其他建议")
    
    class Config:
        use_enum_values = True


class TreatmentPlan(BaseModel):
    """治疗方案"""
    principle: Optional[str] = Field(None, description="治法")
    prescription: Optional[str] = Field(None, description="方药")
    acupuncture: Optional[str] = Field(None, description="针灸")
    tuina: Optional[str] = Field(None, description="推拿")
    moxibustion: Optional[str] = Field(None, description="艾灸")
    health_advice: HealthAdvice = Field(default_factory=HealthAdvice, description="养生建议")
    
    class Config:
        use_enum_values = True


class SyndromeType(str, Enum):
    """证型"""
    YIN_DEFICIENCY = "yin_deficiency"         # 阴虚
    YANG_DEFICIENCY = "yang_deficiency"       # 阳虚
    QI_DEFICIENCY = "qi_deficiency"           # 气虚
    BLOOD_DEFICIENCY = "blood_deficiency"     # 血虚
    DAMP_HEAT = "damp_heat"                   # 湿热
    PHLEGM_DAMP = "phlegm_damp"               # 痰湿
    QI_STAGNATION = "qi_stagnation"           # 气滞
    BLOOD_STASIS = "blood_stasis"             # 血瘀
    COLD_CONSTRICTION = "cold_constriction"   # 寒凝
    HEAT_TOXIN = "heat_toxin"                 # 热毒
    OTHER = "other"                           # 其他


class SymptomInfo(BaseModel):
    """症状信息"""
    name: str = Field(..., description="症状名称")
    severity: Optional[str] = Field(None, description="严重程度：轻/中/重")
    duration: Optional[str] = Field(None, description="持续时间")
    location: Optional[str] = Field(None, description="部位")
    description: Optional[str] = Field(None, description="详细描述")
    trigger: Optional[str] = Field(None, description="诱因")
    relief: Optional[str] = Field(None, description="缓解因素")
    
    class Config:
        use_enum_values = True


class ConsultationRecord(BaseModel):
    """结构化病历"""
    # 会话信息
    session_id: Optional[str] = Field(None, description="会话ID")
    visit_type: Optional[ConsultationVisitType] = Field(None, description="就诊类型")
    visit_date: datetime = Field(default_factory=datetime.now, description="就诊日期")
    
    # 基本信息
    # TODO 姓名不重要
    patient_name: Optional[str] = Field(None, description="患者姓名")
    patient_age: Optional[str] = Field(None, description="患者年龄")
    patient_gender: Optional[str] = Field(None, description="患者性别")
    
    # 主诉
    chief_complaint: Optional[str] = Field(None, description="主诉")
    
    # 病史
    present_illness: Optional[str] = Field(None, description="现病史")
    past_history: Optional[str] = Field(None, description="既往史")
    personal_history: Optional[str] = Field(None, description="个人史")
    family_history: Optional[str] = Field(None, description="家族史")
    marriage_history: Optional[str] = Field(None, description="婚育史")
    
    # 过敏史
    allergy_info: Optional[AllergyInfo] = Field(None, description="过敏史")
    
    # 症状列表
    symptoms: List[SymptomInfo] = Field(default_factory=list)
    
    # 体格检查
    physical_exam: Optional[PhysicalInfo] = Field(None, description="体格检查")
    
    # 舌脉信息
    tongue_image_url: Optional[str] = Field(None, description="舌面照片URL")
    tongue_image_analysis: Optional[str] = Field(None, description="舌象分析")
    face_image_url: Optional[str] = Field(None, description="面部照片URL")
    face_image_analysis: Optional[str] = Field(None, description="面色分析")
    
    # 检查报告
    exam_report_url: Optional[str] = Field(None, description="检查报告URL")
    exam_report_summary: Optional[str] = Field(None, description="检查报告摘要")
    
    # 补充信息
    supplementary_info: Optional[str] = Field(None, description="补充说明")

    # 诊断
    diagnosis: Optional[DiagnosisInfo] = Field(None, description="诊断信息")
    treatment_plan: Optional[TreatmentPlan] = Field(None, description="治疗方案")
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True


# ==================== 问诊状态和槽位定义 ====================

class ConsultationSlot(BaseModel):
    """问诊槽位定义"""
    key: str = Field(..., description="槽位标识")
    question: str = Field(..., description="询问问题")
    required: bool = Field(False, description="是否必需")
    extracted_from_history: bool = Field(False, description="是否从历史中提取")
    
    class Config:
        use_enum_values = True


class SlotStatus(str, Enum):
    """槽位状态"""
    PENDING = "pending"           # 待收集
    COLLECTING = "collecting"    # 收集中
    COLLECTED = "collected"      # 已收集
    SKIPPED = "skipped"           # 已跳过


class SlotCollectionStatus(BaseModel):
    """槽位收集状态"""
    key: str
    status: SlotStatus = Field(SlotStatus.PENDING)
    value: Optional[Any] = Field(None, description="收集到的值")
    raw_content: Optional[str] = Field(None, description="原始内容")


class ConsultationState(BaseModel):
    """问诊状态模型 - 管理多轮问诊的会话状态"""
    session_id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S"))
    
    # 意图路由
    current_intent: IntentionCategory = Field(IntentionCategory.UNKNOWN, description="当前意图")
    consultation_phase: ConsultationPhase = Field(ConsultationPhase.WELCOME, description="问诊阶段")
    
    # 就诊信息
    visit_type: Optional[ConsultationVisitType] = Field(None, description="就诊类型")
    
    # ========== 问诊信息槽位 ==========
    # 基本信息
    patient_info: PatientInfo = Field(default_factory=PatientInfo, description="患者基本信息")
    
    # 主诉
    chief_complaint: Optional[str] = Field(None, description="主诉")
    
    # 现病史
    symptoms: List[SymptomInfo] = Field(default_factory=list, description="症状列表")
    # 现病史是诊疗经过的记录
    present_illness: Optional[str] = Field(None, description="现病史描述")
    
    # 既往史
    past_history: Optional[str] = Field(None, description="既往史")
    
    # 过敏史
    allergy_info: AllergyInfo = Field(default_factory=AllergyInfo, description="过敏史")
    
    # 婚育史
    marriage_history: Optional[str] = Field(None, description="婚育史")
    
    # 个人史
    personal_history: Optional[str] = Field(None, description="个人史")
    
    # 家族史
    family_history: Optional[str] = Field(None, description="家族史")
    
    # 舌照
    tongue_image_url: Optional[str] = Field(None, description="舌面照片URL")
    tongue_analysis: Optional[str] = Field(None, description="舌象分析")
    
    # 面照
    face_image_url: Optional[str] = Field(None, description="面部照片URL")
    face_analysis: Optional[str] = Field(None, description="面色分析")
    
    # 检查报告
    exam_report_url: Optional[str] = Field(None, description="检查报告URL")
    exam_report_summary: Optional[str] = Field(None, description="检查报告摘要")

    # ========== 诊断结果 ==========
    diagnosis: Optional[DiagnosisInfo] = None
    treatment_plan: Optional[TreatmentPlan] = None 
    # 补充信息
    supplementary_info: Optional[str] = Field(None, description="补充说明")
    
    # ========== 槽位收集状态 ==========
    slot_status: Dict[str, SlotCollectionStatus] = Field(default_factory=dict, description="槽位状态")
    pending_slots: List[str] = Field(default_factory=list, description="待收集槽位列表")
    current_slot_key: Optional[str] = Field(None, description="当前正在收集的槽位")
    collected_slots: Dict[str, Any] = Field(default_factory=dict, description="已收集槽位")
    
    
    # ========== 会话状态 ==========
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    turn_count: int = Field(0, description="对话轮数")
    max_turns: int = Field(50, description="最大对话轮数")
    is_complete: bool = Field(False)
    consultation_record: Optional[ConsultationRecord] = Field(default_factory=ConsultationRecord)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True
    
    @property
    def current_phase(self) -> str:
        """兼容性别名 - 返回 consultation_phase 的值"""
        return self.consultation_phase.value if hasattr(self.consultation_phase, 'value') else self.consultation_phase


# 问诊槽位定义列表
CONSULTATION_SLOTS_DEFINITION = [
    # 就诊类型
    {"key": "visit_type", "required": True, "group": "basis"},
    # 基本信息
    {"key": "gender", "required": True, "group": "basic"},
    {"key": "age",  "required": True, "group": "basic"},
    
    # 主诉
    {"key": "chief_complaint", "required": True, "group": "chief_complaint"},
    
    # 症状（结构化）
    {
        "key": "symptoms",
        "required": True,
        "group": "symptom",
        "type": "list_object",  
        "schema": "SymptomInfo"
    },
    
    # 既往史
    {"key": "past_history","required": True, "group": "past"},
    
    # 过敏史
    {"key": "allergy",  "required": True, "group": "allergy"},
    
    # 婚育史
    {"key": "marriage",  "required": True, "group": "marriage"},
    
    # 个人史
    {"key": "personal","required": True, "group": "personal"},
    
    # 家族史
    {"key": "family",  "required": True, "group": "family"},
    
    # 舌照
    {"key": "tongue", "required": False, "group": "tongue"},
    {"key": "tongue_analysis", "required": False, "group": "tongue"},
    
    # 面照
    {"key": "face", "required": False, "group": "face"},
    {"key": "face_analysis", "required": False, "group": "face"},
    
    # 检查报告
    {"key": "exam_report", "required": False, "group": "exam"},
    {"key": "exam_analysis", "required": False, "group": "exam"},
    
    # 补充信息
    {"key": "supplementary",  "required": False, "group": "supplementary"},
]

# 必需槽位
REQUIRED_SLOTS = ["gender", "age", "chief_complaint", "symptoms", "past_history", "allergy", "marriage", "personal", "family"]



class IntentionResult(BaseModel):
    """意图识别结果模型"""
    category: IntentionCategory = Field(..., description="意图大类")
    intention: Optional[str] = Field(None, description="具体意图描述")
    confidence: float = Field(..., ge=0.0, le=1.0, description="分类置信度")
    entities: Dict[str, Any] = Field(default_factory=dict, description="提取的实体信息")
    follow_up_question: Optional[str] = Field(None, description="追问问题")
    should_forward_to_consultation: bool = Field(False, description="是否需要进入问诊流程")
    hospital_referral: Optional[str] = Field(None, description="推荐就诊地址")

    model_config = ConfigDict(populate_by_name=True)


class KGQueryResult(BaseModel):
    """知识图谱查询结果模型"""
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="实体列表")
    relations: List[Dict[str, Any]] = Field(default_factory=list, description="关系列表")
    context: str = Field(..., description="检索到的上下文")
    source: str = Field("knowledge_graph", description="来源")
    relevance_score: float = Field(0.0, description="相关度评分")


class SlotUpdate(BaseModel):
    """槽位更新"""
    field: str = Field(..., description="字段名（必须来自病历结构）")
    value: Any = Field(..., description="字段值")
    confidence: float = Field(..., ge=0.0, le=1.0)

class ConsultationControl(BaseModel):
    """对话控制"""
    next_action: str = Field(
        ...,
        description="next_question / ask_image / finish / clarify"
    )
    target_slot: Optional[str] = Field(None, description="当前要采集的槽位")
    priority: Optional[int] = Field(1, description="优先级")


class ConsultationTurnResult(BaseModel):
    """多轮问诊结果（核心）"""
    slot_updates: List[SlotUpdate] = Field(
        default_factory=list,
        description="本轮提取并更新的槽位"
    )

    # 📊 当前完整结构（可选，用于强同步）
    structured_data: Optional[ConsultationRecord] = Field(
        None,
        description="病历结构"
    )

    # 💬 对话输出
    reply: str = Field(..., description="下一句对用户说的话")

    # 🎯 控制流
    control: ConsultationControl = Field(...)

    # 🖼️ 多模态（图片）
    image_request: Optional[str] = Field(
        None,
        description="tongue / face / report"
    )

    # 🏁 是否结束
    is_finished: bool = Field(False)

    # ⚠️ 风险提示（医疗安全）
    risk_alert: Optional[str] = Field(None)

    class Config:
        use_enum_values = True


def get_enum_value(enum_or_str: Any) -> str:
    """安全获取枚举值，处理字符串或枚举对象"""
    if isinstance(enum_or_str, str):
        return enum_or_str
    if hasattr(enum_or_str, 'value'):
        return enum_or_str.value
    return str(enum_or_str)


def get_slot_by_key(key: str) -> Optional[Dict]:
    """根据 key 获取槽位定义"""
    for slot in CONSULTATION_SLOTS_DEFINITION:
        if slot["key"] == key:
            return slot
    return None


def get_next_slot(pending_slots: List[str]) -> Optional[str]:
    """获取下一个待收集的槽位"""
    for slot_def in CONSULTATION_SLOTS_DEFINITION:
        if slot_def["key"] in pending_slots:
            return slot_def["key"]
    return None


def is_required_slot(key: str) -> bool:
    """判断是否为必需槽位"""
    return key in REQUIRED_SLOTS
