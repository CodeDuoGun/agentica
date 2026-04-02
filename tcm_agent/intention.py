# -*- coding: utf-8 -*-
"""
Intention Recognition Agent
意图识别 Agent

功能：
1. 识别用户意图类别（普通咨询/问诊咨询/非医疗咨询）
2. 意图改写和上下文理解
3. 提取关键实体信息
4. 生成响应建议
"""
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from agentica import Agent, QwenChat 
from agentica.model.message import UserMessage

from tcm_agent.models import IntentionCategory, ConsultationVisitType, IntentionResult, PatientInfo, SymptomInfo


# 医疗相关关键词
MEDICAL_KEYWORDS = [
    "症状", "不舒服", "疼", "痛", "痒", "发烧", "咳嗽", "感冒", "头痛", "头晕",
    "失眠", "睡眠", "消化", "胃", "肚子", "腹泻", "便秘", "恶心", "呕吐",
    "血压", "血糖", "体质", "中医", "中药", "调理", "养生", "湿气", "气血",
    "肝", "肾", "脾", "心", "肺", "妇科", "儿科", "皮肤", "骨科", "内科",
    "门诊", "挂号", "就诊", "医生", "看病", "检查", "体检", "报告"
]

# 非医疗关键词
NON_MEDICAL_KEYWORDS = [
    "股票", "基金", "投资", "赚钱", "天气", "新闻", "娱乐", "明星", "电影",
    "游戏", "电竞", "购物", "电商", "物流", "快递", "美食", "餐厅", "旅游",
    "酒店", "机票", "装修", "房产", "汽车", "手机", "电脑", "编程", "代码"
]


class IntentionRecognitionAgent:
    """
    意图识别 Agent
    
    根据用户输入识别意图类别：
    1. general_medical - 普通医疗问题咨询（用药咨询、病种咨询等）→ 主动推荐挂号地址
    2. consultation - 问诊咨询（症状描述等）→ 进入问诊流程
    3. non_medical - 非医疗咨询 → 不回复
    """
    
    SYSTEM_PROMPT = """你是一个专业的中医问诊系统意图识别专家。你的任务是根据用户的输入准确识别其意图类型。

## 意图分类体系：

### 1. general_medical（普通医疗问题咨询）
- 用药咨询：如"这个药怎么吃"、"中药有什么副作用"
- 病种咨询：如"高血压要注意什么"、"糖尿病饮食"
- 检查结果咨询：如"我的体检报告怎么看"
- 预防保健：如"怎么提高免疫力"、"春天养生"
→ 处理方式：回答问题 + 主动推荐挂号地址

### 2. consultation（问诊咨询）
- 症状描述：如"我最近头疼"、"失眠很久了"
- 身体不适：如"感觉浑身没力气"、"胃口不好"
- 既往病史：如"我有胃病，现在又犯了"
- 要求诊断：如"帮我看看是什么问题"
→ 处理方式：进入问诊流程

### 3. other（其他问题）
- 完全无关话题：如天气、股票、新闻、游戏等
- 政治敏感话题
- 纯粹闲聊无医疗诉求
→ 处理方式：不回复

## 识别策略：
1. 首先判断是否涉及医疗健康领域
2. 如果是医疗领域，判断是咨询类还是问诊类
3. 咨询类：一般有明确的问答结构，问题相对独立
4. 问诊类：涉及症状描述，需要多轮问答收集信息
5. 考虑上下文：如果用户正在描述症状，优先归类为问诊

## 输出要求：
返回JSON格式的意图识别结果：
{
    "category": "general_medical" | "consultation" | "other",
    "intention": "具体意图描述",
    "confidence": 0.0-1.0,
    "entities": {提取的实体信息},
    "follow_up_question": "追问问题（如需要）",
    "should_forward_to_consultation": true | false,
}

重要：
- 非医疗咨询的回复内容应为null
- 置信度低于0.5时，优先判断为other
"""
    
    def __init__(
        self,
        model: Optional[Any] = None,
        temperature: float = 0.1
    ):
        """
        初始化意图识别 Agent
        
        Args:
            model: LLM 模型
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
            if context.get("turn_count"):
                prompt_parts.append(f"当前对话轮数：{context['turn_count']}")
            if context.get("recent_messages"):
                recent_messages = ""
                for msg in context.get("recent_messages"):
                    recent_messages += f"角色:{msg['role']},内容:{msg["content"]}\n"
                prompt_parts.append(f"对话历史:{recent_messages}")
        
        prompt_parts.append("\n请分析以上输入，结合上下文识别用户意图并返回结构化的分析结果。")
        
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


class BasicInfoExtractor:
    """
    基本信息提取 Agent
    
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
        """提取患者信息"""
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
            # past_history=list(set(existing.past_history + new.past_history)),
            # family_history=list(set(existing.family_history + new.family_history)),
            # current_medications=list(set(existing.current_medications + new.current_medications)),
            # allergies=list(set(existing.allergies + new.allergies)),
            # marriage_history=list(set(existing.marriage_history + new.marriage_history)),
            # personal_history=list(set(existing.personal_history + new.personal_history)),
            # primary_symptoms=list(set(existing.primary_symptoms + new.primary_symptoms)),
            # secondary_symptoms=list(set(existing.secondary_symptoms + new.secondary_symptoms)),

            
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


# 向后兼容旧接口
PatientInfoExtractor = BasicInfoExtractor
