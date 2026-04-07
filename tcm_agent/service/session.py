from typing import Dict, List, Any, Optional, Tuple, AsyncIterator
import asyncio
import json
import uuid
from datetime import datetime
from tcm_agent.models import (
    CONSULTATION_SLOTS_DEFINITION,
    SlotCollectionStatus,SlotStatus,
    PatientInfo,
    ConsultationPhase
    )
from tcm_agent.constants import DoctorNameMapping
from log import logger


# TODO 改为redis进行存储
class SessionManager:
    """会话管理器 - 支持多路并发"""
    
    def __init__(self):
        # key: session_id, value: TCMConsultationSystem
        self._sessions: Dict[str, Any] = {}
        # 消息历史
        self._histories: Dict[str, List[Dict]] = {}
        # 会话元信息
        self._metadata: Dict[str, Dict] = {}
        # 异步锁，保护会话字典
        self._lock = asyncio.Lock()
    
    async def create_session(
        self, 
        doctor_id: int, 
        session_id: Optional[str] = None, 
        visit_type: str = "first_visit", 
        patient_data: PatientInfo=None
        ) -> Tuple[str, str]:
        """
        创建新会话
        """
        async with self._lock:
            # 生成会话ID
            if session_id not in self._sessions:
                session_id = str(uuid.uuid4())
            
            # 创建新的问诊系统实例
            from tcm_agent.service.consultation import TCMConsultationSystem, ConsultationVisitType
            
            tcmagent = TCMConsultationSystem(
                enable_stream=False,  # API模式关闭流式输出
                max_turns=50,
            )
            
            # 启动会话
            await tcmagent.start_session(session_id)

            # 初始化槽位状态
            state = tcmagent.current_session.state
            state.pending_slots = []
            for slot_def in CONSULTATION_SLOTS_DEFINITION:
                key = slot_def["key"]
                is_required = slot_def["required"]
                state.slot_status[key] = SlotCollectionStatus(
                    key=key,
                    status=SlotStatus.PENDING if is_required else SlotStatus.SKIPPED
                )
                if is_required:
                    state.pending_slots.append(key)
            
            state.current_slot_key = None
            
            # 进入问诊阶段
            state.consultation_phase = ConsultationPhase.CONSULTATION
            
            # 添加欢迎消息
            welcome = f"您好！我是{DoctorNameMapping[doctor_id]}的数字分身!"
            
            # 更新槽位信息，更新状态信息
            if visit_type == "follow_up_visit":
                welcome += "请问您本次复诊需要咨询什么内容呢？"
                state.patient_info = patient_data
                state.pending_slots = [s for s in state.pending_slots if s not in ["name", "gender", "age"]]
                state.collected_slots["name"] = patient_data.name
                state.collected_slots["gender"] = patient_data.gender
                state.collected_slots["age"] = patient_data.age
            else:
                welcome += " 我了解到您是初次就诊。为了更好地为您服务，能麻烦说一下您的性别和年龄么？"
                state.patient_info = PatientInfo()
            
            logger.debug(f"state.pending_slots: {state.pending_slots}")
            logger.debug(f"slot_status: {state.slot_status}")
            try:
                tcmagent.current_session.state.visit_type = ConsultationVisitType(visit_type)
            except ValueError:
                tcmagent.current_session.state.visit_type = ConsultationVisitType.FIRST_VISIT
            
            # 保存
            self._sessions[session_id] = tcmagent
            self._histories[session_id] = []
            self._metadata[session_id] = {
                "created_at": datetime.now().isoformat(),
                "status": "active",
                "phase": "WELCOME",
                "visit_type": visit_type
            }
           #TODO 这部分再将tcmagent.current_session.messages 写入redis 
            self._add_to_history(session_id, role="assistant", content=welcome)
            self._histories[session_id].append({
                "role": "assistant",
                "content": welcome,
                "timestamp": datetime.now().isoformat()
            })
            
            return session_id, welcome
    
    def _add_to_history(self, session_id: str, role: str, content: str) -> None:
        """添加对话历史"""
        self._sessions[session_id].current_session.messages.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    async def get_session(self, session_id: str) -> Optional[Any]:
        """获取会话"""
        async with self._lock:
            return self._sessions.get(session_id)
    
    async def chat(self, session_id: str, message: str, imgs=None) -> Tuple[str, Optional[str], bool]:
        """
        处理聊天消息

        Args:
            session_id: 会话ID
            message: 用户消息
            imgs: 可选的图片数据（ChatImages 或 dict）

        Returns:
            (response, phase, is_complete)
        """
        # 处理图片数据格式
        from tcm_agent.schema.consultation import ChatImages
        chat_images = None
        if imgs is not None:
            if isinstance(imgs, dict):
                chat_images = ChatImages(**imgs)
            else:
                chat_images = imgs
        async with self._lock:
            tcmagent = self._sessions.get(session_id)
            if not tcmagent:
                return "会话不存在，请创建新会话", None, False
            
            if tcmagent.current_session.status.value != "active":
                return "会话已结束，请创建新会话", None, True
        
        # 添加用户消息
        self._add_to_history(session_id, role="user", content=message)
        self._histories[session_id].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        
        # 调用问诊系统（同步执行）
        try:
            response = await tcmagent.chat(message, chat_images)
        except Exception as e:
            logger.error(f"Chat error: {e}")
            response = f"抱歉，处理您的消息时出现了问题：{str(e)}"
        
        # 添加助手回复
        self._add_to_history(session_id, role="assistant", content=response)
        self._histories[session_id].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat()
        })
        
        # 更新状态
        phase = None
        is_complete = False
        if tcmagent.current_session:
            phase = tcmagent.current_session.state.consultation_phase
            is_complete = tcmagent.current_session.state.is_complete
            self._metadata[session_id]["phase"] = phase
            if is_complete:
                self._metadata[session_id]["status"] = "completed"
        
        return response, phase, is_complete
    
    async def chat_stream(self, session_id: str, message: str, imgs=None):
        """
        处理聊天消息（流式返回）

        Args:
            session_id: 会话ID
            message: 用户消息
            imgs: 可选的图片数据

        Yields:
            SSE 格式的数据
        """
        from tcm_agent.schema.consultation import ChatImages
        chat_images = None
        if imgs is not None:
            if isinstance(imgs, dict):
                chat_images = ChatImages(**imgs)
            else:
                chat_images = imgs

        async with self._lock:
            tcmagent = self._sessions.get(session_id)
            if not tcmagent:
                yield self._sse_format("error", "text", "会话不存在，请创建新会话")
                return
            
            if tcmagent.current_session.status.value != "active":
                yield self._sse_format("error", "text", "会话已结束，请创建新会话")
                return

        # 添加用户消息到历史
        self._add_to_history(session_id, role="user", content=message)
        self._histories[session_id].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })

        # 发送开始事件
        yield self._sse_format("start", "text", "")

        # 调用流式处理
        try:
            full_response = ""
            async for chunk in tcmagent.chat_stream(message, chat_images):
                full_response += chunk
                logger.debug(f"chunk: {chunk}")
                yield self._sse_format("text", "text", chunk)

            # 添加助手回复到历史
            self._add_to_history(session_id, role="assistant", content=full_response)
            self._histories[session_id].append({
                "role": "assistant",
                "content": full_response,
                "timestamp": datetime.now().isoformat()
            })

            # 更新状态
            phase = None
            is_complete = False
            if tcmagent.current_session:
                phase = tcmagent.current_session.state.consultation_phase
                is_complete = tcmagent.current_session.state.is_complete
                self._metadata[session_id]["phase"] = phase
                if is_complete:
                    self._metadata[session_id]["status"] = "completed"

            # 发送完成事件
            yield self._sse_format("done", "text", "", phase=str(phase), is_complete=str(is_complete))

        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            yield self._sse_format("error", "text", f"处理消息时出现错误：{str(e)}")

    def _sse_format(self, event: str, msg_type: str, content: str, **extra) -> str:
        """生成 SSE 格式的数据"""
        data = {"event": event, "msg_type": msg_type, "content": content}
        data.update(extra)
        return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"

    async def get_history(self, session_id: str) -> List[Dict]:
        """获取聊天历史"""
        async with self._lock:
            return self._histories.get(session_id, [])
    
    async def get_session_info(self, session_id: str) -> Optional[Dict]:
        """获取会话信息"""
        async with self._lock:
            if session_id not in self._sessions:
                return None
            
            tcmagent = self._sessions[session_id]
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
            if session_id in self._metadata:
                del self._metadata[session_id]
            return True
    
    async def get_active_count(self) -> int:
        """获取活跃会话数"""
        async with self._lock:
            return len(self._sessions)


# 全局会话管理器
session_manager = SessionManager()
