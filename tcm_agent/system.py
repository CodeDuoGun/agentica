# -*- coding: utf-8 -*-
"""
TCM Consultation System - 主协调系统
中医问诊系统主入口

功能：
1. 统一入口，整合所有组件
2. 意图路由（普通咨询/问诊咨询/非医疗咨询）
3. 多轮问诊流程管理
4. 结构化病历生成
5. 会话管理
"""
import asyncio
from typing import Dict, Any, Optional, List, AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from agentica import Agent, QwenChat

from tcm_agent.agent import TCMDiagnosisAgent
from tcm_agent.knowledge import TCMKnowledgeBase
from tcm_agent.intention import IntentionRecognitionAgent, VisitTypeRecognitionAgent
from tcm_agent.models import (
    ConsultationState,
    ConsultationPhase,
    IntentionCategory,
    IntentionResult,
    ConsultationRecord,
    MedicalHistory,
    get_enum_value,
)
from log import logger


class SessionStatus(Enum):
    """会话状态"""
    ACTIVE = "active"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    ERROR = "error"
    INTERRUPTED = "interrupted"


class ConsultationInterruptReason(Enum):
    """中断原因"""
    MAX_TURNS_EXCEEDED = "max_turns_exceeded"
    PATIENT_QUIT = "patient_quit"
    ABNORMAL_ERROR = "abnormal_error"
    PHASE_COMPLETE = "phase_complete"


