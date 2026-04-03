# -*- coding: utf-8 -*-
"""
TCM Diagnosis Agent - 多轮问诊 Agent
中医问诊 Agent

功能：
1. 多轮对话管理
2. 症状收集
3. 辨证论治
4. 治疗方案生成
5. 养生建议
"""
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime

from agentica import Agent, QwenChat
from agentica.model.message import UserMessage, AssistantMessage

from tcm_agent.models import (
    ConsultationState,
    ConsultationPhase,
    SymptomInfo,
    SymptomLocation,
    PatientInfo,
    PhysicalInfo,
    DiagnosisInfo,
    TreatmentPlan,
    SyndromeType,
)
from tcm_agent.knowledge import TCMKnowledgeBase
from tcm_agent.intention import IntentionRecognitionAgent, PatientInfoExtractor
from log import logger


class TCMDiagnosisAgent:
    """
    中医问诊 Agent
    
    核心组件：
    - 状态管理：管理多轮问诊的状态
    - 对话策略：根据当前阶段和意图生成响应
    - 知识检索：结合知识图谱提供专业建议
    - 辨证论治：基于收集的信息进行辨证分析
    """
    
    WELCOME_MESSAGE = """您好！欢迎来到中医智能问诊系统。

我是您的中医健康助手，可以帮助您：
- 了解和分析您的健康症状
- 提供中医辨证建议
- 给出养生调理方案

为了更好地为您提供服务，我会通过几个简单的问题了解您的情况。

请问您今天是来看什么问题的？有什么不舒服的地方吗？"""
    
    
    def __init__(
        self,
        model: Optional[Any] = None,
        knowledge_base: Optional[TCMKnowledgeBase] = None,
        temperature: float = 0.7,
        enable_stream: bool = True,
    ):
        """
        初始化中医问诊 Agent
        
        Args:
            model: LLM 模型
            knowledge_base: 知识库
            temperature: 生成温度
            enable_stream: 是否启用流式输出
        """
        self.model = model or QwenChat(id="qwen-plus")
        self.knowledge_base = knowledge_base or TCMKnowledgeBase()
        self.knowledge_base.initialize()
        
        # 为不同的 Agent 创建独立的 model 实例，避免 response_format 相互覆盖
        intention_model = model or QwenChat(id="qwen-plus")
        symptom_model = QwenChat(id="qwen-plus")
        patient_model = QwenChat(id="qwen-plus")
        conversation_model = QwenChat(id="qwen-plus")
        
        self.intention_agent = IntentionRecognitionAgent(model=intention_model, temperature=0.1)
        self.patient_info_extractor = PatientInfoExtractor(model=patient_model, temperature=0.1)
        
        self.state = ConsultationState()
        self.conversation_agent = self._create_conversation_agent(conversation_model, temperature)
    
    def _create_conversation_agent(self, model: Any, temperature: float) -> Agent:
        """创建对话 Agent"""
        return Agent(
            model=model,
            name="TCMConsultationAgent",
            instructions=self._build_system_prompt(),
            add_history_to_messages=True,
            history_window=10,
        )
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业、温和、有爱心的中医健康顾问。

## 你的角色：
- 深入理解中医理论，能够进行辨证论治
- 通过友好、耐心的对话收集患者信息
- 提供专业、易懂的中医健康建议
- 遵循中医"治未病"的理念，给出养生指导

## 问诊流程：
1. 欢迎患者，建立信任关系
2. 收集基本信息（年龄、性别等）
3. 详细了解症状（部位、时间、特点、伴随症状等）
4. 必要时询问舌脉情况
5. 进行辨证分析
6. 给出治疗方案和养生建议

## 沟通原则：
1. 温和亲切，用"您"称呼
2. 解释专业术语时使用通俗语言
3. 引导患者详细描述症状
4. 适时给予安慰和鼓励
5. 建议明确但不替代医疗诊断

## 重要提醒：
- 不要给出具体的药物处方（这是中医师的职责）
- 可以建议就医的指征（如症状严重、持续不缓解等）
- 强调生活调理和预防的重要性

