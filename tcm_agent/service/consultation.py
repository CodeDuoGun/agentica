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
from agentica.run_response import RunResponse

from tcm_agent.models import (
    ConsultationState,
    ConsultationPhase,
    ConsultationVisitType,
    ConsultationSlot,
    SlotStatus,
    SlotCollectionStatus,
    ConsultationTurnResult,
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
    ConsultationControl,
    get_enum_value,
    get_slot_by_key,
    get_next_slot,
    is_required_slot,
)
from tcm_agent.knowledge import TCMKnowledgeBase
from tcm_agent.intention import IntentionRecognitionAgent
from tcm_agent.schema.consultation import ChatImages
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
        max_turns: int = 50,
    ):
        self.max_turns = max_turns
        
        # 初始化知识库
        self.knowledge_base = TCMKnowledgeBase()
        self.knowledge_base.initialize()
        
        # 初始化 Agent
        self._init_agents()
        
        # 当前会话
        self.current_session: Optional[ConsultationSession] = None
        
        # 初始化状态
        self.state = ConsultationState()
    
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
        
        self._init_diagnosis_agent()
    
    def _init_diagnosis_agent(self):
        """初始化问诊agent， 给出诊断结果和建议开方"""
        model = QwenChat(id="qwen-plus", temperature=0.1)
        system_prompt = "你是中医诊断和建议开方专家，根据用户的问题，给出诊断结果和建议处方" 
        # TODO 指定response_model=DiagnosisInfo
        self.diagnosis_agent = Agent(
            model=model,
            name="MedicalDiagnosisAgent",
            instructions=system_prompt,
            add_history_to_messages=True,
            history_window=20,
        )

    
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
            response_model=ConsultationTurnResult,
            add_history_to_messages=True,
            history_window=20,
        )
    
    async def start_session(self, session_id: str, visit_type: str = "first_visit"):
        """启动新会话"""
        self.state = ConsultationState(session_id=session_id)
        
        # 设置就诊类型
        try:
            self.state.visit_type = ConsultationVisitType(visit_type)
        except ValueError:
            self.state.visit_type = ConsultationVisitType.FIRST_VISIT
        
        # 初始化槽位状态
        self.state.pending_slots = list(REQUIRED_SLOTS)
        for slot_def in CONSULTATION_SLOTS_DEFINITION:
            if slot_def["key"] not in self.state.slot_status:
                self.state.slot_status[slot_def["key"]] = SlotCollectionStatus(
                    key=slot_def["key"],
                    status=SlotStatus.PENDING if slot_def["key"] in self.state.pending_slots else SlotStatus.SKIPPED
                )
        
        self.current_session = ConsultationSession(
            session_id=session_id,
            state=self.state,
        )
        
        logger.info(f"Session started: {session_id}, visit_type: {visit_type}")
        return session_id
    
    
    async def chat(self, message: str, imgs: Optional[ChatImages]=None) -> str:
        """
        处理用户消息的入口（非流式）

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
            response = await self._route_by_intention(intention_result, message, imgs)

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

    async def chat_stream(self, message: str, imgs: Optional[ChatImages]=None) -> AsyncIterator[str]:
        """
        处理用户消息的入口（流式）

        Yields:
            流式文本片段

        流程：
        1. 意图识别（非流式）
        2. 根据意图路由，流式返回响应
        """
        if not self.current_session:
            yield "会话未初始化"
            return

        state = self.current_session.state

        # 检查轮数限制
        if state.turn_count >= state.max_turns:
            yield await self._handle_interrupt(
                ConsultationInterruptReason.MAX_TURNS_EXCEEDED
            )
            return
        state.turn_count += 1

        # 添加用户消息
        self.current_session.messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })

        try:
            # ========== 步骤1：意图识别（非流式） ==========
            intention_result = await self.intention_agent.recognize(
                message,
                self._get_intention_context()
            )

            logger.info(f"Intention recognized: {intention_result.category}")
            state.current_intent = intention_result.category

            # ========== 步骤2：根据意图路由（流式） ==========
            category = get_enum_value(intention_result.category)

            if category == "general_medical":
                async for chunk in self._handle_general_consultation_stream(message):
                    yield chunk

            elif category == "consultation":
                async for chunk in self._handle_medical_consultation_stream(message, intention_result, imgs):
                    yield chunk

            elif category == "other":
                async for chunk in self._handle_other_question_stream(message):
                    yield chunk

            else:
                yield "抱歉，我无法理解您的问题。您可以：\n1. 描述您的健康问题，我会为您问诊\n2. 咨询一般的中医健康知识"

        except Exception as e:
            logger.error(f"Error in chat_stream: {traceback.format_exc()}")
            yield await self._handle_interrupt(
                ConsultationInterruptReason.ABNORMAL_ERROR,
                error=str(e)
            )

        self.current_session.updated_at = datetime.now()
    
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
        message: str,
        imgs: Optional[ChatImages]=None
    ) -> str:
        """根据意图路由到不同的 Agent"""
        category = get_enum_value(intention.category)

        if category == "general_medical":
            # 普通医疗咨询 -> RAG 检索
            return await self._handle_general_consultation(message)

        elif category == "consultation":
            # 医疗问诊 -> 多轮问答收集信息
            return await self._handle_medical_consultation(message, intention, imgs)

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

        response = result.content if hasattr(result, 'content') else str(result)

        # 添加就医建议
        response += f"\n\n💡 如需进一步诊疗，建议您前往【{self.HOSPITAL_REFERRAL}】进行详细咨询。"

        return response

    async def _handle_general_consultation_stream(self, message: str) -> AsyncIterator[str]:
        """
        处理普通咨询（接入 RAG）- 流式版本
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

        # 流式调用 Agent
        full_response = ""
        async for chunk in self.general_consultation_agent.run_stream(prompt):
            if hasattr(chunk, 'content') and chunk.content:
                full_response += chunk.content
                yield chunk.content

        # 添加就医建议
        if full_response:
            yield f"\n\n💡 如需进一步诊疗，建议您前往【{self.HOSPITAL_REFERRAL}】进行详细咨询。"

        # 保存完整响应到会话
        self.current_session.messages.append({
            "role": "assistant",
            "content": full_response,
            "timestamp": datetime.now().isoformat(),
        })

    async def _handle_other_question(self, message: str) -> str:
        """处理其他问题"""
        # TODO 调用agent进行处理
        return f"您的问题是「{message}」，这个问题我暂时无法回答。建议您：\n1. 咨询具体的中医健康问题\n2. 描述您的症状进行问诊"

    async def _handle_other_question_stream(self, message: str) -> AsyncIterator[str]:
        """处理其他问题 - 流式版本"""
        # TODO 实现流式版本
        response = f"您的问题是「{message}」，这个问题我暂时无法回答。建议您：\n1. 咨询具体的中医健康问题\n2. 描述您的症状进行问诊"

        # 简单模拟打字效果
        for char in response:
            yield char
            await asyncio.sleep(0.01)

        # 保存完整响应
        self.current_session.messages.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat(),
        })
    
    async def _handle_medical_consultation(
        self,
        message: str,
        intention: IntentionResult,
        imgs: Optional[ChatImages]=None
    ) -> str:
        """
        处理医疗问诊（多轮问答收集信息）
        """
        state = self.current_session.state
        
        # 问诊阶段
        if state.consultation_phase == ConsultationPhase.CONSULTATION:
            return await self._handle_consultation_phase(message, intention, imgs)
        
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
            welcome += "您是复诊患者，请问您这次有什么需要咨询的呢？"
            # TODO 从接口更新槽位信息，复诊跳过基本信息，直接问主诉
            state.pending_slots = [s for s in state.pending_slots if s not in ["gender", "age"]]
        else:
            welcome += " 我了解到您是初次就诊。为了更好地为您服务，我需要了解一些信息。"
        
        return welcome
    
    async def _handle_consultation_phase(
        self,
        message: str,
        intention: IntentionResult,
        imgs: Optional[ChatImages]=None
    ) -> str:
        """问诊阶段 - 收集槽位信息
        首先，根据当前问诊阶段患者输入内容，进行槽位填充
        然后，结合当前意图，上下文，当前建议询问内容，当前需要继续收集的内容，进行询问，
        如果槽位填充都结束，分三次请求患者上传舌照，面照以及检查报告，三个槽位填充后，询问是否有补充
        注意，如果是从某个部位或者某一个症状进行询问时，需要给出
        """
        state = self.current_session.state

        # 1️⃣ 判断是否结束
        if self._should_end_consultation(message.lower(), message):
            return await self._finish_consultation()

        # 2️⃣ 构造当前上下文（槽位 + 历史）
        if imgs:
            await self._process_uploaded_images(imgs, state)
        slot_state = {
            k: v.value if hasattr(v, "value") else str(v)
            for k, v in state.collected_slots.items()
        }

        pending_slots = [
            k for k in REQUIRED_SLOTS
            if state.slot_status.get(k, SlotCollectionStatus(key=k)).status != SlotStatus.COLLECTED
        ]
        print(f"pending_slots: {pending_slots}")
        print(f"slot_state: {slot_state}")
        print(f"intention.category: {intention.category}")
        print(f"intention.follow_up_question: {intention.follow_up_question}")

        # 3️⃣ 构造 prompt
        prompt = f"""
    你是中医问诊助手，需要通过对话完成患者信息采集
    建议继续询问的内容是：{intention.follow_up_question}

    【当前已收集信息】
    {slot_state}

    【还需要收集的槽位】
    {pending_slots}

    【用户输入】
    {message}

    请完成：
    1. 从用户输入中提取可以更新的槽位
    2. 更新槽位（只填有把握的）
    3. 生成一句自然的追问（优先收集未完成槽位）
    4. 每次针对某个部位或者某一个症状进行询问时，可以1到2个问题，其余情况禁止一次询问多个问题

    输出结构化结果
    """

        llm_result = await self.medical_consultation_agent.run(prompt)

        # 从 RunResponse 中提取结果
        logger.info(f"medical_consultation_agent result: {llm_result}")
        # response_model 会让 Agent 返回结构化数据
        consultation_result = None
        if hasattr(llm_result, 'parsed'):
            consultation_result = llm_result.parsed
        elif hasattr(llm_result, 'content'):
            # 如果没有 parsed，content 可能包含结构化文本
            consultation_result = llm_result.content

        # 解析槽位更新
        new_slots = {}
        reply = ""

        if consultation_result:
            if isinstance(consultation_result, ConsultationTurnResult):
                # 结构化响应
                new_slots = {s.field: s.value for s in consultation_result.slot_updates}
                reply = consultation_result.reply
            elif isinstance(consultation_result, str):
                # 文本响应，尝试简单提取
                reply = consultation_result

        # 如果 reply 为空，使用默认回复
        if not reply:
            reply = "能再详细说一下吗"

        for k, v in new_slots.items():
            if k in state.slot_status:
                state.collected_slots[k] = v
                state.slot_status[k].status = SlotStatus.COLLECTED
        logger.debug(f"已经收集的槽位置{state.collected_slots}")
        logger.debug(f"已经收集的槽位状态{state.slot_status}")

        # 7️⃣ 判断是否全部完成
        required_done = all(
            state.slot_status.get(k, SlotCollectionStatus(key=k)).status == SlotStatus.COLLECTED
            for k in REQUIRED_SLOTS
        )
        # 如果槽位收集完成，通知前端收集特殊槽位：舌照 / 面照 / 检查报告
        if consultation_result and consultation_result.control.next_action == "ask_image":
            return self._create_image_request_response(consultation_result.image_request, consultation_result.reply)
        
        if consultation_result and consultation_result.control.next_action == "finish":
            return await self._handle_supplementary_phase(message)
        return reply or "能再详细说一下吗"

    async def _handle_medical_consultation_stream(
        self,
        message: str,
        intention: IntentionResult,
        imgs: Optional[ChatImages]=None
    ) -> AsyncIterator[str]:
        """医疗问诊（多轮问答）- 流式版本

        注意：此函数会分块 yield 响应文本，用于流式输出
        """
        state = self.current_session.state

        # 问诊阶段
        if state.consultation_phase == ConsultationPhase.CONSULTATION:
            async for chunk in self._handle_consultation_phase_stream(message, intention, imgs):
                yield chunk

        # 补充信息阶段
        elif state.consultation_phase == ConsultationPhase.SUPPLEMENTARY:
            async for chunk in self._handle_supplementary_phase_stream(message):
                yield chunk

        # 完成阶段
        elif state.consultation_phase == ConsultationPhase.COMPLETE:
            async for chunk in self._handle_complete_phase_stream():
                yield chunk

        else:
            yield "系统状态异常"

    async def _handle_consultation_phase_stream(
        self,
        message: str,
        intention: IntentionResult,
        imgs: Optional[ChatImages]=None
    ) -> AsyncIterator[str]:
        """问诊阶段 - 流式版本"""
        state = self.current_session.state

        # 1️⃣ 判断是否结束
        if self._should_end_consultation(message.lower(), message):
            async for chunk in self._finish_consultation_stream():
                yield chunk
            return

        # 2️⃣ 处理上传的图片
        if imgs:
            await self._process_uploaded_images(imgs, state)

        slot_state = {
            k: v.value if hasattr(v, "value") else str(v)
            for k, v in state.collected_slots.items()
        }

        pending_slots = [
            k for k in REQUIRED_SLOTS
            if state.slot_status.get(k, SlotCollectionStatus(key=k)).status != SlotStatus.COLLECTED
        ]

        # 3️⃣ 构造 prompt
        prompt = f"""
    你是中医问诊助手，需要通过对话完成患者信息采集
    建议继续询问的内容是：{intention.follow_up_question}

    【当前已收集信息】
    {slot_state}

    【还需要收集的槽位】
    {pending_slots}

    【用户输入】
    {message}

    请完成：
    1. 从用户输入中提取可以更新的槽位
    2. 更新槽位（只填有把握的）
    3. 生成一句自然的追问（优先收集未完成槽位）
    4. 每次针对某个部位或者某一个症状进行询问时，可以1到2个问题，其余情况禁止一次询问多个问题

    输出结构化结果
    """

        # 非流式调用获取结果
        llm_result = await self.medical_consultation_agent.run(prompt)
        logger.info(f"medical_consultation_agent result: {llm_result}, type: {type(llm_result)}")

        # 解析结果
        if not llm_result:
            yield "系统繁忙，请稍后再试"
            return
        

        # 提取回复文本
        reply = ""
        new_slots = {}
        consultation_result = llm_result.content if isinstance(llm_result, RunResponse) else llm_result
        logger.info(f"consultation_result: {consultation_result}, type: {type(consultation_result)}")

        if isinstance(consultation_result, ConsultationTurnResult):
            new_slots = {s.field: s.value for s in consultation_result.slot_updates}
            reply = consultation_result.reply
        elif isinstance(consultation_result, str):
            reply = consultation_result

        if not reply:
            reply = "能再详细说一下吗"

        # 更新槽位
        for k, v in new_slots.items():
            if k in state.slot_status:
                state.collected_slots[k] = v
                state.slot_status[k].status = SlotStatus.COLLECTED

        # 检查控制流
        if consultation_result.control.next_action == "ask_image":
            response = self._create_image_request_response(
                consultation_result.image_request,
                consultation_result.reply,
            )
            # 流式输出
            for char in response:
                yield char
            return

        if consultation_result.control.next_action == "finish":
            async for chunk in self._handle_supplementary_phase_stream(message):
                yield chunk
            return

        # 流式输出回复
        for char in reply:
            yield char
            await asyncio.sleep(0.005)

    async def _handle_supplementary_phase_stream(self, message: str) -> AsyncIterator[str]:
        """补充信息阶段 - 流式版本"""
        state = self.current_session.state

        state.supplementary_info = message
        state.consultation_phase = ConsultationPhase.COMPLETE
        state.slot_status["supplementary"].status = SlotStatus.COLLECTED
        state.slot_status["supplementary"].value = message

        async for chunk in self._finish_consultation_stream():
            yield chunk

    async def _handle_complete_phase_stream(self) -> AsyncIterator[str]:
        """完成阶段 - 流式版本"""
        diagnosis_text = await self._generate_diagnosis()

        for char in diagnosis_text:
            yield char
            await asyncio.sleep(0.005)

    async def _handle_supplementary_phase(self, message: str) -> str:
        """补充信息阶段"""
        state = self.current_session.state

        state.supplementary_info = message
        state.consultation_phase = ConsultationPhase.COMPLETE
        state.slot_status["supplementary"].status = SlotStatus.COLLECTED
        state.slot_status["supplementary"].value = message

        # 结束问诊
        return await self._finish_consultation()

    async def _process_uploaded_images(self, imgs: ChatImages, state: ConsultationState):
        """处理上传的图片，根据类型调用不同的解析服务
        
        Args:
            imgs: 上传的图片数据（区分舌照、面照、检查报告）
            state: 问诊状态
        """
        # 舌照处理
        if imgs.tongue_imgs:
            state.tongue_image_url = imgs.tongue_imgs[0] if imgs.tongue_imgs else None
            state.tongue_analysis = await self._analyze_tongue(imgs.tongue_imgs)
            state.slot_status["tongue"].status = SlotStatus.COLLECTED
            state.slot_status["tongue"].value = {"url": state.tongue_image_url, "analysis": state.tongue_analysis}
            logger.info(f"Tongue image processed, analysis: {state.tongue_analysis[:50]}...")

        # 面照处理
        if imgs.face_imgs:
            state.face_image_url = imgs.face_imgs[0] if imgs.face_imgs else None
            state.face_analysis = await self._analyze_face(imgs.face_imgs)
            state.slot_status["face"].status = SlotStatus.COLLECTED
            state.slot_status["face"].value = {"url": state.face_image_url, "analysis": state.face_analysis}
            logger.info(f"Face image processed, analysis: {state.face_analysis[:50]}...")

        # 检查报告处理
        if imgs.check_imgs:
            state.exam_report_url = imgs.check_imgs[0] if imgs.check_imgs else None
            state.exam_report_summary = await self._analyze_exam_report(imgs.check_imgs)
            state.slot_status["report"].status = SlotStatus.COLLECTED
            state.slot_status["report"].value = {"url": state.exam_report_url, "summary": state.exam_report_summary}
            logger.info(f"Exam report processed, summary: {state.exam_report_summary[:50]}...")

    def _create_image_request_response(self, image_type: str, message: str) -> str:
        """创建带 image_request 标记的响应，用于通知前端需要上传哪种图片
        
        Args:
            image_type: 图片类型，可选值 "tongue" | "face" | "report"
            message: 返回给用户的消息
            
        Returns:
            格式化的响应字符串，前端可通过解析获取 image_request
        """
        # 将 image_request 信息附加到返回消息中
        # 前端可以通过解析响应来获取 image_type
        # 建议前端使用正则或字符串匹配来提取 image_request
        return f"[IMAGE_REQUEST:{image_type}]{message}"

    async def _analyze_tongue(self, imgs: List[str]) -> str:
        """舌照分析 - 调用视觉模型分析舌象
        
        Args:
            imgs: 舌照URL列表
            
        Returns:
            舌象分析结果，包含舌质、舌苔等特征描述
        """
        if not imgs:
            return ""

        # 构造分析提示词
        prompt = """请分析这张舌象照片，从中医角度描述：
1. 舌质颜色（淡红/红/绛/紫/淡白等）
2. 舌形（胖瘦、老嫩、裂纹、齿痕等）
3. 舌苔（薄厚、颜色、润燥、腐腻等）
4. 其他特征

请用简洁的中医术语描述。"""

        try:
            # 调用视觉模型进行分析
            # 这里使用 qwen-vl 或其他视觉模型
            result = await self._call_vision_model(imgs, prompt)
            return result
        except Exception as e:
            logger.error(f"Tongue analysis error: {e}")
            return f"舌象分析完成（分析服务暂时不可用）"

    async def _analyze_face(self, imgs: List[str]) -> str:
        """面照分析 - 调用视觉模型分析面色
        
        Args:
            imgs: 面照URL列表
            
        Returns:
            面部分析结果，包含面色、面部特征等描述
        """
        if not imgs:
            return ""

        prompt = """请分析这张面部照片，从中医望诊角度描述：
1. 面色（红润/苍白/萎黄/潮红/晦暗等）
2. 面部光泽（明润/晦暗/油腻等）
3. 特殊部位特征（眼袋、色斑、痤疮等）
4. 整体神态

请用简洁的中医术语描述。"""

        try:
            result = await self._call_vision_model(imgs, prompt)
            return result
        except Exception as e:
            logger.error(f"Face analysis error: {e}")
            return f"面部分析完成（分析服务暂时不可用）"

    async def _analyze_exam_report(self, imgs: List[str]) -> str:
        """检查报告分析 - OCR识别 + 结构化提取
        
        Args:
            imgs: 检查报告图片URL列表
            
        Returns:
            检查报告摘要，包含关键指标和异常值
        """
        if not imgs:
            return ""

        prompt = """请识别并分析这张检查报告：
1. 提取报告类型（血常规、尿常规、生化、影像等）
2. 列出关键指标和数值
3. 标注异常值（偏高/偏低）
4. 给出简要的健康建议（如有异常）

请用简洁、专业的语言描述。"""

        try:
            # 先进行 OCR 识别，再进行结构化提取
            ocr_result = await self._call_vision_model(imgs, prompt)
            return ocr_result
        except Exception as e:
            logger.error(f"Exam report analysis error: {e}")
            return f"检查报告分析完成（分析服务暂时不可用）"

    async def _call_vision_model(self, imgs: List[str], prompt: str) -> str:
        """调用视觉模型进行图片分析
        
        Args:
            imgs: 图片URL列表
            prompt: 分析提示词
            
        Returns:
            视觉模型的分析结果
        """
        from agentica import QwenVLChat

        # 使用视觉模型进行分析
        vision_model = QwenVLChat(id="qwen-vl-plus")

        # 构建多图消息
        image_contents = []
        for img_url in imgs:
            image_contents.append({"type": "image_url", "image_url": {"url": img_url}})

        messages = [
            {"role": "user", "content": [{"type": "text", "text": prompt}] + image_contents}
        ]

        try:
            response = await vision_model.ainvoke(messages)
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            logger.error(f"Vision model call error: {e}")
            raise
    
    async def _handle_complete_phase(self) -> str:
        """完成阶段"""
        return "问诊已完成，请查看上方诊断结果。"
    
    async def _finish_consultation(self) -> str:
        """结束问诊，生成诊断和病历"""
        state = self.current_session.state
        state.consultation_phase = ConsultationPhase.COMPLETE

        # 生成诊断
        diagnosis_response = await self._generate_diagnosis()

        # 异步生成结构化病历
        asyncio.create_task(self._generate_consultation_record())

        return diagnosis_response

    async def _finish_consultation_stream(self) -> AsyncIterator[str]:
        """结束问诊 - 流式版本"""
        state = self.current_session.state
        state.consultation_phase = ConsultationPhase.COMPLETE

        # 先发送提示
        yield "正在生成诊断结果，请稍候...\n\n"

        # 生成诊断
        diagnosis_text = await self._generate_diagnosis()

        # 流式输出诊断
        for char in diagnosis_text:
            yield char
            await asyncio.sleep(0.005)

        # 异步生成结构化病历
        asyncio.create_task(self._generate_consultation_record())
    
    def _should_end_consultation(self, msg_lower: str, message: str) -> bool:
        """判断是否要结束问诊"""
        # TODO: 判断是否满足需要提前终止问诊的case
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
        
        result = await self.diagnosis_agent.run(prompt)
        
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
            return "您已结束问诊，感谢您使用！"
        
        elif reason == ConsultationInterruptReason.ABNORMAL_ERROR:
            logger.error(f"Consultation interrupted: {error}")
            return f"问诊过程中出现错误：{error}\n\n请重新开始问诊。"
        
        return "问诊已结束。"
