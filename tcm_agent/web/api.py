# -*- coding: utf-8 -*-
"""
TCM Agent Web API - FastAPI Backend
中医问诊系统 Web API - 支持多路并发聊天

接口:
- POST /api/sessions - 创建会话
- POST /api/chat - 发送消息
- GET /api/sessions/{session_id} - 获取会话状态
- GET /api/sessions/{session_id}/history - 获取聊天历史
"""
import os
import uuid
import asyncio
import threading
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn

# 添加项目路径
import sys
sys_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

try:
    from log import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# ==================== 配置 ====================
HOST = os.getenv("API_HOST", "0.0.0.0")
PORT = int(os.getenv("API_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"


# ==================== 数据模型 ====================

class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    session_id: Optional[str] = None
    visit_type: Optional[str] = "first_visit"  # first_visit / follow_up_visit


class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: str
    message: str
    visit_type: Optional[str] = None  # 可在聊天时更新就诊类型


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


# ==================== 会话存储（线程安全）====================

class SessionManager:
    """会话管理器 - 支持多路并发"""
    
    def __init__(self):
        # 每个会话一个独立的 TCMConsultationSystem 实例
        # key: session_id, value: TCMConsultationSystem
        self._sessions: Dict[str, Any] = {}
        # 消息历史
        self._histories: Dict[str, List[Dict]] = {}
        # 会话元信息
        self._metadata: Dict[str, Dict] = {}
        # 异步锁，保护会话字典
        self._lock = asyncio.Lock()
    
    async def create_session(self, session_id: Optional[str] = None, visit_type: str = "first_visit") -> Tuple[str, str]:
        """
        创建新会话
        
        Args:
            session_id: 可选的会话ID
            visit_type: 就诊类型 (first_visit / follow_up_visit)
            
        Returns:
            (session_id, welcome_message)
        """
        async with self._lock:
            # 生成会话ID
            if session_id is None:
                session_id = str(uuid.uuid4())
            
            # 避免重复
            while session_id in self._sessions:
                session_id = str(uuid.uuid4())
            
            # 创建新的问诊系统实例
            from tcm_agent.system import TCMConsultationSystem, ConsultationVisitType
            
            system = TCMConsultationSystem(
                enable_stream=False,  # API模式关闭流式输出
                max_turns=50,
            )
            
            # 启动会话
            await system.start_session(session_id)
            
            # 直接设置就诊类型（不调用agent推断）
            try:
                system.current_session.state.visit_type = ConsultationVisitType(visit_type)
            except ValueError:
                system.current_session.state.visit_type = ConsultationVisitType.FIRST_VISIT
            
            # 保存
            self._sessions[session_id] = system
            self._histories[session_id] = []
            self._metadata[session_id] = {
                "created_at": datetime.now().isoformat(),
                "status": "active",
                "phase": "WELCOME",
                "visit_type": visit_type
            }
            
            # 添加欢迎消息
            welcome = "您好！欢迎来到中医智能问诊系统。我是您的中医健康助手，可以帮助您进行健康咨询和中医辨证。请问有什么可以帮助您的？"
            
            self._histories[session_id].append({
                "role": "assistant",
                "content": welcome,
                "timestamp": datetime.now().isoformat()
            })
            
            return session_id, welcome
    
    async def get_session(self, session_id: str) -> Optional[Any]:
        """获取会话"""
        async with self._lock:
            return self._sessions.get(session_id)
    
    async def chat(self, session_id: str, message: str) -> Tuple[str, Optional[str], bool]:
        """
        处理聊天消息
        
        Args:
            session_id: 会话ID
            message: 用户消息
            
        Returns:
            (response, phase, is_complete)
        """
        async with self._lock:
            system = self._sessions.get(session_id)
            if not system:
                return "会话不存在，请创建新会话", None, False
            
            if system.current_session.status.value != "active":
                return "会话已结束，请创建新会话", None, True
        
        # 添加用户消息
        self._histories[session_id].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        
        # 调用问诊系统（同步执行）
        try:
            response = await system.chat(message)
        except Exception as e:
            logger.error(f"Chat error: {e}")
            response = f"抱歉，处理您的消息时出现了问题：{str(e)}"
        
        # 添加助手回复
        self._histories[session_id].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat()
        })
        
        # 更新状态
        phase = None
        is_complete = False
        if system.current_session:
            phase = system.current_session.state.consultation_phase
            is_complete = system.current_session.state.is_complete
            self._metadata[session_id]["phase"] = phase
            if is_complete:
                self._metadata[session_id]["status"] = "completed"
        
        return response, phase, is_complete
    
    async def get_history(self, session_id: str) -> List[Dict]:
        """获取聊天历史"""
        async with self._lock:
            return self._histories.get(session_id, [])
    
    async def get_session_info(self, session_id: str) -> Optional[Dict]:
        """获取会话信息"""
        async with self._lock:
            if session_id not in self._sessions:
                return None
            
            system = self._sessions[session_id]
            metadata = self._metadata.get(session_id, {})
            
            return {
                "session_id": session_id,
                "status": metadata.get("status", "active"),
                "phase": metadata.get("phase", "UNKNOWN"),
                "created_at": metadata.get("created_at", ""),
                "message_count": len(self._histories.get(session_id, []))
            }
    
    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
            if session_id in self._histories:
                del self._histories[session_id]
            if session_id in self._metadata:
                del self._metadata[session_id]
            return True
    
    async def get_active_count(self) -> int:
        """获取活跃会话数"""
        async with self._lock:
            return len(self._sessions)