## 当前问诊阶段信息：
{phase_info}

## 已收集的患者信息：
{patient_info}

## 已收集的症状：
{symptoms}

请根据当前状态，继续与患者进行友好、专业的对话。
"""
    
    async def run(self, user_input: str) -> str:
        """
        处理用户输入
        
        Args:
            user_input: 用户输入
            
        Returns:
            str: Agent 响应
        """
        context = self._get_context()
        logger.info(f"tcm Context: {context}")
        intention_result = await self.intention_agent.recognize(user_input, context)
        logger.info(f"Intention result: {intention_result}")
        self.state.intention = intention_result.intention
        self._add_to_history("user", user_input)
        
        response = await self._generate_response(user_input, intention_result)
        logger.info(f"diagnosis Response: {response}")
        self._add_to_history("assistant", response)
        self._update_phase()
        
        return response
    
    async def run_stream(self, user_input: str):
        """
        流式处理用户输入
        
        Args:
            user_input: 用户输入
            
        Yields:
            str: Agent 响应的增量内容
        """
        context = self._get_context()
        intention_result = await self.intention_agent.recognize(user_input, context)
        
        self.state.intention = intention_result.intention
        self._add_to_history("user", user_input)
        
        async for chunk in self._generate_response_stream(user_input, intention_result):
            yield chunk
        
        self._update_phase()
    
    async def _generate_response(
        self,
        user_input: str,
        intention_result: Any
    ) -> str:
        """生成响应"""
        symptoms_raw = await self.symptom_extractor.extract(user_input)
        logger.info(f"symptoms: {symptoms_raw}")
        symptoms = self._normalize_symptoms(symptoms_raw)
        for symptom in symptoms:
            if symptom.name not in [s.name for s in self.state.symptoms]:
                self.state.symptoms.append(symptom)
        
        patient_info = await self.patient_info_extractor.extract(
            user_input,
            self.state.patient_info
        )
        self.state.patient_info = patient_info
        
        intention_value = self._get_intention_value(intention_result.intention)
        
        if intention_value == "greeting":
            return self.WELCOME_MESSAGE
        
        elif intention_value == "goodbye":
            self.state.is_complete = True
            return "感谢您的咨询，祝您身体健康！如果有任何问题，欢迎随时来问诊。"
        
        elif intention_value == "diagnosis":
            return await self._generate_diagnosis_response()
        
        elif intention_value == "treatment":
            return await self._generate_treatment_response()
        
        elif len(self.state.symptoms) < 3 and self._get_phase_value(self.state.consultation_phase) in [
            "welcome",
            "symptom_inquiry"
        ]:
            return await self._generate_symptom_collection_response(intention_result)
        
        else:
            return await self._generate_follow_up_response(intention_result)
    
    async def _generate_response_stream(self, user_input: str, intention_result: Any):
        """流式生成响应"""
        symptoms_raw = await self.symptom_extractor.extract(user_input)
        symptoms = self._normalize_symptoms(symptoms_raw)
        for symptom in symptoms:
            if symptom.name not in [s.name for s in self.state.symptoms]:
                self.state.symptoms.append(symptom)
        
        patient_info = await self.patient_info_extractor.extract(
            user_input,
            self.state.patient_info
        )
        self.state.patient_info = patient_info
        
        response = await self._generate_response(user_input, intention_result)
        self._add_to_history("assistant", response)
        
        yield response
    
    def _normalize_symptoms(self, symptoms_input: Any) -> List[SymptomInfo]:
        """
        标准化症状输入，确保返回 List[SymptomInfo]
        
        Args:
            symptoms_input: 可能的症状数据（可能是字符串、字典、SymptomInfo对象等）
            
        Returns:
            List[SymptomInfo]: 标准化的症状列表
        """
        if not symptoms_input:
            return []
        
        result = []
        items = symptoms_input if isinstance(symptoms_input, list) else [symptoms_input]
        
        for item in items:
            try:
                if isinstance(item, SymptomInfo):
                    result.append(item)
                elif isinstance(item, dict):
                    # 处理 location 字段，确保是枚举值或 None
                    processed_item = item.copy()
                    if processed_item.get('location') is not None and isinstance(processed_item['location'], str):
                        try:
                            processed_item['location'] = SymptomLocation(processed_item['location'])
                        except ValueError:
                            processed_item['location'] = None
                    result.append(SymptomInfo(**processed_item))
                elif isinstance(item, str):
                    result.append(SymptomInfo(name=item))
            except Exception as e:
                logger.warning(f"Failed to convert symptom item: {item}, error: {e}")
                continue
        
        return result
    
    async def _generate_symptom_collection_response(self, intention_result: Any) -> str:
        """生成症状收集引导响应"""
        symptom_names = [s.name for s in self.state.symptoms]
        
        inquiry_questions = {
            "duration": "这个症状持续多长时间了？",
            "severity": "严重程度如何？是一直这样还是时好时坏？",
            "triggers": "有什么诱因吗？比如生气、劳累、受凉后？",
            "accompanying": "还有其他不舒服的地方吗？",
        }
        
        prompt = self._build_agent_prompt()
        prompt += f"""
        
