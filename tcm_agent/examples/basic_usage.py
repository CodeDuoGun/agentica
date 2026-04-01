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


async def example_intention_recognition():
    """意图识别示例"""
    print("\n" + "=" * 60)
    print("示例1: 意图识别")
    print("=" * 60)
    
    agent = IntentionRecognitionAgent()
    
    test_inputs = [
        "你好，医生",
        "这个中药怎么煎？",
        "我最近总是头疼，睡不着觉",
        "帮我看看我是什么问题",
        "今天天气真不错",
    ]
    
    for user_input in test_inputs:
        result = await agent.recognize(user_input)
        print(f"\n输入: {user_input}")
        print(f"意图类别: {get_enum_value(result.category)}")
        print(f"置信度: {result.confidence:.2f}")
        print(f"推荐回复: {result.suggested_response or 'N/A'}")


async def example_consultation_system():
    """完整的问诊系统示例"""
    print("\n" + "=" * 60)
    print("示例2: 完整问诊系统")
    print("=" * 60)
    
    system = TCMConsultationSystem(max_turns=50, max_consultation_turns=30)
    
    await system.start_session()
    print("助手: 您好！欢迎来到中医智能问诊系统。")
    
    messages = [
        "我最近总是失眠，睡不着觉",
        "30岁，男",
        "头有点疼，白天没精神",
        "没有过敏史",
        "之前没有得过什么大病",
        "无",
        "没有其他补充了"
    ]
    
    for msg in messages:
        print(f"\n用户: {msg}")
        response = await system.chat(msg)
        if response:
            print(f"助手: {response[:300]}..." if len(response) > 300 else f"助手: {response}")
        else:
            print("助手: [非医疗咨询，无回复]")
    
    # 获取结构化病历
    record = system.get_consultation_record()
    if record:
        print("\n" + "=" * 60)
        print("结构化病历:")
        print(f"- 就诊类型: {get_enum_value(record.visit_type)}")
        print(f"- 主诉: {record.chief_complaint}")
        print(f"- 症状数量: {len(record.symptoms)}")
        print(f"- 过敏史: {', '.join(record.medical_history.allergies) or '无'}")


async def example_consultation_flow():
    """问诊流程示例"""
    print("\n" + "=" * 60)
    print("示例3: 问诊流程演示")
    print("=" * 60)
    
    system = TCMConsultationSystem()
    
    # 设置病历生成回调
    def on_record_generated(record):
        print(f"\n[回调] 病历已生成: {record.chief_complaint}")
    
    system.set_record_callback(on_record_generated)
    
    await system.start_session()
    
    # 正常问诊流程
    test_cases = [
        # 普通咨询
        ("这个降压药有什么副作用？", "general_medical"),
        # 问诊
        ("我最近总是胸闷气短", "consultation"),
        ("45岁，男", "consultation"),
        ("这种情况大概有三个月了", "consultation"),
        ("没有过敏史", "consultation"),
        # 非医疗咨询（不回复）
        ("今天股票涨了吗？", "non_medical"),
    ]
    
    for msg, expected_category in test_cases:
        print(f"\n用户: {msg}")
        print(f"预期类别: {expected_category}")
        
        response = await system.chat(msg)
        
        if response:
            print(f"助手: {response[:200]}..." if len(response) > 200 else f"助手: {response}")
        else:
            print("助手: [无回复]")


async def example_interruption_handling():
    """中断处理示例"""
    print("\n" + "=" * 60)
    print("示例4: 中断场景处理")
    print("=" * 60)
    
    # 设置较小的轮数限制来演示中断
    system = TCMConsultationSystem(max_turns=3, max_consultation_turns=3)
    
    await system.start_session()
    print("助手: 您好！欢迎来到中医智能问诊系统。")
    
    messages = [
        "我最近总是头疼",
        "30岁",
        "还有其他不舒服吗",
    ]
    
    for msg in messages:
        print(f"\n用户: {msg}")
        response = await system.chat(msg)
        if response:
            print(f"助手: {response}")
        
        if system.current_session and system.current_session.status.value != "active":
            print(f"\n会话状态: {system.current_session.status.value}")
            print(f"中断原因: {system.current_session.interrupt_reason.value if system.current_session.interrupt_reason else 'N/A'}")
            break


async def main():
    """运行所有示例"""
    print("=" * 60)
    print("中医智能问诊系统 - 使用示例")
    print("=" * 60)
    
    try:
        await example_intention_recognition()
    except Exception as e:
        print(f"\n意图识别示例出错: {e}")
    
    try:
        await example_consultation_system()
    except Exception as e:
        print(f"\n问诊系统示例出错: {e}")
    
    try:
        await example_consultation_flow()
    except Exception as e:
        print(f"\n问诊流程示例出错: {e}")
    
    try:
        await example_interruption_handling()
    except Exception as e:
        print(f"\n中断处理示例出错: {e}")
    
    print("\n" + "=" * 60)
    print("所有示例运行完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
