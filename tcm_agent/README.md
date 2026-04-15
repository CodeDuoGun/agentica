# TCM Agent

中医智能问诊 Agent，基于 [agentica](https://github.com/shibing624/agentica) 框架构建。

## 功能特性

- **多轮问诊对话**：支持自然语言多轮交互，收集患者症状信息
- **意图识别**：智能识别用户意图（问候、症状描述、诊断请求、治疗咨询等）
- **知识图谱 RAG**：基于中医知识图谱的检索增强生成，提供准确的辨证论治建议
- **辨证分析**：根据症状进行证型分析（阴虚、阳虚、气虚、血虚等）
- **治疗方案**：生成个性化调理建议，包括中药方剂、针灸穴位、生活方式、饮食建议

## 架构

```
tcm_agent/
├── __init__.py          # 包入口
├── models.py            # 数据模型（症状、患者、诊断等）
├── knowledge.py         # 知识图谱 + RAG
├── intention.py         # 意图识别 Agent
├── agent.py             # 问诊 Agent
├── system.py            # 主协调系统
├── examples/            # 使用示例
│   ├── basic_usage.py   # 基础用法
│   └── cli_demo.py      # 命令行演示
└── tests/               # 测试代码
```

## 快速开始

### 安装依赖

```bash
pip install agentica networkx
```

### 基础使用

```python
import asyncio
from tcm_agent import TCMConsultationSystem

async def main():
    # 创建问诊系统
    system = TCMConsultationSystem()
    await system.start_session()

    # 开始对话
    response = await system.chat("你好")
    print(response)

    response = await system.chat("我最近总是失眠，睡不好觉")
    print(response)

    # 获取问诊摘要
    summary = system.get_session_summary(system.current_session.session_id)
    print(summary)

asyncio.run(main())
```

### 意图识别

```python
from tcm_agent import IntentionRecognitionAgent

agent = IntentionRecognitionAgent()
result = await agent.recognize("我头疼，该怎么办？")

print(f"意图: {result.intention.value}")
print(f"置信度: {result.confidence:.2f}")
```

### 知识库查询

```python
from tcm_agent import TCMKnowledgeBase

kb = TCMKnowledgeBase()
kb.initialize()

# 基于症状查询
results = kb.query_by_symptoms(["失眠", "心悸"], max_results=3)

# 查询具体实体
info = kb.query_by_entity_name("四君子汤")

# 获取治疗建议
treatment = kb.get_treatment_recommendations("气虚")
```

### 命令行演示

```bash
python -m tcm_agent.examples.cli_demo
```

## 数据模型

### IntentionType (意图类型)

- `GREETING` - 问候
- `SYMPTOM_DESCRIPTION` - 描述症状
- `SYMPTOM_INQUIRY` - 询问症状
- `DIAGNOSIS_REQUEST` - 请求诊断
- `TREATMENT_INQUIRY` - 询问治疗方案
- `MEDICINE_INQUIRY` - 询问药物
- `PREVENTION_INQUIRY` - 询问预防
- `LIFE_ADVICE` - 询问养生建议
- `FOLLOW_UP` - 随访/继续对话
- `GOODBYE` - 结束对话
- `OTHER` - 其他意图

## 知识图谱

内置中医知识图谱包含：

- **证型**：16种常见中医证型
- **中药**：常用中药材信息
- **方剂**：经典方剂组成和适应症
- **穴位**：常用针灸穴位
- **经络**：十二经络循行

关系类型包括：
- `treated_by` - 治疗关系
- `component_of` - 组成关系
- `may_cause` - 因果关系
- `related_to` - 相关关系
- `belongs_to` - 归属关系

## 注意事项

1. 本系统仅供参考，不能替代专业中医师的诊断和治疗
2. 如有严重症状，请及时就医
3. 药物使用请遵医嘱
