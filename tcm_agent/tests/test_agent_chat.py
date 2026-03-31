# -*- coding: utf-8 -*-
"""
TCM Agent - 测试意图识别和对话功能
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tcm_agent import TCMConsultationSystem, IntentionRecognitionAgent


async def test_intention_recognition():
    """测试意图识别"""
    print("=" * 60)
    print("测试意图识别")
    print("=" * 60)
    
    agent = IntentionRecognitionAgent()
    
    test_cases = [
        ("你好", "greeting"),
        ("我最近失眠", "symptom"),
        ("这是什么问题", "inquiry"),
        ("怎么治疗", "treatment"),
        ("谢谢，再见", "goodbye"),
    ]
    
    for text, expected_type in test_cases:
        result = await agent.recognize(text)
        print(f"输入: {text}")
        print(f"识别: {result.intention.value} (期望: {expected_type})")
        print(f"置信度: {result.confidence:.2f}")
        print()


async def test_consultation():
    """测试问诊对话"""
    print("\n" + "=" * 60)
    print("测试问诊对话")
    print("=" * 60)
    
    system = TCMConsultationSystem()
    await system.start_session()
    
    conversation = [
        "你好",
        "我最近总是失眠，睡不好觉",
        "还伴有心悸和健忘",
        "而且精神很差，总觉得乏力",
        "我今年40岁，男",
        "请帮我分析一下",
    ]
    
    for user_msg in conversation:
        print(f"\n用户: {user_msg}")
        response = await system.chat(user_msg)
        print(f"助手: {response[:200]}..." if len(response) > 200 else f"助手: {response}")


async def test_knowledge_query():
    """测试知识库查询"""
    print("\n" + "=" * 60)
    print("测试知识库查询")
    print("=" * 60)
    
    from tcm_agent import TCMKnowledgeBase
    
    kb = TCMKnowledgeBase()
    kb.initialize()
    
    print("\n--- 查询证型 ---")
    results = kb.query_by_symptoms(["失眠", "心悸"], max_results=2)
    for r in results:
        print(f"证型: {r['syndrome']['name']}")
        print(f"描述: {r['syndrome']['description'][:100]}...")
        print()
    
    print("\n--- 查询实体 ---")
    info = kb.query_by_entity_name("四君子汤")
    if "entity" in info:
        print(f"名称: {info['entity']['name']}")
        print(f"类型: {info['entity']['type']}")
        print(f"组成: {info['entity']['properties'].get('composition', [])}")
    
    print("\n--- 治疗建议 ---")
    treatment = kb.get_treatment_recommendations("气虚")
    print(f"生活建议: {treatment.get('lifestyle_advice', [])[:2]}")
    print(f"饮食建议: {treatment.get('diet_advice', [])[:2]}")


async def main():
    await test_intention_recognition()
    await test_consultation()
    await test_knowledge_query()
    
    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
