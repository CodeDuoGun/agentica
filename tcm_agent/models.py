# -*- coding: utf-8 -*-
"""
TCM Agent Data Models
中医问诊系统的数据模型定义
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class IntentionCategory(str, Enum):
    """意图大类"""
    GENERAL_MEDICAL = "general_medical"      # 普通医疗问题咨询
    CONSULTATION = "consultation"             # 问诊咨询（进入问诊流程）
    NON_MEDICAL = "non_medical"             # 非医疗咨询
    UNKNOWN = "unknown"                       # 未知


class ConsultationVisitType(str, Enum):
    """就诊类型"""
    FIRST_VISIT = "first_visit"              # 初诊
    FOLLOW_UP_VISIT = "follow_up_visit"      # 复诊


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
    THICK_WHITE = "thick_white"     # 白厚苔
    THIN_YELLOW = "thin_yellow"     # 薄黄苔
    THICK_YELLOW = "thick_yellow"   # 黄厚苔
    GREASY = "greasy"               # 腻苔
    DRY = "dry"                     # 燥苔
    THIN = "thin"                   # 少苔
    OTHER = "other"


class PulseType(str, Enum):
    """脉象类型"""
    FLOATING = "floating"           # 浮脉
    DEEP = "deep"                   # 沉脉
    SLOW = "slow"                   # 迟脉
    RAPID = "rapid"                 # 数脉
    WEAK = "weak"                   # 弱脉
    STRING_TAUT = "string_taut"     # 弦脉
    SLIPPERY = "slippery"          # 滑脉
    WIRY = "wiry"                  # 紧脉
    THREAD = "thread"              # 细脉
    OTHER = "other"


class SyndromeType(str, Enum):
    """证型（辨证结果）"""
    YIN_DEFICIENCY = "yin_deficiency"           # 阴虚
    YANG_DEFICIENCY = "yang_deficiency"         # 阳虚
    QI_DEFICIENCY = "qi_deficiency"             # 气虚
    BLOOD_DEFICIENCY = "blood_deficiency"       # 血虚
    PHLEGM_DAMP = "phlegm_damp"                 # 痰湿
    BLOOD_STASIS = "blood_stasis"               # 血瘀
    QI_STAGNATION = "qi_stagnation"             # 气郁
    HEAT = "heat"                               # 热证
    COLD = "cold"                               # 寒证
    EXCESS = "excess"                           # 实证
    DEFICIENCY = "deficiency"                   # 虚证
    OTHER = "other"


class ConsultationPhase(str, Enum):
    """问诊阶段"""
    WELCOME = "welcome"                      # 欢迎/确认就诊类型
    BASIC_INFO = "basic_info"               # 收集基本信息
    CHIEF_COMPLAINT = "chief_complaint"     # 主诉
    MEDICAL_HISTORY = "medical_history"      # 病史收集
    ATTACHMENTS = "attachments"             # 上传附件（检查报告/舌面照片）
    SUPPLEMENTARY = "supplementary"          # 补充信息
    DIAGNOSIS = "diagnosis"                 # 诊断
    TREATMENT = "treatment"                 # 治疗方案
    COMPLETE = "complete"                   # 完成


class Gender(str, Enum):
    """性别"""
    MALE = "男"
    FEMALE = "女"
    OTHER = "other"


class SymptomInfo(BaseModel):
    """症状信息模型"""
    name: str = Field(..., description="症状名称")
    location: Optional[SymptomLocation] = Field(None, description="症状部位")
    severity: int = Field(3, ge=1, le=5, description="严重程度 1-5")
    duration: Optional[str] = Field(None, description="持续时间")
    frequency: Optional[str] = Field(None, description="发作频率")
    triggers: Optional[List[str]] = Field(default_factory=list, description="诱因")
    description: Optional[str] = Field(None, description="详细描述")
    
    class Config:
        use_enum_values = True


class PhysicalInfo(BaseModel):
    """体征信息模型"""
    tongue_type: Optional[TongueType] = Field(None, description="舌色")
    tongue_coating: Optional[TongueCoating] = Field(None, description="舌苔")
    pulse_type: Optional[List[PulseType]] = Field(default_factory=list, description="脉象")
    complexion: Optional[str] = Field(None, description="面色")
    
    class Config:
        use_enum_values = True


class PatientInfo(BaseModel):
    """患者基本信息模型"""
    name: Optional[str] = Field(None, description="姓名")
    age: Optional[int] = Field(None, ge=0, le=150, description="年龄")
    gender: Optional[Gender] = Field(None, description="性别")
    # marriage_history: List[str] = Field(default_factory=list, description="婚育史")  
    # personal_history: List[str] = Field(default_factory=list, description="个人史") 
    # past_history: List[str] = Field(default_factory=list, description="既往病史")
    # family_history: List[str] = Field(default_factory=list, description="家族病史")
    # current_medications: List[str] = Field(default_factory=list, description="当前用药")
    # allergies: List[str] = Field(default_factory=list, description="过敏史")
    # primary_symptoms: List[str] = Field(default_factory=list, description="主症")
    # secondary_symptoms: List[str] = Field(default_factory=list, description="次症")

    
    class Config:
        use_enum_values = True


class DiagnosisInfo(BaseModel):
    """诊断信息模型"""
    syndrome: SyndromeType = Field(..., description="证型")
    syndrome_description: str = Field(..., description="证型描述")
    pathogenesis: str = Field(..., description="病机分析")
    differential_diagnosis: List[str] = Field(default_factory=list, description="鉴别诊断")
    recommendation: str = Field(..., description="建议")
    
    class Config:
        use_enum_values = True


class TreatmentPlan(BaseModel):
    """治疗方案模型"""
    principle: str = Field(..., description="治疗原则")
    herbal_prescription: Optional[str] = Field(None, description="中药方剂")
    lifestyle_advice: List[str] = Field(default_factory=list, description="生活建议")
    diet_advice: List[str] = Field(default_factory=list, description="饮食建议")
    precautions: List[str] = Field(default_factory=list, description="注意事项")
    follow_up_advice: str = Field(..., description="复诊建议")

class MedicalHistory(BaseModel):
    """病史信息模型"""
    # 过敏史
    allergies: List[str] = Field(default_factory=list, description="药物/食物过敏史")
    allergy_severity: Optional[str] = Field(None, description="过敏严重程度")
    allergy_manifestation: Optional[str] = Field(None, description="过敏表现")
    
    # 家族史
    family_history: List[str] = Field(default_factory=list, description="家族病史")
    family_conditions: Optional[str] = Field(None, description="家族成员患病情况")
    
    # 婚育史
    marriage_history: Optional[str] = Field(None, description="婚姻状况")
    pregnancy_history: Optional[str] = Field(None, description="孕产史")
    menstrual_history: Optional[str] = Field(None, description="月经史（女性）")
    
    # 个人史
    personal_history: Optional[str] = Field(None, description="个人史")
    living_conditions: Optional[str] = Field(None, description="居住环境")
    dietary_habits: Optional[str] = Field(None, description="饮食习惯")
    smoking_history: Optional[str] = Field(None, description="吸烟史")
    alcohol_history: Optional[str] = Field(None, description="饮酒史")
    exercise_habits: Optional[str] = Field(None, description="运动习惯")
    
    # 既往史
    past_history: List[str] = Field(default_factory=list, description="既往病史")
    surgical_history: List[str] = Field(default_factory=list, description="手术史")
    transfusion_history: Optional[str] = Field(None, description="输血史")
    vaccination_history: Optional[str] = Field(None, description="预防接种史")
    
    # 当前用药
    current_medications: List[str] = Field(default_factory=list, description="当前用药")
    
    # 其他
    occupational_exposure: Optional[str] = Field(None, description="职业暴露")
    
class ConsultationRecord(BaseModel):
    """结构化病历模型"""
    # 就诊信息
    session_id: Optional[str] = Field(None, description="会话ID")
    visit_type: Optional[ConsultationVisitType] = Field(None, description="就诊类型")
    visit_date: datetime = Field(default_factory=datetime.now, description="就诊日期")
    
    # 基本信息
    patient_name: Optional[str] = Field(None, description="患者姓名")
    patient_age: Optional[int] = Field(None, description="年龄")
    patient_gender: Optional[str] = Field(None, description="性别")
    
    # 主诉
    chief_complaint: Optional[str] = Field(None, description="主诉")
    
    # 现病史
    current_illness: Optional[str] = Field(None, description="现病史")
    onset_time: Optional[str] = Field(None, description="发病时间")
    disease_duration: Optional[str] = Field(None, description="病程")
    chief_symptom: Optional[str] = Field(None, description="主要症状")
    symptom_evolution: Optional[str] = Field(None, description="症状演变")
    previous_treatment: Optional[str] = Field(None, description="既往治疗情况")
    
    # 病史
    medical_history: "MedicalHistory" = Field(default_factory=MedicalHistory, description="病史信息")
    
    # 症状列表
    symptoms: List[SymptomInfo] = Field(default_factory=list, description="症状列表")
    
    # 体格检查
    vital_signs: Optional[Dict[str, Any]] = Field(None, description="生命体征")
    general_exam: Optional[str] = Field(None, description="一般情况")
    physical_exam: Optional[PhysicalInfo] = Field(None, description="体格检查")
    
    # 舌脉信息
    tongue_description: Optional[str] = Field(None, description="舌象描述")
    tongue_image_url: Optional[str] = Field(None, description="舌面照片URL")
    tongue_image_analysis: Optional[str] = Field(None, description="舌面照片分析结果")
    pulse_description: Optional[str] = Field(None, description="脉象描述")
    
    # 辅助检查
    lab_results: Optional[str] = Field(None, description="实验室检查")
    imaging_results: Optional[str] = Field(None, description="影像学检查")
    exam_report_urls: List[str] = Field(default_factory=list, description="检查报告图片URLs")
    
    # 辨证论治
    diagnosis: Optional[str] = Field(None, description="西医诊断")
    syndrome_name: Optional[str] = Field(None, description="中医诊断") 
    syndrome: Optional[str] = Field(None, description="中医证型")
    syndrome_differentiation: Optional[str] = Field(None, description="辨证分析")
    pathogenesis: Optional[str] = Field(None, description="病机")
    
    # 治疗方案
    treatment_principle: Optional[str] = Field(None, description="治法")
    herbal_prescription: Optional[str] = Field(None, description="中药处方")
    prescription_analysis: Optional[str] = Field(None, description="方药分析")
    
    # 医嘱
    lifestyle_advice: List[str] = Field(default_factory=list, description="生活调摄建议")
    diet_advice: List[str] = Field(default_factory=list, description="饮食建议")
    precautions: List[str] = Field(default_factory=list, description="注意事项")
    follow_up_advice: Optional[str] = Field(None, description="复诊建议")
    
    # 补充信息
    supplementary_info: Optional[str] = Field(None, description="补充说明")
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")


class ConsultationState(BaseModel):
    """问诊状态模型 - 管理多轮问诊的会话状态"""
    session_id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S"))
    patient_info: PatientInfo = Field(default_factory=PatientInfo, description="患者基本信息")
    visit_type: Optional[ConsultationVisitType] = Field(None, description="就诊类型")
    chief_complaint: Optional[str] = Field(None, description="主诉")
    symptoms: List[SymptomInfo] = Field(default_factory=list)
    medical_history: Optional["MedicalHistory"] = Field(default=None, description="病史信息")
    physical_info: PhysicalInfo = Field(default_factory=PhysicalInfo)
    current_phase: ConsultationPhase = Field(ConsultationPhase.WELCOME)
    intention: Optional[str] = Field(None, description="当前意图")
    diagnosis: Optional[DiagnosisInfo] = None
    treatment_plan: Optional[TreatmentPlan] = None
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    collected_info: Dict[str, Any] = Field(default_factory=dict)
    is_complete: bool = Field(False)
    turn_count: int = Field(0, description="对话轮数")
    max_turns: int = Field(50, description="最大对话轮数")
    tongue_image_url: Optional[str] = Field(None, description="舌面照片URL")
    exam_report_url: Optional[str] = Field(None, description="检查报告URL")
    consultation_record: Optional[ConsultationRecord]= Field(default_factory=ConsultationRecord) 
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True


class IntentionResult(BaseModel):
    """意图识别结果模型"""
    category: IntentionCategory = Field(..., description="意图大类")
    intention: Optional[str] = Field(None, description="具体意图描述")
    confidence: float = Field(..., ge=0.0, le=1.0, description="分类置信度")
    entities: Dict[str, Any] = Field(default_factory=dict, description="提取的实体信息")
    follow_up_question: Optional[str] = Field(None, description="追问问题")
    suggested_response: Optional[str] = Field(None, description="建议回复")
    should_forward_to_consultation: bool = Field(False, description="是否需要进入问诊流程")
    hospital_referral: Optional[str] = Field(None, description="推荐就诊地址")
    
    class Config:
        use_enum_values = True


class KGQueryResult(BaseModel):
    """知识图谱查询结果模型"""
    entities: List[Dict[str, Any]] = Field(default_factory=list, description="实体列表")
    relations: List[Dict[str, Any]] = Field(default_factory=list, description="关系列表")
    context: str = Field(..., description="检索到的上下文")
    source: str = Field("knowledge_graph", description="来源")
    relevance_score: float = Field(0.0, description="相关度评分")


def get_enum_value(enum_or_str: Any) -> str:
    """安全获取枚举值，处理字符串或枚举对象
    
    Args:
        enum_or_str: 枚举对象或字符串
        
    Returns:
        str: 枚举的字符串值
    """
    if isinstance(enum_or_str, str):
        return enum_or_str
    if hasattr(enum_or_str, 'value'):
        return enum_or_str.value
    return str(enum_or_str)

