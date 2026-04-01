# -*- coding: utf-8 -*-
"""
Intention Recognition Agent
意图识别 Agent

功能：
1. 识别用户意图类型
2. 提取关键实体信息
3. 生成追问问题
4. 提供响应建议
"""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from agentica import Agent, QwenChat 
from agentica.model.message import UserMessage

from tcm_agent.models import IntentionType, IntentionResult, PatientInfo, SymptomInfo


class IntentionRecognitionAgent:
    """
    意图识别 Agent
    
    基于大语言模型的意图识别，用于分析用户输入并确定：
    - 用户意图类型
    - 关键实体和症状
    - 后续交互策略
    """
    
    SYSTEM_PROMPT = """你是一个专业的中医问诊系统意图识别专家。你的任务是根据用户的输入准确识别其意图类型。

## 可识别的意图类型：
1. greeting - 问候（如：你好、早上好）
2. symptom - 描述症状（如：我头疼、我最近失眠）
3. inquiry - 询问症状（如：这是什么原因？严重吗？）
4. diagnosis - 请求诊断（如：帮我看看我是什么问题、我这是怎么了）
5. treatment - 询问治疗方案（如：怎么治疗？吃什么药好？）
6. medicine - 询问药物（如：这个药怎么服用？有什么副作用？）
7. prevention - 询问预防（如：怎么预防？平时要注意什么？）
8. advice - 询问养生建议（如：平时该怎么调养？）
9. follow_up - 继续对话（如：还有呢？然后呢？）
10. goodbye - 结束对话（如：谢谢、再见）
11. other - 其他意图

## 识别策略：
1. 仔细分析用户输入的语义
2. 注意上下文线索（如多轮对话）
3. 考虑中医问诊的特定场景
4. 当难以判断时，选择最可能的意图类型

## 输出要求：
返回一个结构化的意图识别结果，包括：
- 意图类型（必须是上述11种之一）
- 置信度（0.0-1.0）
- 提取的实体信息（如症状、部位、持续时间等）
- 追问问题（如果需要更多信息）
- 建议回复（如果适用）

请以JSON格式输出你的分析结果。
"""
    
    def __init__(
        self,
        model: Optional[Any] = None,
        temperature: float = 0.1
    ):
        """
        初始化意图识别 Agent
        
        Args:
            model: LLM 模型，默认使用 OpenAI gpt-4o-mini
            temperature: 生成温度
        """
        self.model = model or QwenChat(id="qwen-plus", temperature=temperature)
        self.agent = Agent(
            model=self.model,
            name="IntentRecognitionAgent",
            instructions=self.SYSTEM_PROMPT,
            response_model=IntentionResult,
            add_history_to_messages=True,
        )
    
    async def recognize(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> IntentionResult:
        """
        识别用户意图
        
        Args:
            user_input: 用户输入
            context: 上下文信息（可选）
            
        Returns:
            IntentionResult: 意图识别结果
        """
        prompt = self._build_prompt(user_input, context)
        
        result = await self.agent.run(prompt)
        return result.content
    
    def _build_prompt(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> str:
        """构建提示词"""
        prompt_parts = [
            f"用户输入：{user_input}"
        ]
        
        if context:
            if context.get("conversation_phase"):
                prompt_parts.append(f"当前问诊阶段：{context['conversation_phase']}")
            if context.get("collected_symptoms"):
                prompt_parts.append(f"已收集的症状：{', '.join(context['collected_symptoms'])}")
            if context.get("previous_intention"):
                prompt_parts.append(f"上一次意图：{context['previous_intention']}")
        
        prompt_parts.append("\n请分析以上输入，识别用户意图并返回结构化的分析结果。")
        
        return "\n".join(prompt_parts)
    
    def recognize_sync(self, user_input: str, context: Optional[Dict[str, Any]] = None) -> IntentionResult:
        """同步版本的意图识别"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.recognize(user_input, context))
                    return future.result()
            else:
                return loop.run_until_complete(self.recognize(user_input, context))
        except RuntimeError:
            return asyncio.run(self.recognize(user_input, context))


class SymptomExtractor:
    """
    症状提取器
    
    从用户输入中提取症状信息，包括：
    - 症状名称
    - 部位
    - 严重程度
    - 持续时间
    - 发作频率
    - 诱因
    """
    
    SYSTEM_PROMPT = """你是一个专业的中医症状分析师。你的任务是从用户的描述中提取详细的症状信息。

## 提取规则：
1. 症状名称：标准化症状名称（如"头疼"→"头痛"）
2. 部位：如果是局部症状，标注部位（头、胸、腹、四肢等）
3. 严重程度：1-5分，1最轻，5最重
4. 持续时间：如"几天"、"几个月"、"长期"等
5. 发作频率：如"偶尔"、"经常"、"每天"等
6. 诱因：如"生气后"、"熬夜后"、"受凉后"等
7. 伴随症状：同时出现的其他症状

## 中医症状分类参考：
- 全身症状：乏力、疲劳、发热、盗汗、自汗、消瘦、肥胖
- 头部症状：头痛、头晕、头重、耳鸣、目眩
- 胸部症状：胸闷、胸痛、心悸、咳嗽、气喘
- 腹部症状：腹痛、腹胀、恶心、呕吐、腹泻、便秘
- 情志症状：烦躁、易怒、抑郁、焦虑、失眠、多梦
- 舌脉特征：舌质淡红/红/紫、舌苔薄白/黄腻、脉浮/沉/数/迟

## 输出要求：
返回一个JSON数组，每个元素包含一个症状的详细信息。
如果用户没有描述症状，返回空数组。

请以JSON格式输出。
"""
    
    def __init__(
        self,
        model: Optional[Any] = None,
        temperature: float = 0.1
    ):
        self.model = model or QwenChat(id="qwen-plus", temperature=temperature)
        self.agent = Agent(
            model=self.model,
            name="SymptomExtractor",
            instructions=self.SYSTEM_PROMPT,
            response_model=List[SymptomInfo],
            add_history_to_messages=False,
        )
    
    async def extract(self, user_input: str) -> List[SymptomInfo]:
        """
        提取症状信息
        
        Args:
            user_input: 用户输入
            
        Returns:
            List[SymptomInfo]: 提取的症状列表
        """
        prompt = f"用户描述：{user_input}\n\n请提取其中的症状信息，以JSON数组格式返回。"
        
        result = await self.agent.run(prompt)
        return result.content
    
    def extract_sync(self, user_input: str) -> List[SymptomInfo]:
        """同步版本"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.extract(user_input))
                    return future.result()
            else:
                return loop.run_until_complete(self.extract(user_input))
        except RuntimeError:
            return asyncio.run(self.extract(user_input))


class PatientInfoExtractor:
    """
    患者信息提取器
    
    从用户输入中提取患者基本信息：
    - 姓名
    - 年龄
    - 性别
    - 职业
    - 既往病史
    - 过敏史
    """
    
    SYSTEM_PROMPT = """你是一个专业的中医问诊信息收集助手。你的任务是从用户的描述中提取患者的基本信息。

## 提取规则：
1. 姓名：从称呼中提取
2. 年龄：注意用户可能用"今年30"、"30岁"等形式描述
3. 性别：先生/女士、他/她等代词
4. 职业：注意用户可能提到的职业信息
5. 既往病史：用户提到的既往疾病
6. 过敏史：用户提到的过敏情况
7. 体质：用户可能提到的体质特点

## 输出要求：
返回一个JSON对象，包含患者的基本信息。如果某项信息未提及，设为null。

请以JSON格式输出。
"""
    
    def __init__(
        self,
        model: Optional[Any] = None,
        temperature: float = 0.1
    ):
        self.model = model or QwenChat(id="qwen-plus", temperature=temperature)
        self.agent = Agent(
            model=self.model,
            name="PatientInfoExtractor",
            instructions=self.SYSTEM_PROMPT,
            response_model=PatientInfo,
            add_history_to_messages=False,
        )
    
    async def extract(self, user_input: str, existing_info: Optional[PatientInfo] = None) -> PatientInfo:
        """
        提取患者信息
        
        Args:
            user_input: 用户输入
            existing_info: 已有的患者信息（用于补充）
            
        Returns:
            PatientInfo: 患者信息
        """
        prompt = f"用户描述：{user_input}"
        
        if existing_info:
            existing_parts = []
            if existing_info.name:
                existing_parts.append(f"姓名：{existing_info.name}")
            if existing_info.age:
                existing_parts.append(f"年龄：{existing_info.age}")
            if existing_info.gender:
                existing_parts.append(f"性别：{existing_info.gender}")
            if existing_parts:
                prompt += f"\n已知信息：{', '.join(existing_parts)}"
        
        prompt += "\n\n请提取患者的基本信息。"
        
        result = await self.agent.run(prompt)
        
        merged_info = result.content
        if existing_info:
            merged_info = self._merge_patient_info(existing_info, merged_info)
        
        return merged_info
    
    def _merge_patient_info(
        self,
        existing: PatientInfo,
        new: PatientInfo
    ) -> PatientInfo:
        """合并患者信息"""
        return PatientInfo(
            name=new.name or existing.name,
            age=new.age or existing.age,
            gender=new.gender or existing.gender,
            occupation=new.occupation or existing.occupation,
            constitution=new.constitution or existing.constitution,
            medical_history=list(set(existing.medical_history + new.medical_history)),
            family_history=list(set(existing.family_history + new.family_history)),
            current_medications=list(set(existing.current_medications + new.current_medications)),
            allergies=list(set(existing.allergies + new.allergies)),
        )
    
    def extract_sync(self, user_input: str, existing_info: Optional[PatientInfo] = None) -> PatientInfo:
        """同步版本"""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.extract(user_input, existing_info))
                    return future.result()
            else:
                return loop.run_until_complete(self.extract(user_input, existing_info))
        except RuntimeError:
            return asyncio.run(self.extract(user_input, existing_info))
