**tcmagent** 基于异步轻量级框架开发的agent

TODO
- [ ] print_response  修改为yield sse


tcm_agent/
├── __init__.py           # 包入口，导出所有公共接口
├── models.py             # 数据模型定义
│                         # - IntentionType: 意图类型枚举
│                         # - ConsultationPhase: 问诊阶段枚举
│                         # - SyndromeType: 证型枚举
│                         # - SymptomInfo/PatientInfo/DiagnosisInfo 等数据模型
├── knowledge.py          # 知识图谱 + RAG 系统
│                         # - TCMKnowledgeGraph: 知识图谱管理
│                         # - TCMKnowledgeBase: 知识库（支持症状查询、治疗建议）
├── intention.py          # 意图识别 Agent
│                         # - IntentionRecognitionAgent: 意图识别
│                         # - SymptomExtractor: 症状提取
│                         # - PatientInfoExtractor: 患者信息提取
├── agent.py              # 问诊 Agent
│                         # - TCMDiagnosisAgent: 核心问诊逻辑
├── system.py             # 主协调系统
│                         # - TCMConsultationSystem: 统一入口
│                         # - ConsultationSession: 会话管理
├── examples/             # 使用示例
│   ├── basic_usage.py    # 基础用法
│   └── cli_demo.py       # 命令行演示
├── tests/                # 测试代码
│   ├── test_tcm_agent.py # 单元测试
│   ├── test_agent_chat.py
│   └── test_custom_prompt.py
└── README.md             # 文档