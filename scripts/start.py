"""启动脚本 - 用于启动 Prefab Gateway 服务"""
import sys
import uvicorn


def dev():
    """开发模式启动（自动重载）"""
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="debug"
    )


def start():
    """标准模式启动"""
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )


def prod():
    """生产模式启动（多进程）"""
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        workers=4,
        log_level="warning"
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "dev":
        dev()
    elif len(sys.argv) > 1 and sys.argv[1] == "prod":
        prod()
    else:
        start()

