"""
状态检查相关的API接口
"""
from fastapi import APIRouter
from tcm_agent.utils.response import general_response

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    健康检查接口
    """
    return general_response(data={"status": "ok"})

