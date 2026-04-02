# -*- coding: utf-8 -*-
"""
TCM Agent Tests
中医问诊 Agent 测试代码
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestTCMModels:
    """测试数据模型"""
    
    def test_intention_type_enum(self):
        from tcm_agent.models import IntentionType
        assert IntentionType.GREETING.value == "greeting"
        assert IntentionType.SYMPTOM_DESCRIPTION.value == "symptom"
        assert IntentionType.DIAGNOSIS_REQUEST.value == "diagnosis"
    
    def test_consultation_phase_enum(self):
        from tcm_agent.models import ConsultationPhase
        assert ConsultationPhase.WELCOME.value == "welcome"
        assert ConsultationPhase.SYMPTOM_INQUIRY.value == "symptom"
    
    def test_symptom_info_model(self):
        from tcm_agent.models import SymptomInfo
        symptom = SymptomInfo(
            name="头痛",
            severity=4,
            duration="3天"
        )
        assert symptom.name == "头痛"
        assert symptom.severity == 4
        assert symptom.duration == "3天"
    
    def test_patient_info_model(self):
        from tcm_agent.models import PatientInfo, Gender
        patient = PatientInfo(
            name="张三",
            age=35,
            gender=Gender.MALE
        )
        assert patient.name == "张三"
        assert patient.age == 35
        assert patient.gender == Gender.MALE
    
    def test_consultation_state_model(self):
        from tcm_agent.models import ConsultationState, ConsultationPhase
        state = ConsultationState()
        assert state.session_id
        assert state.consultation_phase == ConsultationPhase.WELCOME
        assert len(state.symptoms) == 0
        assert not state.is_complete


class TestTCMKnowledgeGraph:
    """测试知识图谱"""
    
    def test_create_empty_graph(self):
        from tcm_agent.knowledge import TCMKnowledgeGraph
        kg = TCMKnowledgeGraph()
        assert kg.graph is not None
        assert len(kg.entity_index) == 0
    
    def test_add_entity(self):
        from tcm_agent.knowledge import TCMKnowledgeGraph, TCMEntity
        kg = TCMKnowledgeGraph()
        entity = TCMEntity(
            id="test_entity",
            name="测试实体",
            type="syndrome",
            description="一个测试实体"
        )
        kg.add_entity(entity)
        assert "test_entity" in kg.entity_index
        retrieved = kg.get_entity("test_entity")
        assert retrieved.name == "测试实体"
    
    def test_add_relation(self):
        from tcm_agent.knowledge import TCMKnowledgeGraph, TCMEntity, TCMRelation
        kg = TCMKnowledgeGraph()
        entity1 = TCMEntity(id="e1", name="实体1", type="syndrome")
        entity2 = TCMEntity(id="e2", name="实体2", type="herb")
        kg.add_entity(entity1)
        kg.add_entity(entity2)
        
        relation = TCMRelation(
            source="e1",
            target="e2",
            relation_type="treated_by",
            weight=1.0
        )
        kg.add_relation(relation)
        
        related = kg.get_related_entities("e1")
        assert len(related) == 1
        assert related[0][0].name == "实体2"
    
    def test_find_entity_by_name(self):
        from tcm_agent.knowledge import TCMKnowledgeGraph, TCMEntity
        kg = TCMKnowledgeGraph()
        entity = TCMEntity(
            id="yin_deficiency",
            name="阴虚",
            type="syndrome",
            aliases=["阴虚证", "阴虚体质"]
        )
        kg.add_entity(entity)
        
        assert kg.find_entity_by_name("阴虚").id == "yin_deficiency"
        assert kg.find_entity_by_name("阴虚证").id == "yin_deficiency"
        assert kg.find_entity_by_name("阴虚体质").id == "yin_deficiency"


class TestTCMKnowledgeBase:
    """测试知识库"""
    
    def test_initialize(self):
        from tcm_agent.knowledge import TCMKnowledgeBase
        kb = TCMKnowledgeBase()
        kb.initialize()
        assert kb._initialized
        assert len(kb.kg.entity_index) > 0
    
    def test_query_by_symptoms(self):
        from tcm_agent.knowledge import TCMKnowledgeBase
        kb = TCMKnowledgeBase()
        kb.initialize()
        
        results = kb.query_by_symptoms(["失眠", "心悸"], max_results=3)
        assert isinstance(results, list)
    
    def test_query_by_entity_name(self):
        from tcm_agent.knowledge import TCMKnowledgeBase
        kb = TCMKnowledgeBase()
        kb.initialize()
        
        result = kb.query_by_entity_name("四君子汤")
        assert "entity" in result
        assert result["entity"]["name"] == "四君子汤"
    
    def test_search_similar(self):
        from tcm_agent.knowledge import TCMKnowledgeBase
        kb = TCMKnowledgeBase()
        kb.initialize()
        
        results = kb.search_similar("补气", max_results=5)
        assert isinstance(results, list)
        if results:
            assert "entity" in results[0]
            assert "score" in results[0]
    
    def test_get_treatment_recommendations(self):
        from tcm_agent.knowledge import TCMKnowledgeBase
        kb = TCMKnowledgeBase()
        kb.initialize()
        
        treatment = kb.get_treatment_recommendations("气虚")
        assert "syndrome_analysis" in treatment
        assert "lifestyle_advice" in treatment
        assert "diet_advice" in treatment


class TestIntentionRecognition:
    """测试意图识别"""
    
    @pytest.mark.asyncio
    async def test_recognize_greeting(self):
        from tcm_agent.intention import IntentionRecognitionAgent
        from tcm_agent.models import IntentionType
        
        agent = IntentionRecognitionAgent()
        result = await agent.recognize("你好")
        
        assert result.intention == IntentionType.GREETING
        assert result.confidence > 0
    
    @pytest.mark.asyncio
    async def test_recognize_symptom(self):
        from tcm_agent.intention import IntentionRecognitionAgent
        from tcm_agent.models import IntentionType
        
        agent = IntentionRecognitionAgent()
        result = await agent.recognize("我最近总是头疼")
        
        assert result.intention in [IntentionType.SYMPTOM_DESCRIPTION, IntentionType.OTHER]
    
    @pytest.mark.asyncio
    async def test_recognize_goodbye(self):
        from tcm_agent.intention import IntentionRecognitionAgent
        from tcm_agent.models import IntentionType
        
        agent = IntentionRecognitionAgent()
        result = await agent.recognize("谢谢，再见")
        
        assert result.intention == IntentionType.GOODBYE


class TestTCMDiagnosisAgent:
    """测试问诊 Agent"""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        from tcm_agent.agent import TCMDiagnosisAgent
        
        agent = TCMDiagnosisAgent()
        assert agent.model is not None
        assert agent.knowledge_base is not None
        assert agent.state is not None
    
    @pytest.mark.asyncio
    async def test_greeting_response(self):
        from tcm_agent.agent import TCMDiagnosisAgent
        
        agent = TCMDiagnosisAgent()
        response = await agent.run("你好")
        
        assert len(response) > 0
        assert "欢迎" in response or "您好" in response
    
    @pytest.mark.asyncio
    async def test_symptom_collection(self):
        from tcm_agent.agent import TCMDiagnosisAgent
        
        agent = TCMDiagnosisAgent()
        await agent.run("我最近失眠")
        
        assert len(agent.state.symptoms) > 0
        assert agent.state.consultation_phase in ["welcome", "symptom"]
    
    @pytest.mark.asyncio
    async def test_reset(self):
        from tcm_agent.agent import TCMDiagnosisAgent
        
        agent = TCMDiagnosisAgent()
        await agent.run("你好")
        await agent.run("我头疼")
        
        assert len(agent.state.symptoms) > 0
        
        agent.reset()
        assert len(agent.state.symptoms) == 0
        assert agent.state.consultation_phase == "welcome"


class TestTCMConsultationSystem:
    """测试问诊系统"""
    
    @pytest.mark.asyncio
    async def test_start_session(self):
        from tcm_agent.system import TCMConsultationSystem
        
        system = TCMConsultationSystem()
        session_id = await system.start_session()
        
        assert session_id
        assert system.current_session is not None
        assert system.current_session.session_id == session_id
    
    @pytest.mark.asyncio
    async def test_chat(self):
        from tcm_agent.system import TCMConsultationSystem
        
        system = TCMConsultationSystem()
        await system.start_session()
        
        response = await system.chat("你好")
        assert len(response) > 0
        
        assert len(system.current_session.messages) == 2
    
    @pytest.mark.asyncio
    async def test_session_summary(self):
        from tcm_agent.system import TCMConsultationSystem
        
        system = TCMConsultationSystem()
        await system.start_session()
        
        await system.chat("你好")
        await system.chat("我最近失眠")
        
        summary = system.get_session_summary(system.current_session.session_id)
        
        assert "session_id" in summary
        assert "turns" in summary
        assert summary["turns"] == 2
    
    @pytest.mark.asyncio
    async def test_end_session(self):
        from tcm_agent.system import TCMConsultationSystem
        
        system = TCMConsultationSystem()
        await system.start_session()
        
        await system.chat("你好")
        
        summary = await system.end_session()
        
        assert "session_id" in summary
        assert system.current_session is None


def run_async_test(coro):
    """运行异步测试"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.run(coro))
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
