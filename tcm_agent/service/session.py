from typing import Dict, List, Any, Optional, Tuple
import asyncio
import json
import uuid
from datetime import datetime
from tcm_agent.models import (
    CONSULTATION_SLOTS_DEFINITION,
    SlotCollectionStatus, SlotStatus,
    PatientInfo,
    ConsultationPhase,
)
from tcm_agent.constants import DoctorNameMapping
from tcm_agent.utils.redis_db import redis_tool
from log import logger


class SessionManager:
    """会话管理器 - 支持多路并发"""

    SESSION_TTL = 7 * 24 * 60 * 60
    SESSION_IDS_KEY = "tcm:session:ids"

    def __init__(self):
        # key: session_id, value: TCMConsultationSystem
        self._sessions: Dict[str, Any] = {}
        # 异步锁，保护会话字典
        self._lock = asyncio.Lock()

    def _history_key(self, session_id: str) -> str:
        return f"tcm:session:{session_id}:history"

    def _metadata_key(self, session_id: str) -> str:
        return f"tcm:session:{session_id}:metadata"

    def _touch_session_keys(self, session_id: str) -> None:
        redis_tool.expire(self._history_key(session_id), self.SESSION_TTL)
        redis_tool.expire(self._metadata_key(session_id), self.SESSION_TTL)
        redis_tool.expire(self.SESSION_IDS_KEY, self.SESSION_TTL)

    def _save_metadata(self, session_id: str, metadata: Dict[str, Any]) -> None:
        metadata_key = self._metadata_key(session_id)
        for key, value in metadata.items():
            if value is None:
                value = ""
            redis_tool.hset(metadata_key, key, str(value))
        redis_tool.sadd(self.SESSION_IDS_KEY, session_id)
        self._touch_session_keys(session_id)

    def _get_metadata(self, session_id: str) -> Dict[str, str]:
        metadata = redis_tool.hgetall(self._metadata_key(session_id))
        return metadata or {}

    def _append_history(self, session_id: str, role: str, content: str) -> Dict[str, str]:
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        redis_tool.rpush(self._history_key(session_id), json.dumps(message, ensure_ascii=False))
        redis_tool.sadd(self.SESSION_IDS_KEY, session_id)
        self._touch_session_keys(session_id)
        return message

    def _load_history(self, session_id: str) -> List[Dict[str, Any]]:
        history = redis_tool.lrange(self._history_key(session_id), 0, -1)
        return [json.loads(item) for item in history] if history else []

    def _sync_agent_messages_from_redis(self, session_id: str) -> None:
        tcmagent = self._sessions.get(session_id)
        if not tcmagent or not tcmagent.current_session:
            return
        tcmagent.current_session.messages = self._load_history(session_id)

    async def create_session(
        self,
        doctor_id: int,
        session_id: Optional[str] = None,
        visit_type: str = "first_visit",
        patient_data: PatientInfo = None,
    ) -> Tuple[str, str]:
        """
        创建新会话
        """
        async with self._lock:
            if session_id and (session_id in self._sessions or redis_tool.exist(self._metadata_key(session_id))):
                session_id = str(uuid.uuid4())
            elif session_id is None:
                session_id = str(uuid.uuid4())

            from tcm_agent.service.consultation import TCMConsultationSystem, ConsultationVisitType

            tcmagent = TCMConsultationSystem(
                max_turns=50,
            )

            await tcmagent.start_session(session_id)

            state = tcmagent.current_session.state
            state.pending_slots = []
            for slot_def in CONSULTATION_SLOTS_DEFINITION:
                key = slot_def["key"]
                is_required = slot_def["required"]
                state.slot_status[key] = SlotCollectionStatus(
                    key=key,
                    status=SlotStatus.PENDING if is_required else SlotStatus.SKIPPED,
                )
                if is_required:
                    state.pending_slots.append(key)

            state.current_slot_key = None
            state.consultation_phase = ConsultationPhase.CONSULTATION

            welcome = f"您好！我是{DoctorNameMapping[doctor_id]}的数字医生!"

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

            self._sessions[session_id] = tcmagent

            metadata = {
                "created_at": datetime.now().isoformat(),
                "status": "active",
                "phase": ConsultationPhase.WELCOME.value,
                "visit_type": visit_type,
            }
            self._save_metadata(session_id, metadata)

            self._append_history(session_id, role="assistant", content=welcome)
            self._sync_agent_messages_from_redis(session_id)

            return session_id, welcome

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

            self._append_history(session_id, role="user", content=message)
            self._sync_agent_messages_from_redis(session_id)

        try:
            response = await tcmagent.chat(message, chat_images)
        except Exception as e:
            logger.error(f"Chat error: {e}")
            response = f"抱歉，处理您的消息时出现了问题：{str(e)}"

        async with self._lock:
            self._append_history(session_id, role="assistant", content=response)
            self._sync_agent_messages_from_redis(session_id)

            phase = None
            is_complete = False
            if tcmagent.current_session:
                phase = tcmagent.current_session.state.consultation_phase
                is_complete = tcmagent.current_session.state.is_complete
                metadata = self._get_metadata(session_id)
                metadata["phase"] = phase.value if phase is not None else ""
                if is_complete:
                    metadata["status"] = "completed"
                self._save_metadata(session_id, metadata)

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

            self._append_history(session_id, role="user", content=message)
            self._sync_agent_messages_from_redis(session_id)

        yield self._sse_format("start", "text", "")

        try:
            full_response = ""
            async for chunk in tcmagent.chat_stream(message, chat_images):
                full_response += chunk
                logger.debug(f"chunk: {chunk}")
                yield self._sse_format("text", "text", chunk)

            async with self._lock:
                self._append_history(session_id, role="assistant", content=full_response)
                self._sync_agent_messages_from_redis(session_id)

                phase = None
                is_complete = False
                if tcmagent.current_session:
                    phase = tcmagent.current_session.state.consultation_phase
                    is_complete = tcmagent.current_session.state.is_complete
                    metadata = self._get_metadata(session_id)
                    metadata["phase"] = phase.value if phase is not None else ""
                    if is_complete:
                        metadata["status"] = "completed"
                    self._save_metadata(session_id, metadata)

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
            return self._load_history(session_id)

    async def get_session_info(self, session_id: str) -> Optional[Dict]:
        """获取会话信息"""
        async with self._lock:
            metadata = self._get_metadata(session_id)
            if not metadata:
                return None

            history = self._load_history(session_id)
            return {
                "session_id": session_id,
                "status": metadata.get("status", "active"),
                "phase": metadata.get("phase", "UNKNOWN"),
                "created_at": metadata.get("created_at", ""),
                "message_count": len(history),
            }

    async def update_session(self, session_id: str, **updates: Any) -> Optional[Dict]:
        """更新会话元信息"""
        async with self._lock:
            metadata = self._get_metadata(session_id)
            if not metadata:
                return None

            for key, value in updates.items():
                if value is not None:
                    metadata[key] = str(value)
            self._save_metadata(session_id, metadata)

            history = self._load_history(session_id)
            return {
                "session_id": session_id,
                "status": metadata.get("status", "active"),
                "phase": metadata.get("phase", "UNKNOWN"),
                "created_at": metadata.get("created_at", ""),
                "message_count": len(history),
            }

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        async with self._lock:
            existed = bool(self._sessions.pop(session_id, None))
            metadata_exists = bool(redis_tool.exist(self._metadata_key(session_id)))
            history_exists = bool(redis_tool.exist(self._history_key(session_id)))

            redis_tool.delete(self._metadata_key(session_id), self._history_key(session_id))
            redis_tool.srem(self.SESSION_IDS_KEY, session_id)

            return existed or metadata_exists or history_exists

    async def get_active_count(self) -> int:
        """获取活跃会话数"""
        async with self._lock:
            return redis_tool.scard(self.SESSION_IDS_KEY)


session_manager = SessionManager()
