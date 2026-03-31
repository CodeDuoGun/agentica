# -*- coding: utf-8 -*-
"""
TCM Consultation System - 主协调系统
中医问诊系统主入口

功能：
1. 统一入口，整合所有组件
2. 多轮对话管理
3. 状态持久化
4. 会话管理
"""
import asyncio
from typing import Dict, Any, Optional, List, Callable, AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from tcm_agent.agent import TCMDiagnosisAgent
from tcm_agent.knowledge import TCMKnowledgeBase
from tcm_agent.intention import IntentionRecognitionAgent
from tcm_agent.models import (
    ConsultationState,
    ConsultationPhase,
    IntentionType,
    IntentionResult,
)


class SessionStatus(Enum):
    """会话状态"""
    ACTIVE = "active"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    ERROR = "error"


@dataclass
class ConsultationSession:
    """问诊会话"""
    session_id: str
    state: ConsultationState = field(default_factory=ConsultationState)
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    messages: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class TCMConsultationSystem:
    """
    中医问诊系统主类
    
    统一管理多轮问诊流程，整合：
    - 意图识别
    - 症状提取
    - 知识图谱查询
    - 辨证论治
    - 治疗方案生成
    
    支持：
    - 同步/异步调用
    - 流式输出
    - 会话管理
    - 状态持久化
    """
    
    def __init__(
        self,
        model: Any = None,
        knowledge_base: Optional[TCMKnowledgeBase] = None,
        enable_stream: bool = True,
        max_turns: int = 50,
    ):
        """
        初始化问诊系统
        
        Args:
            model: LLM 模型
            knowledge_base: 知识库
            enable_stream: 启用流式输出
            max_turns: 最大对话轮次
        """
        self.diagnosis_agent = TCMDiagnosisAgent(
            model=model,
            knowledge_base=knowledge_base,
            enable_stream=enable_stream,
        )
        self.knowledge_base = self.diagnosis_agent.knowledge_base
        self.intention_agent = IntentionRecognitionAgent(model=model)
        
        self.enable_stream = enable_stream
        self.max_turns = max_turns
        
        self.current_session: Optional[ConsultationSession] = None
        self.sessions: Dict[str, ConsultationSession] = {}
    
    async def start_session(self, session_id: Optional[str] = None) -> str:
        """
        开始新会话
        
        Args:
            session_id: 会话ID，默认自动生成
            
        Returns:
            str: 会话ID
        """
        if session_id is None:
            session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        
        self.diagnosis_agent.reset()
        
        self.current_session = ConsultationSession(
            session_id=session_id,
            state=self.diagnosis_agent.get_state(),
        )
        self.sessions[session_id] = self.current_session
        
        return session_id
    
    async def chat(self, message: str) -> str:
        """
        处理单条消息
        
        Args:
            message: 用户消息
            
        Returns:
            str: 响应内容
        """
        if not self.current_session:
            await self.start_session()
        
        if self.current_session.status != SessionStatus.ACTIVE:
            self.current_session.status = SessionStatus.ACTIVE
            self.current_session.updated_at = datetime.now()
        
        turn_count = len(self.current_session.messages)
        if turn_count >= self.max_turns:
            self.current_session.status = SessionStatus.COMPLETED
            return "本次问诊已达到最大对话轮次，建议您整理问题后重新开始咨询。"
        
        self.current_session.messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })
        
        response = await self.diagnosis_agent.run(message)
        
        self.current_session.state = self.diagnosis_agent.get_state()
        self.current_session.messages.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now().isoformat(),
        })
        self.current_session.updated_at = datetime.now()
        
        if self.diagnosis_agent.get_state().is_complete:
            self.current_session.status = SessionStatus.COMPLETED
        
        return response
    
    async def chat_stream(self, message: str) -> AsyncIterator[str]:
        """
        流式处理消息
        
        Args:
            message: 用户消息
            
        Yields:
            str: 响应内容片段
        """
        if not self.current_session:
            await self.start_session()
        
        self.current_session.messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        })
        
        full_response = ""
        async for chunk in self.diagnosis_agent.run_stream(message):
            full_response += chunk
            yield chunk
        
        self.current_session.state = self.diagnosis_agent.get_state()
        self.current_session.messages.append({
            "role": "assistant",
            "content": full_response,
            "timestamp": datetime.now().isoformat(),
        })
        self.current_session.updated_at = datetime.now()
    
    def chat_sync(self, message: str) -> str:
        """同步版本"""
        return asyncio.run(self.chat(message))
    
    async def end_session(self) -> Dict[str, Any]:
        """
        结束当前会话
        
        Returns:
            Dict: 会话摘要
        """
        if not self.current_session:
            return {"error": "No active session"}
        
        self.current_session.status = SessionStatus.COMPLETED
        self.current_session.updated_at = datetime.now()
        
        summary = self.get_session_summary(self.current_session.session_id)
        
        self.current_session = None
        
        return summary
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """
        获取会话摘要
        
        Args:
            session_id: 会话ID
            
        Returns:
            Dict: 会话摘要
        """
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}
        
        state = session.state
        
        summary = {
            "session_id": session_id,
            "status": session.status.value,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "turns": len(session.messages),
            "phase": state.current_phase.value if state.current_phase else None,
            "symptoms": [s.name for s in state.symptoms],
            "has_diagnosis": state.diagnosis is not None,
            "has_treatment": state.treatment_plan is not None,
        }
        
        if state.patient_info.age:
            summary["patient_age"] = state.patient_info.age
        if state.patient_info.gender:
            summary["patient_gender"] = state.patient_info.gender.value
        
        if state.diagnosis:
            summary["diagnosis"] = {
                "syndrome": state.diagnosis.syndrome.value,
                "description": state.diagnosis.syndrome_description,
                "pathogenesis": state.diagnosis.pathogenesis,
            }
        
        if state.treatment_plan:
            summary["treatment"] = {
                "principle": state.treatment_plan.principle,
                "lifestyle_advice": state.treatment_plan.lifestyle_advice,
                "diet_advice": state.treatment_plan.diet_advice,
            }
        
        return summary
    
    async def query_knowledge(
        self,
        query: str,
        entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        查询知识库
        
        Args:
            query: 查询内容
            entity_type: 实体类型过滤
            
        Returns:
            List[Dict]: 查询结果
        """
        results = self.knowledge_base.search_similar(
            query,
            entity_types=[entity_type] if entity_type else None,
            max_results=5
        )
        return results
    
    async def diagnose_by_symptoms(
        self,
        symptoms: List[str],
        patient_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        基于症状进行诊断
        
        Args:
            symptoms: 症状列表
            patient_info: 患者信息
            
        Returns:
            Dict: 诊断结果
        """
        kg_results = self.knowledge_base.query_by_symptoms(symptoms, max_results=5)
        
        if kg_results:
            top_result = kg_results[0]
            syndrome_info = top_result.get("syndrome", {})
            
            diagnosis = {
                "syndrome": syndrome_info.get("name"),
                "description": syndrome_info.get("description"),
                "category": syndrome_info.get("category"),
                "related_organs": syndrome_info.get("related_organs", []),
                "common_symptoms": syndrome_info.get("common_symptoms", []),
                "confidence": top_result.get("confidence", 0),
                "treatment": top_result.get("treatment"),
            }
            
            return diagnosis
        
        return {
            "error": "No matching syndrome found",
            "suggestion": "Please provide more detailed symptom description"
        }
    
    def get_session(self, session_id: str) -> Optional[ConsultationSession]:
        """获取会话"""
        return self.sessions.get(session_id)
    
    def list_sessions(self) -> List[str]:
        """列出所有会话ID"""
        return list(self.sessions.keys())


async def create_cli_session():
    """创建命令行会话"""
    system = TCMConsultationSystem()
    
    print("=" * 60)
    print("欢迎使用中医智能问诊系统")
    print("=" * 60)
    print("输入您的问题，系统将进行中医辨证分析")
    print("输入 'quit' 或 '退出' 结束问诊")
    print("输入 'reset' 重新开始")
    print("输入 'summary' 查看当前问诊摘要")
    print("=" * 60)
    print()
    
    await system.start_session()
    
    print("助手: " + system.diagnosis_agent.WELCOME_MESSAGE)
    print()
    
    while True:
        try:
            user_input = input("您: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["quit", "退出", "exit", "q"]:
                summary = await system.end_session()
                print("\n问诊摘要:")
                print(f"- 对话轮次: {summary.get('turns', 0)}")
                if summary.get("diagnosis"):
                    print(f"- 辨证结果: {summary['diagnosis'].get('syndrome')}")
                if summary.get("symptoms"):
                    print(f"- 主要症状: {', '.join(summary['symptoms'][:5])}")
                print("\n感谢您的咨询，祝您健康！")
                break
            
            if user_input.lower() in ["reset", "重置"]:
                await system.start_session()
                print("\n[已重置问诊]")
                print("助手: " + system.diagnosis_agent.WELCOME_MESSAGE)
                continue
            
            if user_input.lower() == "summary":
                if system.current_session:
                    summary = system.get_session_summary(system.current_session.session_id)
                    print("\n当前问诊摘要:")
                    print(f"- 阶段: {summary.get('phase')}")
                    print(f"- 已收集症状: {', '.join(summary.get('symptoms', []))}")
                    if summary.get("diagnosis"):
                        print(f"- 辨证: {summary['diagnosis'].get('syndrome')}")
                continue
            
            response = await system.chat(user_input)
            print(f"\n助手: {response}")
            print()
            
        except KeyboardInterrupt:
            print("\n\n问诊已中断，再见！")
            break
        except Exception as e:
            print(f"\n发生错误: {e}")
            continue
    
    return system


def main():
    """主入口"""
    asyncio.run(create_cli_session())


if __name__ == "__main__":
    main()