# 全局会话管理器
session_manager = SessionManager()


# ==================== FastAPI 应用 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info("中医问诊系统 API 启动")
    yield
    logger.info("中医问诊系统 API 关闭")


app = FastAPI(
    title="中医智能问诊系统 API",
    description="提供问诊会话管理、聊天接口",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== 静态文件服务 ====================

web_dir = os.path.dirname(os.path.abspath(__file__))
index_path = os.path.join(web_dir, "index.html")


@app.get("/", response_class=FileResponse)
async def root():
    """返回前端页面"""
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {"message": "前端页面未找到，请访问 /api/docs 查看 API 文档"}


# ==================== API 路由 ====================

@app.post("/api/sessions", response_model=Dict[str, Any])
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
    session_id, welcome = await session_manager.create_session(session_id, visit_type)
    
    return {
        "session_id": session_id,
        "welcome_message": welcome,
        "visit_type": visit_type,
        "status": "active"
    }


@app.get("/api/sessions/{session_id}", response_model=SessionInfo)
async def get_session_info(session_id: str):
    """获取会话信息"""
    info = await session_manager.get_session_info(session_id)
    if not info:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    return SessionInfo(**info)


@app.get("/api/sessions/{session_id}/history", response_model=List[Message])
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


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    发送聊天消息
    
    Request:
        - session_id: 会话ID
        - message: 用户消息
    
    Returns:
        - session_id: 会话ID
        - response: 助手回复
        - phase: 当前阶段
        - is_complete: 是否完成
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    
    response, phase, is_complete = await session_manager.chat(
        request.session_id,
        request.message
    )
    
    return ChatResponse(
        session_id=request.session_id,
        response=response,
        phase=phase,
        is_complete=is_complete,
        timestamp=datetime.now().isoformat()
    )


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除会话"""
    success = await session_manager.delete_session(session_id)
    if success:
        return {"message": "会话已删除", "session_id": session_id}
    raise HTTPException(status_code=404, detail="会话不存在")


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    active_count = await session_manager.get_active_count()
    return HealthResponse(
        status="ok",
        active_sessions=active_count,
        timestamp=datetime.now().isoformat()
    )


# ==================== 启动 ====================

def main():
    """启动服务器"""
    print("=" * 60)
    print("中医智能问诊系统 Web API")
    print("=" * 60)
    print(f"API 地址: http://{HOST}:{PORT}")
    print(f"前端页面: http://{HOST}:{PORT}/")
    print(f"API 文档: http://{HOST}:{PORT}/docs")
    print("=" * 60)
    
    uvicorn.run(
        "tcm_agent.web.api:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info"
    )


if __name__ == "__main__":
    main()