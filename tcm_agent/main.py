import os
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import uvicorn
from log import logger

# 添加项目路径
import sys
sys_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)


# ==================== 配置 ====================
HOST = os.getenv("API_HOST", "0.0.0.0")
PORT = int(os.getenv("API_PORT", "8000"))
DEBUG = os.getenv("DEBUG", "true").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    logger.info("中医问诊系统 API 启动")
    yield
    logger.info("中医问诊系统 API 关闭")


app = FastAPI(
    title="中医智能问诊系统 API",
    description="提供问诊会话管理、聊天接口",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
from tcm_agent.view import api_router
app.include_router(api_router, prefix="/api")

# ==================== 静态文件服务 ====================

web_dir = os.path.dirname(os.path.abspath(__file__))
index_path = os.path.join(web_dir, "web", "index.html")

# 挂载静态文件目录（CSS 和 JS）
app.mount("/static", StaticFiles(directory=os.path.join(web_dir, "web")), name="static")


@app.get("/", response_class=FileResponse)
async def root():
    """返回前端页面"""
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {"message": "前端页面未找到，请访问 /api/docs 查看 API 文档"}

def main():
    """启动服务器"""
    print("=" * 60)
    print("中医智能问诊系统 Web API")
    print("=" * 60)
    print(f"API 地址: http://{HOST}:{PORT}")
    print(f"前端页面: http://127.0.0.1:{PORT}/")
    print(f"API 文档: http://{HOST}:{PORT}/docs")
    print("=" * 60)
    
    uvicorn.run(
        "tcm_agent.main:app",
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info"
    )


if __name__ == "__main__":
    main()