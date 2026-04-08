from datetime import datetime
from typing import Dict, Any, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from tcm_agent.schema.consultation import CreateSessionRequest, HealthResponse, SessionInfo, ChatRequest, Message, UserSessionResponse
from tcm_agent.service.session import session_manager
router = APIRouter()


@router.post("/sessions", response_model=Dict[str, Any])
async def create_session(request: CreateSessionRequest = None):
    """
    创建新会话
    """
    user_id = request.user_id if request else None
    session_id = request.session_id if request else None
    visit_type = request.visit_type if request else "first_visit"
    doctor_id = request.doctor_id if request else 1
    patient_data = request.patient_data if request else None

    session_id, welcome = await session_manager.create_session(
        doctor_id=doctor_id,
        user_id=user_id,
        session_id=session_id,
        visit_type=visit_type,
        patient_data=patient_data,
    )
    
    return {
        "user_id": user_id or "",
        "session_id": session_id,
        "welcome_message": welcome,
        "visit_type": visit_type,
        "status": "active"
    }


@router.get("/users/{user_id}/session", response_model=UserSessionResponse)
async def get_user_session(user_id: str):
    """获取用户最近会话及聊天历史"""
    result = await session_manager.get_user_session(user_id)
    if not result:
        return UserSessionResponse(user_id=user_id, session=None, history=[])

    session_info = SessionInfo(**result["session"])
    history = [
        Message(
            role=msg["role"],
            content=msg["content"],
            timestamp=msg["timestamp"]
        )
        for msg in result["history"]
    ]
    return UserSessionResponse(user_id=user_id, session=session_info, history=history)


@router.get("/sessions/{session_id}", response_model=SessionInfo)
async def get_session_info(session_id: str):
    """获取会话信息"""
    info = await session_manager.get_session_info(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return SessionInfo(**info)


@router.get("/sessions/{session_id}/history", response_model=List[Message])
async def get_chat_history(session_id: str):
    """获取聊天历史"""
    history = await session_manager.get_history(session_id)
    return [
        Message(
            role=msg["role"],
            content=msg["content"],
            timestamp=msg["timestamp"]
        )
        for msg in history
    ]


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    发送聊天消息（SSE 流式返回）
    
    Request:
        - session_id: 会话ID
        - message: 用户消息
    
    Returns:
        SSE 流，包含 event, msg_type, content 字段
        msg_type: text, img, object
        event: start, text, done, error
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    
    return StreamingResponse(
        session_manager.chat_stream(
            request.session_id,
            request.message,
            request.imgs
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    success = await session_manager.delete_session(session_id)
    if success:
        return {"message": "会话已删除", "session_id": session_id}
    raise HTTPException(status_code=404, detail="会话不存在")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    active_count = await session_manager.get_active_count()
    return HealthResponse(
        status="ok",
        active_sessions=active_count,
        timestamp=datetime.now().isoformat()
    )


@router.get("/patients", response_model=Dict[str, Any])
async def get_patients():
    """获取就诊人列表"""
    patients = [
        {"id": 1, "name": "张三", "gender": "男", "age": 35, "phone": "138****1234"},
        {"id": 2, "name": "李四", "gender": "女", "age": 28, "phone": "139****5678"},
        {"id": 3, "name": "王五", "gender": "男", "age": 45, "phone": "137****9012"}
    ]
    return {"patients": patients}
