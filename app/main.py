"""
Prefab Gateway - Main Application

AI 预制件生态系统的 API 网关
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from services.spec_cache_service import spec_cache_service
from app.routers import run, secrets, prefabs, webhooks

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format=settings.log_format
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info("Starting Prefab Gateway...")
    
    # 连接 Redis
    await spec_cache_service.connect()
    
    # 启动清理守护进程
    from services import file_handler_service
    import asyncio
    cleanup_task = asyncio.create_task(
        file_handler_service.start_cleanup_daemon(
            interval_seconds=300,  # 每 5 分钟清理一次
            max_age_seconds=3600   # 清理 1 小时前的目录
        )
    )
    
    logger.info(f"Prefab Gateway started on {settings.host}:{settings.port}")
    
    yield
    
    # 关闭
    logger.info("Shutting down Prefab Gateway...")
    cleanup_task.cancel()
    await spec_cache_service.close()
    logger.info("Prefab Gateway stopped")


# 创建 FastAPI 应用
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI 预制件生态系统的唯一、安全、可控的流量入口",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(run.router)
app.include_router(secrets.router)
app.include_router(prefabs.router)
app.include_router(webhooks.router)


@app.get("/", tags=["System"])
async def root():
    """根路径 - 系统信息"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running"
    }


@app.get("/health", tags=["System"])
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "version": settings.app_version
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

