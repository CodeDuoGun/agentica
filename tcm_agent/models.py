# -*- coding: utf-8 -*-
"""
TCM Agent Data Models
中医问诊系统的数据模型定义
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class IntentionType(str, Enum):
    """用户意图类型枚举"""
    GREETING = "greeting"                    # 问候
    SYMPTOM_DESCRIPTION = "symptom"         # 描述症状
    SYMPTOM_INQUIRY = "inquiry"            # 询问症状
    DIAGNOSIS_REQUEST = "diagnosis"        # 请求诊断
    TREATMENT_INQUIRY = "treatment"        # 询问治疗方案
    MEDICINE_INQUIRY = "medicine"          # 询问药物
    PREVENTION_INQUIRY = "prevention"      # 询问预防
    LIFE_ADVICE = "advice"                # 询问养生建议
    FOLLOW_UP = "follow_up"                # 随访/继续对话
    GOODBYE = "goodbye"                    # 结束对话
    OTHER = "other"                        # 其他意图


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
    WELCOME = "welcome"               # 欢迎/问候
    BASIC_INFO = "basic_info"        # 收集基本信息
    SYMPTOM_INQUIRY = "symptom"      # 症状询问
    TONGUE_PULSE = "tongue_pulse"    # 舌脉诊查
    DIFFERENTIAL = "differential"      # 辨证分析
    TREATMENT_PLAN = "treatment"     # 治疗方案
    FOLLOW_UP = "follow_up"          # 随访指导
    CONCLUSION = "conclusion"        # 结束问诊


class Gender(str, Enum):
    """性别"""
    MALE = "male"
    FEMALE = "female"
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
    occupation: Optional[str] = Field(None, description="职业")
    constitution: Optional[str] = Field(None, description="体质")
    medical_history: List[str] = Field(default_factory=list, description="既往病史")
    family_history: List[str] = Field(default_factory=list, description="家族病史")
    current_medications: List[str] = Field(default_factory=list, description="当前用药")
    allergies: List[str] = Field(default_factory=list, description="过敏史")
    
    class Config:
        use_enum_values = True


class DiagnosisInfo(BaseModel):
    """诊断信息模型"""
    syndrome: SyndromeType = Field(..., description="证型")
    syndrome_description: str = Field(..., description="证型描述")
    pathogenesis: str = Field(..., description="病机分析")
    primary_symptoms: List[str] = Field(default_factory=list, description="主症")
    secondary_symptoms: List[str] = Field(default_factory=list, description="次症")
    differential_diagnosis: List[str] = Field(default_factory=list, description="鉴别诊断")
    recommendation: str = Field(..., description="建议")
    
    class Config:
        use_enum_values = True


class TreatmentPlan(BaseModel):
    """治疗方案模型"""
    principle: str = Field(..., description="治疗原则")
    herbal_prescription: Optional[str] = Field(None, description="中药方剂")
    acupuncture_points: List[str] = Field(default_factory=list, description="针灸穴位")
    lifestyle_advice: List[str] = Field(default_factory=list, description="生活建议")
    diet_advice: List[str] = Field(default_factory=list, description="饮食建议")
    precautions: List[str] = Field(default_factory=list, description="注意事项")
    follow_up_advice: str = Field(..., description="复诊建议")


class ConsultationState(BaseModel):
    """问诊状态模型 - 管理多轮问诊的会话状态"""
    session_id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d%H%M%S"))
    patient_info: PatientInfo = Field(default_factory=PatientInfo)
    symptoms: List[SymptomInfo] = Field(default_factory=list)
    physical_info: PhysicalInfo = Field(default_factory=PhysicalInfo)
    current_phase: ConsultationPhase = Field(ConsultationPhase.WELCOME)
    intention: IntentionType = Field(IntentionType.OTHER)
    diagnosis: Optional[DiagnosisInfo] = None
    treatment_plan: Optional[TreatmentPlan] = None
    conversation_history: List[Dict[str, Any]] = Field(default_factory=list)
    collected_info: Dict[str, Any] = Field(default_factory=dict)
    is_complete: bool = Field(False)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        use_enum_values = True


class IntentionResult(BaseModel):
    """意图识别结果模型"""
    intention: IntentionType = Field(..., description="识别的意图类型")
    confidence: float = Field(..., ge=0.0, le=1.0, description="置信度")
    entities: Dict[str, Any] = Field(default_factory=dict, description="提取的实体信息")
    follow_up_question: Optional[str] = Field(None, description="追问问题")
    suggested_response: Optional[str] = Field(None, description="建议回复")
    
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
