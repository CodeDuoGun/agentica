"""
v1版本API路由汇总
"""
from fastapi import APIRouter
from tcm_agent.view import consultation, status
from typing import Dict, Any, Optional, List, Tuple

# 创建v1版本的主路由
api_router = APIRouter()

# 注册各个子模块的路由
api_router.include_router(consultation.router)
api_router.include_router(status.router, tags=["状态"])

