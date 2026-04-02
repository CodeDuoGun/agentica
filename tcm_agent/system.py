# -*- coding: utf-8 -*-
"""
TCM Consultation System - 主协调系统
中医问诊系统主入口

架构：
1. 意图识别 -> 普通咨询 / 医疗问诊 / 其他问题
2. 普通咨询 -> RAG 检索回答
3. 医疗问诊 -> 多轮问答收集槽位信息
4. 完成后 -> 异步生成结构化病历
"""
import asyncio
import traceback
import re
from typing import Dict, Any, Optional, List, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from agentica import Agent, QwenChat

from tcm_agent.models import (
    ConsultationState,
    ConsultationPhase,
    ConsultationVisitType,
    ConsultationSlot,
    SlotStatus,
    SlotCollectionStatus,
    IntentionCategory,
    IntentionResult,
    ConsultationRecord,
    SymptomInfo,
    MedicalHistory,
    AllergyInfo,
    PhysicalInfo,
    DiagnosisInfo,
    TreatmentPlan,
    PatientInfo,
    CONSULTATION_SLOTS_DEFINITION,
    REQUIRED_SLOTS,
    SLOT_GROUPS,
    get_enum_value,
    get_slot_by_key,
    get_next_slot,
    is_required_slot,
)
from tcm_agent.knowledge import TCMKnowledgeBase
from tcm_agent.intention import IntentionRecognitionAgent
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
    status: SessionStatus = SessionStatus.ACTIVE
    state: ConsultationState = field(default_factory=ConsultationState)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class TCMConsultationSystem:
    """
    中医问诊系统主协调器
    
    工作流程：
    1. 接收用户消息
    2. 意图识别（普通咨询 / 医疗问诊 / 其他问题）
    3. 根据意图路由到不同 Agent
    4. 医疗问诊：多轮槽位收集
    5. 完成：异步生成结构化病历
    """
    
    HOSPITAL_REFERRAL = "中医门诊部"
    
    def __init__(
        self,
        enable_stream: bool = True,
        max_turns: int = 50,
    ):
        self.enable_stream = enable_stream
        self.max_turns = max_turns
        
        # 初始化知识库
        self.knowledge_base = TCMKnowledgeBase()
        self.knowledge_base.initialize()
        
        # 初始化 Agent
        self._init_agents()
        
        # 当前会话
        self.current_session: Optional[ConsultationSession] = None
    
    def _init_agents(self):
        """初始化各个 Agent"""
        # 基础模型
        base_model = QwenChat(id="qwen-plus", temperature=0.7)
        
        # 意图识别 Agent
        intention_model = QwenChat(id="qwen-plus", temperature=0.1)
        self.intention_agent = IntentionRecognitionAgent(model=intention_model)
        
        # 普通咨询 Agent（带 RAG）
        self._init_general_consultation_agent()
        
        # 医疗问诊 Agent
        self._init_medical_consultation_agent()
    
    def _init_general_consultation_agent(self):
        """初始化普通咨询 Agent"""
        model = QwenChat(id="qwen-plus", temperature=0.7)
        
        system_prompt = """你是一个专业的中医健康咨询助手。请根据提供的参考信息回答用户的问题。

参考信息来自中医知识库，包含相关的症状、疾病、治疗方案等内容。
请结合参考信息给出专业、准确的回答。

注意：
1. 如果参考信息中有相关内容，优先基于参考信息回答
2. 如果没有相关参考信息，可以基于你的中医知识回答
3. 如果问题超出你的能力范围，建议用户就医
4. 回答要简洁、专业、易懂"""
        
        self.general_consultation_agent = Agent(
            model=model,
            name="GeneralConsultationAgent",
            instructions=system_prompt,
            add_history_to_messages=True,
            history_window=10,
        )
    
    def _init_medical_consultation_agent(self):
        """初始化医疗问诊 Agent"""
        model = QwenChat(id="qwen-plus", temperature=0.7)
        
        system_prompt = """你是一个专业的中医问诊助手，正在进行多轮问诊。

你的任务是：
1. 根据当前的问诊阶段，向用户询问相关信息
2. 从用户的回答中提取有效的槽位信息
3. 更新问诊状态
4. 决定是否继续收集信息或结束问诊

问诊槽位包括：
- 基本信息：性别、年龄
- 主诉：主要症状、持续时间、具体表现
- 既往史：之前类似病史
- 过敏史：过敏原和反应
- 婚育史：婚育情况
- 个人史：生活习惯（抽烟、喝酒等）
- 家族史：遗传病史
- 舌照：舌象照片
- 面照：面部照片
- 检查报告：相关检查结果
- 补充信息：其他需要说明的情况

每次只询问一个问题，简洁明了。
收集到足够信息后，进入诊断环节。"""
        
        self.medical_consultation_agent = Agent(
            model=model,
            name="MedicalConsultationAgent",
            instructions=system_prompt,
            add_history_to_messages=True,
            history_window=20,
        )
    
    async def start_session(self, session_id: str, visit_type: str = "first_visit"):
        """启动新会话"""
        state = ConsultationState(session_id=session_id)
        
        # 设置就诊类型
        try:
            state.visit_type = ConsultationVisitType(visit_type)
        except ValueError:
            state.visit_type = ConsultationVisitType.FIRST_VISIT
        
        # 初始化槽位状态
        state.pending_slots = list(REQUIRED_SLOTS)
        for slot_def in CONSULTATION_SLOTS_DEFINITION:
            if slot_def["key"] not in state.slot_status:
                state.slot_status[slot_def["key"]] = SlotCollectionStatus(
                    key=slot_def["key"],
                    status=SlotStatus.PENDING if slot_def["key"] in state.pending_slots else SlotStatus.SKIPPED
                )
        
        self.current_session = ConsultationSession(
            session_id=session_id,
            state=state,
        )
        
        logger.info(f"Session started: {session_id}, visit_type: {visit_type}")
        return session_id
    
    async def chat(self, message: str) -> str:
        """
        处理用户消息的入口
        
        流程：
        1. 意图识别
        2. 根据意图路由
        3. 返回响应
        """
        if not self.current_session:
            return "会话未初始化"
        
        state = self.current_session.state
        
        # 检查轮数限制
        if state.turn_count >= state.max_turns:
            return await self._handle_interrupt(
                ConsultationInterruptReason.MAX_TURNS_EXCEEDED
            )
        
        state.turn_count += 1
        
        # 添加用户消息
        self.current_session.messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })
        
        try:
            # ========== 步骤1：意图识别 ==========
            intention_result = await self.intention_agent.recognize(
                message,
                self._get_intention_context()
            )
            
            logger.info(f"Intention recognized: {intention_result.category}")
            
            # 更新当前意图
            state.current_intent = intention_result.category
            
            # ========== 步骤2：根据意图路由 ==========
            response = await self._route_by_intention(intention_result, message)
            
        except Exception as e:
            logger.error(f"Error in chat: {traceback.format_exc()}")
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
        
        self.current_session.updated_at = datetime.now()
        
        return response
    
    def _get_intention_context(self) -> Dict[str, Any]:
        """获取意图识别的上下文"""
        if not self.current_session:
            return {}
        
        state = self.current_session.state
        recent_messages = self.current_session.messages[-6:]
        
        return {
            "session_id": state.session_id,
            "phase": state.consultation_phase,
            "current_intent": state.current_intent,
            "collected_slots": [k for k, v in state.slot_status.items() if v.status == SlotStatus.COLLECTED],
            "recent_messages": recent_messages,
        }
    
    async def _route_by_intention(
        self,
        intention: IntentionResult,
        message: str
    ) -> str:
        """根据意图路由到不同的 Agent"""
        category = get_enum_value(intention.category)
        
        if category == "general_medical":
            # 普通医疗咨询 -> RAG 检索
            return await self._handle_general_consultation(message)
        
        elif category == "consultation":
            # 医疗问诊 -> 多轮问答收集信息
            return await self._handle_medical_consultation(message, intention)
        
        elif category == "other":
            # 其他问题 -> 其他 Agent 处理
            return await self._handle_other_question(message)
        
        else:
            # 未知意图 -> 引导进入问诊或普通咨询
            return "抱歉，我无法理解您的问题。您可以：\n1. 描述您的健康问题，我会为您问诊\n2. 咨询一般的中医健康知识"
    
    async def _handle_general_consultation(self, message: str) -> str:
        """
        处理普通咨询（接入 RAG）
        """
        # RAG 检索
        kb_results = self.knowledge_base.search_similar(message, max_results=5)
        
        # 构建参考信息
        context = ""
        if kb_results:
            context = "【参考信息】\n"
            for i, result in enumerate(kb_results, 1):
                content = result.get('content', '')[:500]
                context += f"{i}. {content}\n\n"
        
        # 构建提示
        prompt = f"用户问题：{message}\n\n{context}\n请根据以上信息回答用户的问题。"
        
        # 调用 Agent
        result = await self.general_consultation_agent.run(prompt)
        
        response = result.content
        
        # 添加就医建议
        response += f"\n\n💡 如需进一步诊疗，建议您前往【{self.HOSPITAL_REFERRAL}】进行详细咨询。"
        
        return response
    
    async def _handle_medical_consultation(
        self,
        message: str,
        intention: IntentionResult
    ) -> str:
        """
        处理医疗问诊（多轮问答收集信息）
        """
        state = self.current_session.state
        
        # 欢迎阶段
        if state.consultation_phase == ConsultationPhase.WELCOME:
            return await self._handle_welcome(message, intention)
        
        # 问诊阶段
        elif state.consultation_phase == ConsultationPhase.CONSULTATION:
            return await self._handle_consultation_phase(message, intention)
        
        # 补充信息阶段
        elif state.consultation_phase == ConsultationPhase.SUPPLEMENTARY:
            return await self._handle_supplementary_phase(message)
        
        # 完成阶段
        elif state.consultation_phase == ConsultationPhase.COMPLETE:
            return await self._handle_complete_phase()
        
        return "系统状态异常"
    
    async def _handle_welcome(self, message: str, intention: IntentionResult) -> str:
        """欢迎阶段 - 初始化问诊"""
        state = self.current_session.state
        visit_type = state.visit_type
        visit_type_text = "复诊" if visit_type == ConsultationVisitType.FOLLOW_UP_VISIT else "初诊"
        
        # 初始化槽位状态
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
        
        # 初始化患者信息
        state.patient_info = PatientInfo()
        
        # 进入问诊阶段
        state.consultation_phase = ConsultationPhase.CONSULTATION
        
        # 欢迎消息
        welcome = f"您好！欢迎来到中医智能问诊系统。我是您的中医健康助手。"
        
        if visit_type_text == "复诊":
            welcome += " 您是复诊患者，请问您这次有什么需要咨询的呢？"
            # 复诊跳过基本信息，直接问主诉
            state.pending_slots = [s for s in state.pending_slots if s not in ["gender", "age"]]
        else:
            welcome += " 我了解到您是初次就诊。为了更好地为您服务，我需要了解一些信息。"
        
        return welcome
    
    async def _handle_consultation_phase(
        self,
        message: str,
        intention: IntentionResult
    ) -> str:
        """问诊阶段 - 收集槽位信息"""
        state = self.current_session.state
        msg_lower = message.lower()
        
        # 检查是否要结束问诊
        if self._should_end_consultation(msg_lower, message):
            return await self._finish_consultation()
        
        # 从当前消息中提取槽位信息
        self._extract_slots_from_message(message, intention)
        
        # 获取下一个待询问的槽位
        next_slot_key = self._get_next_pending_slot()
        
        if next_slot_key:
            # 还有待收集的槽位
            state.current_slot_key = next_slot_key
            slot_def = get_slot_by_key(next_slot_key)
            if slot_def:
                return slot_def["question"]
        
        # 必需槽位已收集，询问补充信息
        required_done = all(
            state.slot_status.get(k, SlotCollectionStatus(key=k)).status == SlotStatus.COLLECTED
            for k in REQUIRED_SLOTS if k in state.slot_status
        )
        
        if required_done:
            # 询问补充信息
            state.consultation_phase = ConsultationPhase.SUPPLEMENTARY
            return "好的，基本信息已收集。请问您还有舌照、面照、检查报告需要上传吗？或者有其他需要补充说明的情况？"
        
        # 继续问下一个槽位
        next_slot_key = self._get_next_pending_slot()
        if next_slot_key:
            slot_def = get_slot_by_key(next_slot_key)
            if slot_def:
                return slot_def["question"]
        
        # 所有槽位收集完成
        return await self._finish_consultation()
    
    async def _handle_supplementary_phase(self, message: str) -> str:
        """补充信息阶段"""
        state = self.current_session.state
        msg_lower = message.lower()
        
        # 保存补充信息
        if message and msg_lower not in ["无", "没有", "没了", "没有了"]:
            state.supplementary_info = message
        
        # 结束问诊
        return await self._finish_consultation()
    
    async def _handle_complete_phase(self) -> str:
        """完成阶段"""
        return "问诊已完成，请查看上方诊断结果。"
    
    async def _finish_consultation(self) -> str:
        """结束问诊，生成诊断"""
        state = self.current_session.state
        state.consultation_phase = ConsultationPhase.COMPLETE
        
        # 生成诊断
        diagnosis_response = await self._generate_diagnosis()
        
        # 异步生成结构化病历
        asyncio.create_task(self._generate_consultation_record())
        
        return diagnosis_response
    
    def _should_end_consultation(self, msg_lower: str, message: str) -> bool:
        """判断是否要结束问诊"""
        end_keywords = ["没有了", "没别的", "就这些", "暂时没", "就这些了", "可以了", "结束", "诊断", "结论"]
        
        if any(kw in msg_lower for kw in end_keywords):
            return True
        
        # 多次回复"没有"也可能结束
        if msg_lower in ["没", "无", "没有", "没有其他", "没了"]:
            no_count = getattr(self.current_session.state, '_no_response_count', 0) + 1
            self.current_session.state._no_response_count = no_count
            if no_count >= 2:
                self.current_session.state._no_response_count = 0
                return True
        
        return False
    
    def _extract_slots_from_message(
        self,
        message: str,
        intention: IntentionResult
    ) -> None:
        """从消息中提取槽位信息"""
        state = self.current_session.state
        msg_lower = message.lower()
        entities = intention.entities
        
        # ========== 基本信息 ==========
        # 性别
        if state.slot_status.get("gender", SlotCollectionStatus(key="gender")).status != SlotStatus.COLLECTED:
            gender = None
            if "gender" in entities:
                gender = entities["gender"]
            elif any(k in msg_lower for k in ["男", "先生", "男性"]):
                gender = "男"
            elif any(k in msg_lower for k in ["女", "女士", "女性"]):
                gender = "女"
            
            if gender:
                state.slot_status["gender"].status = SlotStatus.COLLECTED
                state.slot_status["gender"].value = gender
                state.patient_info.gender = gender
                state.pending_slots = [s for s in state.pending_slots if s != "gender"]
        
        # 年龄
        if state.slot_status.get("age", SlotCollectionStatus(key="age")).status != SlotStatus.COLLECTED:
            age = entities.get("age")
            if not age:
                age_match = re.search(r'(\d+)\s*(岁|周岁)', message)
                if age_match:
                    age = age_match.group(1)
            
            if age:
                state.slot_status["age"].status = SlotStatus.COLLECTED
                state.slot_status["age"].value = age
                state.patient_info.age = age
                state.pending_slots = [s for s in state.pending_slots if s != "age"]
        
        # ========== 主诉 ==========
        if state.slot_status.get("chief_complaint", SlotCollectionStatus(key="chief_complaint")).status != SlotStatus.COLLECTED:
            symptoms = entities.get("symptom", []) or entities.get("symptom_list", [])
            if symptoms:
                chief = ", ".join(symptoms) if isinstance(symptoms, list) else symptoms
                state.slot_status["chief_complaint"].status = SlotStatus.COLLECTED
                state.slot_status["chief_complaint"].value = chief
                state.chief_complaint = chief
                state.pending_slots = [s for s in state.pending_slots if s != "chief_complaint"]
                
                # 同时记录症状列表
                for symptom_name in (symptoms if isinstance(symptoms, list) else [symptoms]):
                    symptom = SymptomInfo(name=symptom_name)
                    if symptom.name not in [s.name for s in state.symptoms]:
                        state.symptoms.append(symptom)
        
        # ========== 症状详情 ==========
        if state.slot_status.get("symptom_detail", SlotCollectionStatus(key="symptom_detail")).status != SlotStatus.COLLECTED:
            duration = entities.get("duration")
            location = entities.get("location")
            severity = entities.get("severity")
            
            detail_info = []
            if duration:
                detail_info.append(f"持续时间：{duration}")
            if location:
                detail_info.append(f"部位：{location}")
            if severity:
                detail_info.append(f"程度：{severity}")
            
            if detail_info or len(message) > 10:
                state.slot_status["symptom_detail"].status = SlotStatus.COLLECTED
                state.slot_status["symptom_detail"].value = message
                state.slot_status["symptom_detail"].raw_content = message
                state.pending_slots = [s for s in state.pending_slots if s != "symptom_detail"]
                
                # 更新症状详情
                if state.symptoms and detail_info:
                    state.symptoms[-1].duration = duration
                    state.symptoms[-1].location = location
                    state.symptoms[-1].severity = severity
        
        # ========== 既往史 ==========
        if state.slot_status.get("past_history", SlotCollectionStatus(key="past_history")).status != SlotStatus.COLLECTED:
            if any(k in msg_lower for k in ["既往", "之前", "以前", "病史"]):
                state.slot_status["past_history"].status = SlotStatus.COLLECTED
                state.slot_status["past_history"].value = message
                state.past_history = message
                state.pending_slots = [s for s in state.pending_slots if s != "past_history"]
        
        # ========== 过敏史 ==========
        if state.slot_status.get("allergy", SlotCollectionStatus(key="allergy")).status != SlotStatus.COLLECTED:
            if any(k in msg_lower for k in ["过敏"]):
                state.slot_status["allergy"].status = SlotStatus.COLLECTED
                state.slot_status["allergy"].value = message
                state.allergy_info.has_allergy = True
                state.allergy_info.allergen = message
                state.pending_slots = [s for s in state.pending_slots if s != "allergy"]
            elif any(k in msg_lower for k in ["没有过敏", "不过敏", "无过敏"]):
                state.slot_status["allergy"].status = SlotStatus.COLLECTED
                state.slot_status["allergy"].value = "无"
                state.pending_slots = [s for s in state.pending_slots if s != "allergy"]
        
        # ========== 婚育史 ==========
        if state.slot_status.get("marriage_history", SlotCollectionStatus(key="marriage_history")).status != SlotStatus.COLLECTED:
            if any(k in msg_lower for k in ["婚", "育", "生", "孩"]):
                state.slot_status["marriage_history"].status = SlotStatus.COLLECTED
                state.slot_status["marriage_history"].value = message
                state.marriage_history = message
                state.pending_slots = [s for s in state.pending_slots if s != "marriage_history"]
        
        # ========== 个人史 ==========
        if state.slot_status.get("personal_history", SlotCollectionStatus(key="personal_history")).status != SlotStatus.COLLECTED:
            if any(k in msg_lower for k in ["抽烟", "吸烟", "喝酒", "饮酒", "生活习惯"]):
                state.slot_status["personal_history"].status = SlotStatus.COLLECTED
                state.slot_status["personal_history"].value = message
                state.personal_history = message
                state.pending_slots = [s for s in state.pending_slots if s != "personal_history"]
        
        # ========== 家族史 ==========
        if state.slot_status.get("family_history", SlotCollectionStatus(key="family_history")).status != SlotStatus.COLLECTED:
            if any(k in msg_lower for k in ["家族", "遗传", "父母", "爸妈"]):
                state.slot_status["family_history"].status = SlotStatus.COLLECTED
                state.slot_status["family_history"].value = message
                state.family_history = message
                state.pending_slots = [s for s in state.pending_slots if s != "family_history"]
        
        # ========== 舌照 ==========
        if state.slot_status.get("tongue", SlotCollectionStatus(key="tongue")).status != SlotStatus.COLLECTED:
            if message.startswith("data:image") or any(ext in message.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                if "tongue" in msg_lower or "舌" in message:
                    state.slot_status["tongue"].status = SlotStatus.COLLECTED
                    state.slot_status["tongue"].value = "已上传"
                    state.tongue_image_url = message
                    state.pending_slots = [s for s in state.pending_slots if s != "tongue"]
        
        # ========== 面照 ==========
        if state.slot_status.get("face", SlotCollectionStatus(key="face")).status != SlotStatus.COLLECTED:
            if message.startswith("data:image") or any(ext in message.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                if "face" in msg_lower or "面" in msg_lower:
                    state.slot_status["face"].status = SlotStatus.COLLECTED
                    state.slot_status["face"].value = "已上传"
                    state.face_image_url = message
                    state.pending_slots = [s for s in state.pending_slots if s != "face"]
        
        # ========== 检查报告 ==========
        if state.slot_status.get("exam_report", SlotCollectionStatus(key="exam_report")).status != SlotStatus.COLLECTED:
            if message.startswith("data:image") or any(ext in message.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                state.slot_status["exam_report"].status = SlotStatus.COLLECTED
                state.slot_status["exam_report"].value = "已上传"
                state.exam_report_url = message
                state.pending_slots = [s for s in state.pending_slots if s != "exam_report"]
    
    def _get_next_pending_slot(self) -> Optional[str]:
        """获取下一个待收集的槽位"""
        state = self.current_session.state
        
        # 首先检查当前正在收集的槽位
        if state.current_slot_key:
            slot_status = state.slot_status.get(state.current_slot_key)
            if slot_status and slot_status.status == SlotStatus.PENDING:
                return state.current_slot_key
        
        # 遍历所有槽位定义
        for slot_def in CONSULTATION_SLOTS_DEFINITION:
            key = slot_def["key"]
            slot_status = state.slot_status.get(key)
            if slot_status and slot_status.status == SlotStatus.PENDING and key in state.pending_slots:
                return key
        
        return None
    
    async def _handle_other_question(self, message: str) -> str:
        """处理其他问题"""
        # TODO 调用agent进行处理
        return f"您的问题是「{message}」，这个问题我暂时无法回答。建议您：\n1. 咨询具体的中医健康问题\n2. 描述您的症状进行问诊"
    
    async def _generate_diagnosis(self) -> str:
        """生成诊断结果"""
        state = self.current_session.state
        
        # 构建诊断上下文
        diagnosis_context = self._build_diagnosis_context()
        
        # 调用 Agent 生成诊断
        prompt = f"""请根据以下问诊信息进行中医辨证论治：

{diagnosis_context}

请给出：
1. 辨证分析
2. 证型诊断
3. 治法方药建议
4. 养生调护建议

请用专业、简洁的语言回复。"""
        
        result = await self.medical_consultation_agent.run(prompt)
        
        diagnosis_text = result.content
        
        # 保存诊断信息
        state.diagnosis = DiagnosisInfo(
            analysis=diagnosis_text,
        )
        
        return diagnosis_text
    
    def _build_diagnosis_context(self) -> str:
        """构建诊断上下文"""
        state = self.current_session.state
        
        parts = []
        
        # 基本信息
        if state.patient_info.gender:
            parts.append(f"性别：{state.patient_info.gender}")
        if state.patient_info.age:
            parts.append(f"年龄：{state.patient_info.age}岁")
        
        # 主诉
        if state.chief_complaint:
            parts.append(f"主诉：{state.chief_complaint}")
        
        # 症状
        if state.symptoms:
            symptoms_text = "、".join([s.name for s in state.symptoms])
            parts.append(f"症状：{symptoms_text}")
        
        # 现病史
        if state.present_illness:
            parts.append(f"现病史：{state.present_illness}")
        
        # 既往史
        if state.past_history:
            parts.append(f"既往史：{state.past_history}")
        
        # 过敏史
        if state.allergy_info.has_allergy:
            parts.append(f"过敏史：{state.allergy_info.allergen}（{state.allergy_info.reaction}）")
        else:
            parts.append("过敏史：无")
        
        # 舌照分析
        if state.tongue_analysis:
            parts.append(f"舌象：{state.tongue_analysis}")
        
        # 补充信息
        if state.supplementary_info:
            parts.append(f"补充：{state.supplementary_info}")
        
        return "\n".join(parts)
    
    async def _generate_consultation_record(self) -> ConsultationRecord:
        """生成结构化病历"""
        state = self.current_session.state
        
        try:
            record = ConsultationRecord(
                session_id=state.session_id,
                visit_type=state.visit_type,
                visit_date=datetime.now(),
                
                patient_name=state.patient_info.name,
                patient_age=state.patient_info.age,
                patient_gender=state.patient_info.gender,
                
                chief_complaint=state.chief_complaint,
                
                past_history=state.past_history,
                personal_history=state.personal_history,
                family_history=state.family_history,
                marriage_history=state.marriage_history,
                
                allergy_info=state.allergy_info if state.allergy_info.has_allergy else AllergyInfo(),
                
                symptoms=state.symptoms,
                
                physical_exam=PhysicalInfo(),
                
                tongue_image_url=state.tongue_image_url,
                tongue_image_analysis=state.tongue_analysis,
                face_image_url=state.face_image_url,
                face_image_analysis=state.face_analysis,
                
                exam_report_url=state.exam_report_url,
                exam_report_summary=state.exam_report_summary,
                
                supplementary_info=state.supplementary_info,
                
                diagnosis=state.diagnosis,
                treatment_plan=state.treatment_plan,
            )
            
            state.consultation_record = record
            logger.info(f"Consultation record generated: {state.session_id}")
            
            return record
            
        except Exception as e:
            logger.error(f"Error generating consultation record: {e}")
            raise
    
    async def _handle_interrupt(
        self,
        reason: ConsultationInterruptReason,
        error: Optional[str] = None
    ) -> str:
        """处理中断"""
        state = self.current_session.state
        state.is_complete = True
        
        if reason == ConsultationInterruptReason.MAX_TURNS_EXCEEDED:
            return "问诊轮数已达到上限，请重新开始或联系人工客服。"
        
        elif reason == ConsultationInterruptReason.PATIENT_QUIT:
            return "您已结束问诊，感谢您的使用！"
        
        elif reason == ConsultationInterruptReason.ABNORMAL_ERROR:
            logger.error(f"Consultation interrupted: {error}")
            return f"问诊过程中出现错误：{error}\n\n请重新开始问诊。"
        
        return "问诊已结束。"