当前已收集的症状：{', '.join(symptom_names) if symptom_names else '暂无'}
已识别的意图：{self._get_intention_value(intention_result.intention)}，置信度：{intention_result.confidence:.2f}

请根据以下策略生成回复：
1. 如果症状不足3个，继续引导患者描述更多症状
2. 选择一个最需要追问的方面提问
3. 保持温和、耐心的语气
4. 避免重复已经问过的问题
"""
        
        result = await self.conversation_agent.run(prompt)
        return result.content
    
    async def _generate_diagnosis_response(self) -> str:
        """生成辨证分析响应"""
        if len(self.state.symptoms) < 2:
            return "为了给您更准确的建议，我需要先了解更多症状信息。请您描述一下您的具体症状。"
        
        self.state.consultation_phase = ConsultationPhase.DIFFERENTIAL
        
        symptom_names = [s.name for s in self.state.symptoms]
        kg_results = self.knowledge_base.query_by_symptoms(symptom_names, max_results=3)
        
        diagnosis = self._perform_differential_diagnosis(kg_results)
        self.state.diagnosis = diagnosis
        
        response = f"""根据您描述的情况，我来进行辨证分析：

**主要症状**：{', '.join(symptom_names)}

**辨证结果**：{diagnosis.syndrome_description}

**病机分析**：{diagnosis.pathogenesis}

**治疗原则**：{diagnosis.recommendation}
"""
        
        return response
    
    async def _generate_treatment_response(self) -> str:
        """生成治疗方案响应"""
        if not self.state.diagnosis:
            await self._generate_diagnosis_response()
        
        syndrome_name = self._get_intention_value(self.state.diagnosis.syndrome) if self.state.diagnosis.syndrome else "虚证"
        
        patient_info_dict = {
            "age": self.state.patient_info.age,
            "gender": self._get_intention_value(self.state.patient_info.gender) if self.state.patient_info.gender else None,
            "constitution": self.state.patient_info.constitution,
        }
        
        treatment = self.knowledge_base.get_treatment_recommendations(
            syndrome_name,
            patient_info_dict
        )
        
        self.state.treatment_plan = TreatmentPlan(
            principle=treatment.get("syndrome_analysis", {}).get("category", "调理"),
            lifestyle_advice=treatment.get("lifestyle_advice", []),
            diet_advice=treatment.get("diet_advice", []),
            precautions=treatment.get("precautions", []),
            follow_up_advice="建议1-2周后复诊观察效果"
        )
        
        self.state.consultation_phase = ConsultationPhase.TREATMENT_PLAN
        
        response = "根据您的体质和症状，我为您提供以下调理方案：\n\n"
        
        if treatment.get("treatment_plan", {}).get("herbal_prescriptions"):
            prescriptions = treatment["treatment_plan"]["herbal_prescriptions"]
            response += "**中药调理建议**：\n"
            for p in prescriptions[:2]:
                response += f"- {p['name']}：{p.get('indication', '调理身体')}"
                if p.get('composition'):
                    response += f"\n  组成：{', '.join(p['composition'])}"
                response += "\n"
        
        if treatment.get("lifestyle_advice"):
            response += "\n**生活调理建议**：\n"
            for advice in treatment["lifestyle_advice"][:5]:
                response += f"- {advice}\n"
        
        if treatment.get("diet_advice"):
            response += "\n**饮食建议**：\n"
            for advice in treatment["diet_advice"][:5]:
                response += f"- {advice}\n"
        
        if treatment.get("precautions"):
            response += "\n**注意事项**：\n"
            for p in treatment["precautions"][:3]:
                response += f"- {p}\n"
        
        return response
    
    async def _generate_follow_up_response(self, intention_result: Any) -> str:
        """生成随访/继续对话响应"""
        prompt = self._build_agent_prompt()
        prompt += f"""
        
