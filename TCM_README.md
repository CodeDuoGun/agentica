**tcmagent** 基于异步轻量级框架开发的agent

TODO
- [ ] print_response  修改为yield sse
- [x] 接入知识图谱RAG检索, 处理医疗咨询问题、中医相关问题
- [x] Diagnosis agent, 目前回复内容过于冗余繁琐, 修改_build_system_prompt
- [ ] 修改状态问题槽位信息
- [x] sessionid 
- [ ] ConsultationRecord 结构化病历agent ，提示词
- [x] VisitTypeRecognitionAgent 去掉
- [x] 打招呼语创建session后返回，无问题
- [x] 意图识别没代入上下文
- [x] 需要接入问诊agent， _handle_medical_consultation 修改入口
- [ ] 增加诊断agent
- [ ] 修改session Lock机制，会话历史入库， redis, 删除self._histories 逻辑
- [ ] 让问诊大模型通过对话，。维持更新对话的槽位信息，并进行更新，这样估计会很慢。。。
- [ ] 去掉无用的代码
- [ ] 补充测试脚本，kg测试脚本



# run locally with conda
1. 创建环境
```bash

conda create -n tcmagent python=3.12
conda activate tcmagent
pip insall -r requirements.txt
 
```
2. 获取env 文件，咨询 @tangxueduo

3. 启动脚本
```bash
python -m tcm_agent.main
```


多轮对话示例
{
  "slot_updates": [
    {
      "field": "chief_complaint",
      "value": "头痛伴发热两天",
      "confidence": 0.93
    },
    {
      "field": "symptoms",
      "value": [
        {
          "name": "头痛",
          "duration": "2天",
          "severity": "中",
          "location": "头部",
          "description": "持续性疼痛",
          "trigger": "夜间加重",
          "relief": null
        },
        {
          "name": "发热",
          "duration": "2天",
          "severity": "轻",
          "location": null,
          "description": "低热",
          "trigger": "夜间加重",
          "relief": null
        }
      ],
      "confidence": 0.91
    }
  ],
  "structured_data": null,
  "reply": "头痛是胀痛还是刺痛呢，发热大概多少度，有测量过吗",
  "control": {
    "next_action": "next_question",
    "target_slot": "symptoms.description",
    "priority": 1
  },
  "image_request": null,
  "is_finished": false,
  "risk_alert": null
}