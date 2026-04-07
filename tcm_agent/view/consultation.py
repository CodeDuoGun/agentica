import re
import traceback
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from tcm_agent.utils.response import general_response
from log import logger
from typing import Dict, Any, List, AsyncIterator
from tcm_agent.schema.consultation import CreateSessionRequest, HealthResponse, SessionInfo, ChatRequest, ChatResponse, Message
from fastapi import FastAPI, HTTPException
from tcm_agent.service.session import session_manager
router = APIRouter()


@router.post("/sessions", response_model=Dict[str, Any])
async def create_session(request: CreateSessionRequest = None):
    """
    创建新会话
    
    Request:
        - session_id: 可选的会话ID
        - visit_type: 就诊类型 (first_visit / follow_up_visit)
    
    Returns:
        - session_id: 会话ID
        - welcome_message: 欢迎消息
    """
    session_id = request.session_id if request else None
    visit_type = request.visit_type if request else "first_visit"
    session_id, welcome = await session_manager.create_session(request.doctor_id, session_id, visit_type, request.patient_data)
    
    return {
        "session_id": session_id,
        "welcome_message": welcome,
        "visit_type": visit_type,
        "status": "active"
    }


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