@dataclass
class ConsultationSession:
    """问诊会话"""
    session_id: str
    state: ConsultationState = field(default_factory=ConsultationState)
    status: SessionStatus = SessionStatus.ACTIVE
    interrupt_reason: Optional[ConsultationInterruptReason] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TCMConsultationSystem:
    """
    中医问诊系统主类
    
    统一管理问诊流程，整合：
    - 意图识别和路由
    - 问诊流程管理
    - 结构化病历生成
    - 中断场景处理
    
    支持：
    - 同步/异步调用
    - 流式输出
    - 会话管理
    """
    
    # 挂号推荐地址
    HOSPITAL_REFERRAL = "线上中医问诊"
    
    # 结束话术模板
    ENDING_MESSAGES = {
        ConsultationInterruptReason.MAX_TURNS_EXCEEDED: 
            "本次问诊已达到最大对话轮次（{max_turns}轮），建议您整理问题后重新开始咨询。如需紧急就医，请前往线下医院就诊。",
        ConsultationInterruptReason.PATIENT_QUIT: 
            "感谢您的咨询，祝您身体健康！如果有任何问题，欢迎随时来问诊。",
        ConsultationInterruptReason.ABNORMAL_ERROR: 
            "抱歉，系统遇到了问题，请您稍后重新开始问诊。如有紧急情况，请前往线下医院就诊。",
        ConsultationInterruptReason.PHASE_COMPLETE: 
            "问诊已完成，您可以根据上述建议进行调理。如有需要，请保存本次问诊记录。如有其他问题，欢迎随时咨询。",
    }
    
    def __init__(
        self,
        model: Any = None,
        knowledge_base: Optional[TCMKnowledgeBase] = None,
        enable_stream: bool = True,
        max_turns: int = 50,
        max_consultation_turns: int = 30,
    ):
        """
        初始化问诊系统
        
        Args:
            model: LLM 模型
            knowledge_base: 知识库
            enable_stream: 启用流式输出
            max_turns: 最大对话轮次（包含非问诊轮次）
            max_consultation_turns: 最大问诊轮次
        """
        # 为不同组件创建独立的 model 实例，避免 response_format 冲突
        self.model = model or QwenChat(id="qwen-plus")
        self.intention_model = QwenChat(id="qwen-plus")
        self.consultation_model = QwenChat(id="qwen-plus")
        
        self.knowledge_base = knowledge_base or TCMKnowledgeBase()
        self.knowledge_base.initialize()
        
        self.diagnosis_agent = TCMDiagnosisAgent(
            model=self.consultation_model,
            knowledge_base=self.knowledge_base,
            enable_stream=enable_stream,
        )
        
        self.intention_agent = IntentionRecognitionAgent(model=self.intention_model)
        self.visit_type_agent = VisitTypeRecognitionAgent(model=self.consultation_model)
        
        self.enable_stream = enable_stream
        self.max_turns = max_turns
        self.max_consultation_turns = max_consultation_turns
        
        self.current_session: Optional[ConsultationSession] = None
        self.sessions: Dict[str, ConsultationSession] = {}
        
        self._on_record_generated: Optional[Callable] = None
    
    def set_record_callback(self, callback: Callable[[ConsultationRecord], None]):
        """设置病历生成完成后的回调"""
        self._on_record_generated = callback
    
    async def start_session(self, session_id: Optional[str] = None) -> str:
        """开始新会话"""
        if session_id is None:
            session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        
        self.diagnosis_agent.reset()
        
        self.current_session = ConsultationSession(
            session_id=session_id,
            state=self.diagnosis_agent.get_state(),
        )
        self.current_session.state.max_turns = self.max_consultation_turns
        self.sessions[session_id] = self.current_session
        
        logger.info(f"Session started: {session_id}")
        return session_id
    
    async def chat(self, message: str) -> str:
        """
        处理单条消息
        
        Args:
            message: 用户消息
            
        Returns:
            str: 响应内容
        """
        if not self.current_session:
            await self.start_session()
        
        if self.current_session.status != SessionStatus.ACTIVE:
            await self.start_session()
        
        # 检查轮数限制
        if self.current_session.state.turn_count >= self.max_turns:
            return await self._handle_interrupt(
                ConsultationInterruptReason.MAX_TURNS_EXCEEDED
            )
        
        self.current_session.state.turn_count += 1
        
        # 添加用户消息
        self.current_session.messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })
        
        try:
            # 意图识别
            intention_result = await self.intention_agent.recognize(
                message,
                self._get_intention_context()
            )
            
            logger.info(f"Intention recognized: {intention_result}")
            
            # 根据意图类别路由
            response = await self._route_by_intention(intention_result, message)
            
        except Exception as e:
            logger.error(f"Error in chat: {e}")
            return await self._handle_interrupt(
                ConsultationInterruptReason.ABNORMAL_ERROR,
                error=str(e)
            )
        
        # 添加助手消息
        self.current_session.messages.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat(),
        })
        
        self.current_session.state = self.diagnosis_agent.get_state()
        self.current_session.updated_at = datetime.now()
        
        return response
    
    async def _route_by_intention(
        self, 
        intention: IntentionResult, 
        message: str
    ) -> str:
        """根据意图类别路由"""
        category = get_enum_value(intention.category)
        
        if category == "non_medical":
            return self._get_non_medical_response()
        
        elif category == "general_medical":
            return await self._handle_general_medical(intention, message)
        
        elif category == "consultation":
            return await self._handle_consultation(intention, message)
        
        else:
            return "抱歉，我无法理解您的问题，请重新描述。"
    
    def _get_non_medical_response(self) -> str:
        """非医疗咨询不回复"""
        return "问点医疗的"  # 返回空字符串，不进行回复
    
    async def _handle_general_medical(
        self, 
        intention: IntentionResult, 
        message: str
    ) -> str:
        """处理普通医疗问题咨询"""
        # 查询知识库获取相关信息
        #TODO 修改为graphrag  mixquery
        kb_results = self.knowledge_base.search_similar(message, max_results=3)
        
        # 构建回复
        response_parts = []
        
        if intention.suggested_response:
            response_parts.append(intention.suggested_response)
        
        # 添加知识库相关信息
        if kb_results:
            response_parts.append("\n\n以下是相关参考信息：")
            for i, result in enumerate[Dict[str, Any]](kb_results[:2], 1):
                response_parts.append(f"\n{i}. {result.get('content', '')[:200]}")
        
        # 主动推荐挂号
        response_parts.append(
            f"\n\n如需进一步诊疗，建议您前往【{self.HOSPITAL_REFERRAL}】进行详细咨询。"
        )
        
        return "".join(response_parts)
    
    async def _handle_consultation(
        self, 
        intention: IntentionResult, 
        message: str
    ) -> str:
        """处理问诊咨询"""
        current_phase = get_enum_value(self.current_session.state.current_phase)
        
        # 根据阶段处理
        if current_phase == "welcome":
            return await self._handle_welcome_phase(message, intention)
        elif current_phase == "basic_info":
            return await self._handle_basic_info_phase(message)
        elif current_phase == "chief_complaint":
            return await self._handle_chief_complaint_phase(message, intention)
        elif current_phase == "medical_history":
            return await self._handle_medical_history_phase(message, intention)
        elif current_phase == "attachments":
            return await self._handle_attachments_phase(message)
        elif current_phase == "supplementary":
            return await self._handle_supplementary_phase(message)
        elif current_phase == "complete":
            return await self._handle_consultation_complete()
        else:
            return await self.diagnosis_agent.run(message)
    
    async def _handle_welcome_phase(self, message: str, intention: IntentionResult) -> str:
        """处理欢迎阶段"""
        # 识别就诊类型
        try:
            visit_type = await self.visit_type_agent.recognize(message)
            self.current_session.state.visit_type = visit_type
        except Exception:
            # 默认初诊
            pass
        
        # 更新阶段
        self.current_session.state.current_phase = ConsultationPhase.BASIC_INFO
        
        visit_type_text = "复诊" if self.current_session.state.visit_type == "follow_up_visit" else "初诊"
        
        welcome_message = f"您好！欢迎来到中医智能问诊系统。"
        
        if visit_type_text == "复诊":
            welcome_message += " 好的，我了解到您是复诊患者。请问您这次有什么需要咨询的呢？"
        else:
            welcome_message += " 我了解到您是初次就诊。为了更好地为您服务，我需要了解一些基本信息。"
        
        return welcome_message
    
    async def _handle_basic_info_phase(self, message: str) -> str:
        """处理基本信息收集阶段"""
        # 提取基本信息
        patient_info = await self.diagnosis_agent.patient_info_extractor.extract(
            message,
            self.current_session.state.patient_info
        )
        self.current_session.state.patient_info = patient_info
        
        # 检查是否收集完成
        info_complete = (
            patient_info.age is not None or
            patient_info.name is not None
        )
        
        if info_complete:
            self.current_session.state.current_phase = ConsultationPhase.CHIEF_COMPLAINT
            return f"好的，已记录您的基础信息。接下来请描述一下您的主要不适症状（主诉）。"
        
        return "请告诉我您的年龄和性别，以便我更好地为您诊断。"
    
    async def _handle_chief_complaint_phase(
        self, 
        message: str, 
        intention: IntentionResult
    ) -> str:
        """处理主诉阶段"""
        # 提取症状
        symptoms_raw = await self.diagnosis_agent.symptom_extractor.extract(message)
        symptoms = self.diagnosis_agent._normalize_symptoms(symptoms_raw)
        
        for symptom in symptoms:
            if symptom.name not in [s.name for s in self.current_session.state.symptoms]:
                self.current_session.state.symptoms.append(symptom)
        
        # 更新主诉
        if intention.entities.get("symptom"):
            self.current_session.state.chief_complaint = ", ".join(intention.entities["symptom"])
        
        # 检查轮数限制
        consultation_turns = self._count_consultation_turns()
        if consultation_turns >= self.max_consultation_turns:
            return await self._handle_interrupt(ConsultationInterruptReason.MAX_TURNS_EXCEEDED)
        
        # 如果症状已收集，询问病史
        if len(self.current_session.state.symptoms) >= 1:
            self.current_session.state.current_phase = ConsultationPhase.MEDICAL_HISTORY
            return await self._generate_medical_history_prompt()
        
        # 继续收集症状
        follow_up = intention.follow_up_question or "还有其他不舒服的地方吗？"
        return follow_up
    
    async def _handle_medical_history_phase(
        self, 
        message: str, 
        intention: IntentionResult
    ) -> str:
        """处理病史收集阶段"""
        # 提取病史信息
        history_info = self._extract_medical_history(message)
        
        if history_info:
            # 更新病史
            medical_history = self.current_session.state.medical_history
            for key, value in history_info.items():
                if hasattr(medical_history, key):
                    current_value = getattr(medical_history, key)
                    if isinstance(current_value, list) and value not in current_value:
                        current_value.append(value)
                    elif current_value is None:
                        setattr(medical_history, key, value)
        
        # 询问是否需要上传附件
        self.current_session.state.current_phase = ConsultationPhase.ATTACHMENTS
        return (
            "好的，已记录相关信息。\n\n请问您是否有以下资料需要上传？\n"
            "1. 检查报告/化验单\n"
            "2. 舌面照片\n"
            "如有，请直接发送图片；如没有，请回复'无'继续。"
        )
    
    async def _handle_attachments_phase(self, message: str) -> str:
        """处理附件上传阶段"""
        msg_lower = message.lower()
        
        if msg_lower in ["无", "没有", "没有图片", "不用上传"]:
            self.current_session.state.current_phase = ConsultationPhase.SUPPLEMENTARY
            return "好的。接下来请问您还有没有其他需要补充说明的情况？如没有，请回复'没有'。"
        
        # 检查是否是图片（这里简化处理，实际需要检查 message type）
        if message.startswith("data:image") or message.endswith((".jpg", ".jpeg", ".png", ".webp")):
            # 模拟图片处理
            if "tongue" in msg_lower or "舌" in message:
                self.current_session.state.tongue_image_url = message
                self.current_session.state.physical_info.tongue_type = "待分析"
                return "好的，已收到舌面照片，正在分析中..."
            else:
                self.current_session.state.exam_report_url = message
                return "好的，已收到检查报告。"
        
        # 继续询问
        self.current_session.state.current_phase = ConsultationPhase.SUPPLEMENTARY
        return "请问还有其他需要补充说明的情况吗？如没有，请回复'没有'。"
    
    async def _handle_supplementary_phase(self, message: str) -> str:
        """处理补充信息阶段"""
        msg_lower = message.lower()
        
        if msg_lower in ["没有", "无", "不用", "没了"]:
            # 进入诊断阶段
            return await self._generate_diagnosis_and_record()
        
        # 记录补充信息
        self.current_session.state.consultation_record = ConsultationRecord(
            supplementary_info=message
        )
        
        return await self._generate_diagnosis_and_record()
    
    async def _generate_diagnosis_and_record(self) -> str:
        """生成诊断和结构化病历"""
        self.current_session.state.current_phase = ConsultationPhase.COMPLETE
        
        # 生成诊断
        diagnosis_response = await self.diagnosis_agent._generate_diagnosis_response()
        
        # 异步生成结构化病历
        asyncio.create_task(self._generate_consultation_record())
        
        return diagnosis_response
    
    async def _generate_consultation_record(self) -> ConsultationRecord:
        """生成结构化病历"""
        state = self.current_session.state
        patient_info = state.patient_info
        
        # 初始化 medical_history 如果为 None
        medical_history = state.medical_history
        if medical_history is None:
            medical_history = MedicalHistory()
        
        record = ConsultationRecord(
            # 会话信息
            session_id=self.current_session.session_id,
            visit_type=state.visit_type,
            visit_date=datetime.now(),
            
            # 基本信息
            patient_name=patient_info.name,
            patient_age=patient_info.age,
            patient_gender=get_enum_value(patient_info.gender) if patient_info.gender else None,
            
            # 主诉
            chief_complaint=state.chief_complaint,
            
            # 病史
            medical_history=medical_history,
            
            # 症状列表
            symptoms=state.symptoms,
            
            # 体格检查
            physical_exam=state.physical_info,
            
            # 舌脉信息
            tongue_image_url=state.tongue_image_url,
            tongue_image_analysis=state.tongue_image_url,  # 待分析
            pulse_description=get_enum_value(state.physical_info.pulse_type[0]) if state.physical_info.pulse_type else None,
            
            # 辅助检查
            exam_report_urls=[state.exam_report_url] if state.exam_report_url else [],
            
            # 辨证论治
            diagnosis=get_enum_value(state.diagnosis.syndrome) if state.diagnosis else None,
            syndrome=state.diagnosis.syndrome_description if state.diagnosis else None,
            syndrome_differentiation=state.diagnosis.pathogenesis if state.diagnosis else None,
            
            # 治疗方案
            treatment_principle=state.treatment_plan.principle if state.treatment_plan else None,
            herbal_prescription=state.treatment_plan.herbal_prescription if state.treatment_plan else None,
            lifestyle_advice=state.treatment_plan.lifestyle_advice if state.treatment_plan else [],
            diet_advice=state.treatment_plan.diet_advice if state.treatment_plan else [],
            precautions=state.treatment_plan.precautions if state.treatment_plan else [],
            follow_up_advice=state.treatment_plan.follow_up_advice if state.treatment_plan else None,
            
            # 补充信息
            supplementary_info=state.consultation_record.supplementary_info if state.consultation_record else None,
            
            # 元数据
            created_at=datetime.now(),
            updated_at=datetime.now(),
            metadata={
                "session_id": self.current_session.session_id,
                "turn_count": state.turn_count,
                "phase": get_enum_value(state.current_phase),
            }
        )
        
        self.current_session.state.consultation_record = record
        self.current_session.state.is_complete = True
        self.current_session.status = SessionStatus.COMPLETED
        
        # 触发回调
        if self._on_record_generated:
            self._on_record_generated(record)
        
        logger.info(f"Consultation record generated: {record}")
        return record
    
    async def _handle_consultation_complete(self) -> str:
        """处理问诊完成后的用户输入"""
        return "问诊已完成。如有其他问题，请重新开始咨询。"
    
    async def _generate_medical_history_prompt(self) -> str:
        """生成病史询问提示"""
        return (
            "了解了您的症状。接下来我想了解一些病史信息：\n\n"
            "1. 过敏史：您有没有对什么药物或食物过敏？\n"
            "2. 既往史：您之前有没有患过什么疾病？\n"
            "3. 家族史：您的直系亲属中有没有什么遗传病？\n"
            "4. 婚育史：（如适用）您的婚姻和生育情况如何？\n"
            "5. 个人史：您的工作环境、生活习惯等有什么特点？\n\n"
            "请逐一告诉我，如没有请说明'无'。"
        )
    
    def _extract_medical_history(self, message: str) -> Dict[str, Any]:
        """从消息中提取病史信息（简化实现）"""
        history = {}
        msg_lower = message.lower()
        
        # 过敏史关键词
        allergy_keywords = ["过敏", "过敏原", "过敏体质"]
        if any(kw in msg_lower for kw in allergy_keywords):
            history["allergies"] = [message]
        
        # 既往史关键词
        past_keywords = ["既往", "以前", "之前有", "患过"]
        if any(kw in msg_lower for kw in past_keywords):
            history["past_history"] = [message]
        
        # 家族史关键词
        family_keywords = ["家族", "遗传", "父亲", "母亲"]
        if any(kw in msg_lower for kw in family_keywords):
            history["family_history"] = [message]
        
        return history
    
    def _count_consultation_turns(self) -> int:
        """计算问诊轮数"""
        return self.current_session.state.turn_count
    
    def _get_intention_context(self) -> Dict[str, Any]:
        """获取意图识别的上下文"""
        if not self.current_session:
            return {}
        
        state = self.current_session.state
        return {
            "conversation_phase": get_enum_value(state.current_phase),
            "collected_symptoms": [s.name for s in state.symptoms],
            "previous_intention": state.intention,
            "patient_age": state.patient_info.age,
            "patient_gender": get_enum_value(state.patient_info.gender) if state.patient_info.gender else None,
            "turn_count": state.turn_count,
        }
    
    async def _handle_interrupt(
        self, 
        reason: ConsultationInterruptReason,
        error: Optional[str] = None
    ) -> str:
        """处理中断场景"""
        self.current_session.status = SessionStatus.INTERRUPTED
        self.current_session.interrupt_reason = reason
        self.current_session.updated_at = datetime.now()
        
        if error:
            logger.error(f"Consultation interrupted: {reason.value}, error: {error}")
        
        message = self.ENDING_MESSAGES.get(reason, "")
        message = message.format(max_turns=self.max_turns)
        
        # 如果是异常错误，生成最终病历
        if reason == ConsultationInterruptReason.ABNORMAL_ERROR:
            await self._generate_consultation_record()
        
        return message
    
    async def chat_stream(self, message: str) -> AsyncIterator[str]:
        """流式处理消息"""
        if not self.current_session:
            await self.start_session()
        
        self.current_session.messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })
        
        full_response = ""
        async for chunk in self.diagnosis_agent.run_stream(message):
            full_response += chunk
            yield chunk
        
        self.current_session.state = self.diagnosis_agent.get_state()
        self.current_session.messages.append({
            "role": "assistant",
            "content": full_response,
            "timestamp": datetime.now().isoformat(),
        })
        self.current_session.updated_at = datetime.now()
    
    def chat_sync(self, message: str) -> str:
        """同步版本"""
        return asyncio.run(self.chat(message))
    
    async def end_session(self) -> Dict[str, Any]:
        """结束当前会话"""
        if not self.current_session:
            return {"error": "No active session"}
        
        self.current_session.status = SessionStatus.COMPLETED
        self.current_session.interrupt_reason = ConsultationInterruptReason.PATIENT_QUIT
        self.current_session.updated_at = datetime.now()
        
        summary = self.get_session_summary(self.current_session.session_id)
        
        self.current_session = None
        
        return summary
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """获取会话摘要"""
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        state = session.state
        
        summary = {
            "session_id": session_id,
            "status": session.status.value,
            "interrupt_reason": session.interrupt_reason.value if session.interrupt_reason else None,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "turns": len(session.messages),
            "consultation_turns": state.turn_count,
            "phase": get_enum_value(state.current_phase),
            "symptoms": [s.name for s in state.symptoms],
            "has_diagnosis": state.diagnosis is not None,
            "has_treatment": state.treatment_plan is not None,
            "has_record": state.consultation_record is not None,
        }
        
        if state.patient_info.age:
            summary["patient_age"] = state.patient_info.age
        if state.patient_info.gender:
            summary["patient_gender"] = get_enum_value(state.patient_info.gender)
        
        if state.consultation_record:
            summary["consultation_record"] = state.consultation_record.model_dump()
        
        return summary
    
    def get_consultation_record(self, session_id: Optional[str] = None) -> Optional[ConsultationRecord]:
        """获取结构化病历"""
        if session_id:
            session = self.sessions.get(session_id)
            return session.state.consultation_record if session else None
        return self.current_session.state.consultation_record if self.current_session else None
    
    async def query_knowledge(
        self,
        query: str,
        entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """查询知识库"""
        results = self.knowledge_base.search_similar(
            query,
            entity_types=[entity_type] if entity_type else None,
            max_results=5
        )
        return results
    
    def get_session(self, session_id: str) -> Optional[ConsultationSession]:
        """获取会话"""
        return self.sessions.get(session_id)
    
    def list_sessions(self) -> List[str]:
        """列出所有会话ID"""
        return list(self.sessions.keys())


async def create_cli_session():
    """创建命令行会话"""
    system = TCMConsultationSystem()
    
    print("=" * 60)
    print("欢迎使用中医智能问诊系统")
    print("=" * 60)
    print("输入您的问题，系统将进行中医辨证分析")
    print("输入 'quit' 或 '退出' 结束问诊")
    print("输入 'reset' 重新开始")
    print("输入 'summary' 查看当前问诊摘要")
    print("=" * 60)
    print()
    
    await system.start_session()
    
    print("助手: " + system.diagnosis_agent.WELCOME_MESSAGE)
    
    while True:
        try:
            user_input = input("您: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["quit", "退出", "exit", "q"]:
                summary = await system.end_session()
                print("\n问诊摘要:")
                print(f"- 对话轮次: {summary.get('turns', 0)}")
                if summary.get("consultation_record"):
                    record = summary["consultation_record"]
                    print(f"- 主诉: {record.get('chief_complaint', 'N/A')}")
                    print(f"- 症状: {', '.join(record.get('symptoms', []))}")
                print("\n感谢您的咨询，祝您健康！")
                break
            
            if user_input.lower() in ["reset", "重置"]:
                await system.start_session()
                print("\n[已重置问诊]")
                print("助手: " + system.diagnosis_agent.WELCOME_MESSAGE)
                continue
            
            if user_input.lower() == "summary":
                if system.current_session:
                    summary = system.get_session_summary(system.current_session.session_id)
                    print("\n当前问诊摘要:")
                    print(f"- 阶段: {summary.get('phase')}")
                    print(f"- 问诊轮数: {summary.get('consultation_turns', 0)}")
                    print(f"- 已收集症状: {', '.join(summary.get('symptoms', []))}")
                    if summary.get("consultation_record"):
                        print(f"- 病历已生成")
                continue
            
            response = await system.chat(user_input)
            if response:
                print(f"\n助手: {response}")
            print()
            
        except KeyboardInterrupt:
            print("\n\n问诊已中断，再见！")
            break
        except Exception as e:
            print(f"\n发生错误: {e}")
            continue
    
    return system


def main():
    """主入口"""
    asyncio.run(create_cli_session())


if __name__ == "__main__":
    main()
