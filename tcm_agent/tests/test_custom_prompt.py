# -*- coding: utf-8 -*-
"""
TCM Agent - 自定义提示词示例
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from agentica import Agent, QwenChat
from tcm_agent import TCMDiagnosisAgent


async def main():
    print("=" * 60)
    print("示例1: 自定义问诊 Agent 的系统提示词")
    print("=" * 60)
    
    from tcm_agent.agent import TCMDiagnosisAgent
    from tcm_agent.knowledge import TCMKnowledgeBase
    
    custom_kb = TCMKnowledgeBase()
    custom_kb.initialize()
    
    agent = TCMDiagnosisAgent(
        knowledge_base=custom_kb
    )
    
    agent.conversation_agent.instructions = """
你是一个专业的中医专家，具有30年临床经验。
你的特点：
1. 说话专业但易懂，会用通俗语言解释专业术语
2. 总是耐心倾听患者的描述
3. 善于引导患者详细描述症状
4. 强调"治未病"的预防理念
5. 会给出具体的生活调理建议

当前问诊阶段信息：
{phase_info}

已收集的患者信息：
{patient_info}

已收集的症状：
{symptoms}

请根据当前状态，与患者进行友好、专业的对话。
"""
    
    await agent.run("你好")
    print("\n用户: 我最近失眠")
    response = await agent.run("我最近失眠")
    print(f"助手: {response[:200]}..." if len(response) > 200 else f"助手: {response}")
    
    print("\n" + "=" * 60)
    print("示例2: 使用不同的 LLM 模型")
    print("=" * 60)
    
    from agentica import DeepSeekChat
    
    agent2 = TCMDiagnosisAgent(
        model=DeepSeekChat(id="deepseek-chat")
    )
    
    response = await agent2.run("你好")
    print(f"助手: {response[:150]}..." if len(response) > 150 else f"助手: {response}")
    
    print("\n" + "=" * 60)
    print("示例3: 知识库扩展")
    print("=" * 60)
    
    from tcm_agent.knowledge import TCMKnowledgeBase, TCMEntity, TCMRelation
    
    kb = TCMKnowledgeBase()
    kb.initialize()
    
    new_entity = TCMEntity(
        id="custom_syndrome",
        name="肝郁脾虚",
        type="syndrome",
        aliases=["肝脾不和"],
        description="肝气郁结，脾失健运的证候",
        properties={
            "category": "虚实夹杂",
            "related_organs": ["肝", "脾"],
            "common_symptoms": ["胁痛", "腹胀", "食欲不振", "便溏", "情志抑郁"]
        }
    )
    kb.kg.add_entity(new_entity)
    
    kb.kg.add_relation(TCMRelation(
        source="custom_syndrome",
        target="xiaoyao_decoction",
        relation_type="treated_by",
        weight=1.0
    ))
    
    result = kb.query_by_entity_name("肝郁脾虚")
    print(f"新增证型: {result['entity']['name']}")
    print(f"描述: {result['entity']['description']}")
    
    print("\n" + "=" * 60)
    print("所有示例完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
