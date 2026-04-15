# -*- coding: utf-8 -*-
"""
TCM Agent - Traditional Chinese Medicine Diagnosis Agent
基于 agentica 框架构建的中医智能问诊系统

Features:
- 多轮问诊对话
- 知识图谱 RAG
- 意图识别
- 症状分析
- 辨证论治
"""

from tcm_agent.knowledge import TCMKnowledgeBase 
from tcm_agent.intention import IntentionRecognitionAgent 
from tcm_agent.service.consultation import TCMConsultationSystem, ConsultationSession, SessionStatus
from tcm_agent.models import (
    SymptomInfo,
    DiagnosisInfo,
    TreatmentPlan,
    ConsultationState,
    IntentionCategory,
    IntentionResult,
    PatientInfo,
    PhysicalInfo,
    ConsultationPhase,
    ConsultationVisitType,
    MedicalHistory,
    ConsultationRecord,
    KGQueryResult,
)

__version__ = "0.1.0"

__all__ = [
    "TCMKnowledgeBase",
    "TCMKnowledgeGraph",
    "IntentionRecognitionAgent",
    "SymptomExtractor",
    "TCMConsultationSystem",
    "ConsultationSession",
    "SessionStatus",
    "SymptomInfo",
    "DiagnosisInfo",
    "TreatmentPlan",
    "ConsultationState",
    "IntentionCategory",
    "IntentionResult",
    "PatientInfo",
    "PhysicalInfo",
    "ConsultationPhase",
    "ConsultationVisitType",
    "MedicalHistory",
    "ConsultationRecord",
    "KGQueryResult",
]
