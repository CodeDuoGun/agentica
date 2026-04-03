from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel
from tcm_agent.models import PatientInfo

class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    session_id: Optional[str] = None
    visit_type: Optional[str] = "first_visit"  # first_visit / follow_up_visit
    doctor_id: int
    patient_data: PatientInfo

class ChatImages(BaseModel):
    tongue_imgs: List[str] = []
    face_imgs: List[str] = []
    check_imgs: List[str] = []

class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: str
    message: str
    visit_type: Optional[str] = None  # 可在聊天时更新就诊类型
    imgs: ChatImages


class Message(BaseModel):
    """消息模型"""
    role: str  # "user" or "assistant"
    content: str
    timestamp: str


class SessionInfo(BaseModel):
    """会话信息"""
    session_id: str
    status: str
    phase: str
    created_at: str
    message_count: int


class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str
    response: str
    phase: Optional[str] = None
    is_complete: bool = False
    timestamp: str = ""


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    active_sessions: int
    timestamp: str