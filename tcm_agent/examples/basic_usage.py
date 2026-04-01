# -*- coding: utf-8 -*-
"""
TCM Agent - Usage Examples
中医问诊 Agent 使用示例

默认模型为通义千问 (Qwen)，需要环境变量 DASHSCOPE_API_KEY。
也可在 ~/.agentica/.env 或项目根目录 .env 中配置（见 .env.example）。
"""
import asyncio
import sys
import os
from pathlib import Path

# 仓库根目录加入 path，且优先加载根目录 .env（cwd 在 examples/ 时也能读到密钥）
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv

load_dotenv(_REPO_ROOT / ".env")

from tcm_agent import (
    TCMConsultationSystem,
    TCMDiagnosisAgent,
    TCMKnowledgeBase,
    IntentionRecognitionAgent,
)
from tcm_agent.models import get_enum_value
from agentica import QwenChat


async def example_basic_chat():
    """基础对话示例"""
    print("=" * 60)
    print("示例1: 基础问诊对话")
    print("=" * 60)
    
    system = TCMConsultationSystem()
    await system.start_session()
    
    responses = []
    responses.append(await system.chat("你好，医生"))
    print(f"用户: 你好，医生\n助手: {responses[0]}\n")
    
    responses.append(await system.chat("我最近总是失眠，睡不好觉"))
    print(f"用户: 我最近总是失眠，睡不好觉\n助手: {responses[1]}\n")
    
    responses.append(await system.chat("有时候还会头晕，白天精神很差"))
    print(f"用户: 有时候还会头晕，白天精神很差\n助手: {responses[2]}\n")
    
    responses.append(await system.chat("我今年35岁，男"))
    print(f"用户: 我今年35岁，男\n助手: {responses[3]}\n")
    
    responses.append(await system.chat("请帮我分析一下这是什么情况"))
    print(f"用户: 请帮我分析一下这是什么情况\n助手: {responses[4]}\n")
    
    responses.append(await system.chat("平时该怎么调理"))
    print(f"用户: 平时该怎么调理\n助手: {responses[5]}\n")


async def example_intention_recognition():
    """意图识别示例"""
    print("\n" + "=" * 60)
    print("示例2: 意图识别")
    print("=" * 60)
    
    agent = IntentionRecognitionAgent()
    
    test_inputs = [
        "你好",
        "我头疼",
        "这是怎么回事？",
        "怎么治疗比较好？",
        "需要吃什么药？",
        "平时要注意什么？",
        "谢谢，再见",
    ]
    
    for user_input in test_inputs:
        result = await agent.recognize(user_input)
        print(f"输入: {user_input}")
        print(f"意图: {get_enum_value(result.intention)} (置信度: {result.confidence:.2f})")


async def example_knowledge_query():
    """知识库查询示例"""
    print("\n" + "=" * 60)
    print("示例3: 知识库查询")
    print("=" * 60)
    
    kb = TCMKnowledgeBase()
    kb.initialize()
    
    print("\n--- 查询1: 基于症状查询证型 ---")
    results = kb.query_by_symptoms(["失眠", "心悸"], max_results=3)
    for r in results:
        print(f"症状: {r['symptom']}")
        print(f"证型: {r['syndrome']['name']}")
        print(f"描述: {r['syndrome']['description']}")
        if r['syndrome'].get('related_prescriptions'):
            print(f"推荐方剂: {[p['name'] for p in r['syndrome']['related_prescriptions']]}")
        print()
    
    print("\n--- 查询2: 查询具体实体 ---")
    entity_info = kb.query_by_entity_name("四君子汤")
    print(f"实体: {entity_info['entity']['name']}")
    print(f"描述: {entity_info['entity']['description']}")
    print(f"组成: {entity_info['entity']['properties'].get('composition', [])}")
    
    print("\n--- 查询3: 语义搜索 ---")
    search_results = kb.search_similar("补气健脾的方子", max_results=3)
    for r in search_results:
        print(f"实体: {r['entity']['name']}")
        print(f"类型: {r['entity']['type']}")
        print(f"匹配度: {r['score']:.2f}")
        print()
    
    print("\n--- 查询4: 获取治疗建议 ---")
    treatment = kb.get_treatment_recommendations("气虚")
    print(f"治疗方案:")
    print(f"- 生活方式: {treatment.get('lifestyle_advice', [])[:3]}")
    print(f"- 饮食建议: {treatment.get('diet_advice', [])[:3]}")


async def example_direct_agent():
    """直接使用 Agent 示例"""
    print("\n" + "=" * 60)
    print("示例4: 直接使用问诊 Agent")
    print("=" * 60)
    
    agent = TCMDiagnosisAgent(model=QwenChat(id="qwen-plus"))
    
    messages = [
        "医生你好",
        "我最近总是觉得乏力，没精神",
        "而且食欲不太好，吃什么都不香",
        "还经常腹胀，大便也不正常",
        "我今年42岁，女性",
        "请帮我看看这是什么问题",
    ]
    
    for msg in messages:
        print(f"\n用户: {msg}")
        response = await agent.run(msg)
        print(f"助手: {response[:200]}..." if len(response) > 200 else f"助手: {response}")
    
    state = agent.get_state()
    print(f"\n问诊状态:")
    print(f"- 阶段: {get_enum_value(state.current_phase)}")
    print(f"- 已收集症状: {[s.name for s in state.symptoms]}")
    if state.diagnosis:
        print(f"- 辨证: {get_enum_value(state.diagnosis.syndrome)}")


async def example_diagnose_by_symptoms():
    """基于症状诊断示例"""
    print("\n" + "=" * 60)
    print("示例5: 基于症状诊断")
    print("=" * 60)
    
    system = TCMConsultationSystem()
    
    symptoms = [
        "失眠",
        "心悸",
        "健忘",
        "乏力",
        "面色萎黄",
    ]
    
    patient_info = {
        "age": 45,
        "gender": "女",
    }
    
    result = await system.diagnose_by_symptoms(symptoms, patient_info)
    
    print(f"输入症状: {', '.join(symptoms)}")
    print(f"\n诊断结果:")
    print(f"- 证型: {result.get('syndrome')}")
    print(f"- 分类: {result.get('category')}")
    print(f"- 相关脏腑: {', '.join(result.get('related_organs', []))}")
    print(f"- 常见症状: {', '.join(result.get('common_symptoms', [])[:5])}")
    
    if result.get('treatment', {}).get('herbal_prescriptions'):
        print(f"\n推荐方剂:")
        for p in result['treatment']['herbal_prescriptions']:
            print(f"- {p['name']}: {p.get('indication', '')}")


async def main():
    """运行所有示例"""
    print("中医问诊 Agent 使用示例")
    print("=" * 60)
    
    # await example_basic_chat()
    # await example_intention_recognition()
    # await example_knowledge_query()
    await example_direct_agent()
    # await example_diagnose_by_symptoms()
    
    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