用户意图：{self._get_intention_value(intention_result.intention)}
意图置信度：{intention_result.confidence:.2f}

当前症状：{[s.name for s in self.state.symptoms]}

请根据用户意图生成合适的回复：
- 如果是追问症状，给出专业的解释
- 如果是咨询问题，提供帮助
- 如果想了解更多，鼓励继续描述
"""
        
        result = await self.conversation_agent.run(prompt)
        return result.content
    
    def _perform_differential_diagnosis(self, kg_results: List[Dict[str, Any]]) -> DiagnosisInfo:
        """进行辨证分析"""
        if kg_results:
            top_result = kg_results[0]
            syndrome_info = top_result.get("syndrome", {})
            
            syndrome_name = syndrome_info.get("name", "其他")
            syndrome_description = syndrome_info.get("description", "")
            
            category = syndrome_info.get("category", "")
            related_organs = syndrome_info.get("related_organs", [])
            common_symptoms = syndrome_info.get("common_symptoms", [])
            
            pathogenesis = self._generate_pathogenesis(
                syndrome_name,
                category,
                related_organs,
                [s.name for s in self.state.symptoms]
            )
            
            try:
                syndrome_type = SyndromeType(syndrome_name)
            except ValueError:
                syndrome_type = SyndromeType.OTHER
            
            return DiagnosisInfo(
                syndrome=syndrome_type,
                syndrome_description=f"{syndrome_name}（{category}）：{syndrome_description}",
                pathogenesis=pathogenesis,
                differential_diagnosis=[],
                recommendation=f"治法：{self._get_treatment_principle(syndrome_name)}"
            )
        
        return DiagnosisInfo(
            syndrome=SyndromeType.OTHER,
            syndrome_description="综合分析",
            pathogenesis="根据您描述的症状，难以确定具体证型，建议进一步详细描述或咨询专业中医师。",
            differential_diagnosis=[],
            recommendation="建议：详细描述症状，或咨询专业中医师进行面诊。"
        )
    
    def _generate_pathogenesis(
        self,
        syndrome_name: str,
        category: str,
        related_organs: List[str],
        symptoms: List[str]
    ) -> str:
        """生成病机分析"""
        pathogenesis_templates = {
            "虚证": "{symptoms}，多因{organs}功能不足所致，属于{category}。",
            "实证": "{symptoms}，多因邪气盛实、气机阻滞所致，属于{category}。",
            "热证": "{symptoms}，多因热邪内扰、阴液不足所致，属于{category}。",
            "寒证": "{symptoms}，多因寒邪侵袭、阳气受阻所致，属于{category}。",
        }
        
        template = pathogenesis_templates.get(
            category,
            "{symptoms}，病机复杂，需辨证论治。"
        )
        
        organs_str = "、".join(related_organs) if related_organs else "相关脏腑"
        symptoms_str = "、".join(symptoms[:3]) if symptoms else "症状"
        
        return template.format(
            symptoms=symptoms_str,
            organs=organs_str,
            category=category
        )
    
    def _get_treatment_principle(self, syndrome_name: str) -> str:
        """获取治疗原则"""
        principles = {
            "阴虚": "滋阴补肾",
            "阳虚": "温阳散寒",
            "气虚": "补气健脾",
            "血虚": "养血补血",
            "痰湿": "化痰祛湿",
            "气郁": "疏肝解郁",
            "血瘀": "活血化瘀",
            "心火": "清心泻火",
            "肝火": "清肝泻火",
        }
        
        for key, principle in principles.items():
            if key in syndrome_name:
                return principle
        
        return "调理脏腑"
    
    def _build_agent_prompt(self) -> str:
        """构建 Agent 提示词"""
        phase_info = self._get_phase_value(self.state.consultation_phase)
        
        patient_info_parts = []
        if self.state.patient_info.age:
            patient_info_parts.append(f"年龄：{self.state.patient_info.age}")
        if self.state.patient_info.gender:
            patient_info_parts.append(f"性别：{self._get_intention_value(self.state.patient_info.gender)}")
        
        symptoms_parts = [s.name for s in self.state.symptoms]
        
        return self._build_system_prompt().format(
            phase_info=phase_info,
            patient_info=', '.join(patient_info_parts) if patient_info_parts else "待收集",
            symptoms=', '.join(symptoms_parts) if symptoms_parts else "暂无"
        )
    
    def _get_context(self) -> Dict[str, Any]:
        """获取上下文信息"""
        intention_value = self._get_intention_value(self.state.intention)
        return {
            "conversation_phase": self._get_phase_value(self.state.consultation_phase),
            "collected_symptoms": [s.name for s in self.state.symptoms],
            "previous_intention": intention_value if intention_value != "other" else None,
            "patient_age": self.state.patient_info.age,
            "patient_gender": self._get_intention_value(self.state.patient_info.gender) if self.state.patient_info.gender else None,
        }
    
    def _get_intention_value(self, intention: Any) -> str:
        """安全获取意图值，处理字符串或枚举对象"""
        if isinstance(intention, str):
            return intention
        if hasattr(intention, 'value'):
            return intention.value
        return str(intention)
    
    def _get_phase_value(self, phase: Any) -> str:
        """安全获取阶段值，处理字符串或枚举对象"""
        if isinstance(phase, str):
            return phase
        if hasattr(phase, 'value'):
            return phase.value
        return str(phase)
    
    def _add_to_history(self, role: str, content: str) -> None:
        """添加对话历史"""
        self.state.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def _update_phase(self) -> None:
        """更新问诊阶段"""
        current_phase = self._get_phase_value(self.state.consultation_phase)
        welcome_phase = self._get_phase_value(ConsultationPhase.WELCOME)
        symptom_phase = self._get_phase_value(ConsultationPhase.SYMPTOM_INQUIRY)
        tongue_phase = self._get_phase_value(ConsultationPhase.TONGUE_PULSE)
        differential_phase = self._get_phase_value(ConsultationPhase.DIFFERENTIAL)
        
        if current_phase == welcome_phase:
            if len(self.state.symptoms) > 0:
                self.state.consultation_phase = ConsultationPhase.SYMPTOM_INQUIRY
        
        elif current_phase == symptom_phase:
            if len(self.state.symptoms) >= 3:
                self.state.consultation_phase = ConsultationPhase.TONGUE_PULSE
        
        elif current_phase == tongue_phase:
            self.state.consultation_phase = ConsultationPhase.DIFFERENTIAL
        
        self.state.updated_at = datetime.now()
    
    def get_state(self) -> ConsultationState:
        """获取当前状态"""
        return self.state
    
    def reset(self) -> None:
        """重置问诊状态"""
        self.state = ConsultationState()
    
    def run_sync(self, user_input: str) -> str:
        """同步版本"""
        import asyncio
        return asyncio.run(self.run(user_input))
