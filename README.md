# 🌐 Prefab Gateway

AI 预制件生态系统的 **唯一、安全、可控的流量入口**。

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 📋 概述

Prefab Gateway 是 AI 预制件平台的核心组件，负责：

- 🔐 **认证与授权** - JWT 基于的用户认证
- 🛡️ **安全隔离** - 密钥在运行时动态注入，永不持久化
- 🎯 **智能路由** - 自动解析并路由到对应的 Knative 服务
- ✅ **输入验证** - 严格的参数类型和权限检查
- 📊 **可观测性** - 全链路请求追踪

## 🏗️ 架构设计

```
┌─────────────┐
│   Code AI   │
└──────┬──────┘
       │ JWT Token
       ▼
┌─────────────────────────────────────┐
│      Prefab Gateway (本项目)         │
│  ┌────────────────────────────────┐ │
│  │  1. 认证 & 授权                │ │
│  │  2. 获取预制件规格              │ │
│  │  3. 输入验证                    │ │
│  │  4. ACL 权限检查                │ │
│  │  5. 密钥解析（从 Vault）        │ │
│  │  6. 路由到 Knative              │ │
│  └────────────────────────────────┘ │
└──────┬──────────────────────────────┘
       │ {inputs, _secrets}
       ▼
┌───────────────────┐
│ Knative Services  │
│  (prefab-factory) │
└───────────────────┘
```

## 🚀 快速开始

### 前置要求

- Python 3.11+
- Redis (可选 - 用于规格缓存，未配置时自动使用内存)
- uv (包管理器)

### 安装

```bash
# 克隆仓库
git clone https://github.com/The-Agent-Builder/prefab-gateway.git
cd prefab-gateway

# 安装依赖
uv sync --dev

# 配置环境变量（可选）
# 如果不配置，将使用默认配置（内存模式）
# cp .env.example .env
# 编辑 .env 文件
```

### 运行

```bash
# 开发模式（推荐）- 自动重载
uv run dev

# 或者直接启动
uv run start

# 生产模式（多进程）
uv run prod

# 或手动使用 uvicorn
uv run uvicorn app.main:app --reload --port 8000
```

### 访问 API 文档

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 📚 API 端点

### 1. 执行预制件 - `POST /v1/run`

```json
{
  "calls": [
    {
      "prefab_id": "weather-api-v1",
      "version": "1.0.0",
      "function_name": "get_current_weather",
      "inputs": {
        "city": "London"
      }
    }
  ]
}
```

**响应:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "COMPLETED",
  "results": [
    {
      "status": "SUCCESS",
      "output": {
        "temperature": 15.5,
        "condition": "Cloudy"
      }
    }
  ]
}
```

### 2. 配置密钥 - `POST /v1/secrets`

```json
{
  "prefab_id": "weather-api-v1",
  "secret_name": "API_KEY",
  "secret_value": "sk-..."
}
```

### 3. 获取预制件规格 - `GET /v1/prefabs/{id}/{version}/spec`

返回预制件的函数签名和参数定义。

## 🔐 安全特性

### 密钥生命周期

1. **存储阶段**: 用户通过 `/v1/secrets` 端点存储密钥到 Vault
2. **解析阶段**: Gateway 在运行时从 Vault 读取密钥
3. **注入阶段**: 密钥作为 `_secrets` 字段注入到下游请求
4. **使用阶段**: Knative 服务临时设置环境变量
5. **清理阶段**: 函数执行完成后立即清理环境变量

**关键点**: Gateway 永不持久化密钥，只在运行时传递。

### 访问控制

- **InputFile**: 检查用户是否有 S3 对象的读取权限
- **OutputFile**: 自动授予用户对生成文件的所有权

## 🧪 测试

```bash
# 运行所有测试
uv run pytest tests/ -v

# 测试覆盖率
uv run pytest tests/ --cov=app --cov=services --cov-report=html

# 代码风格检查
uv run flake8 app/ services/ models/ --max-line-length=120
```

## 📁 项目结构

```
prefab-gateway/
├── app/
│   ├── main.py                 # FastAPI 应用入口
│   ├── dependencies/           # 依赖注入（认证等）
│   │   └── auth.py
│   └── routers/                # 路由模块
│       ├── run.py              # /v1/run 端点
│       ├── secrets.py          # /v1/secrets 端点
│       └── prefabs.py          # /v1/prefabs 端点
├── config/
│   └── settings.py             # 应用配置
├── models/
│   ├── requests.py             # 请求模型
│   └── responses.py            # 响应模型
├── services/
│   ├── vault_service.py        # 密钥保管库
│   ├── acl_service.py          # 访问控制
│   └── spec_cache_service.py   # 规格缓存
├── tests/                      # 测试
├── pyproject.toml              # 项目配置
└── README.md
```

## ⚙️ 配置

通过环境变量或 `.env` 文件配置：

```bash
# JWT 配置
JWT_SECRET_KEY=your-secret-key-change-in-production
JWT_ALGORITHM=HS256

# Redis 配置
REDIS_HOST=localhost
REDIS_PORT=6379

# Knative 配置
KNATIVE_DOMAIN_SUFFIX=prefab.svc.cluster.local
KNATIVE_NAMESPACE=default

# 日志级别
LOG_LEVEL=INFO
```

## 📊 监控和可观测性

每个请求都会生成唯一的 `request_id`，用于全链路追踪：

```
[550e8400-...] Processing run request with 1 calls for user test-user-123
[550e8400-...] Processing call 1/1: weather-api-v1@1.0.0
[550e8400-...] Resolved secret: API_KEY
[550e8400-...] Invoking: http://weather-api-v1.default.prefab.svc.cluster.local/invoke/get_current_weather
[550e8400-...] Call 1 completed successfully
```

## 🤝 与其他服务的集成

- **prefab-template**: 定义密钥声明（`secrets` 字段）
- **prefab-factory**: 部署时声明环境变量，运行时接收密钥
- **prefab-releases**: 提供预制件的发布信息

## 📝 开发指南

### 添加新端点

1. 在 `app/routers/` 创建新路由文件
2. 实现端点逻辑
3. 在 `app/main.py` 中注册路由
4. 编写测试

### 添加新服务

1. 在 `services/` 创建服务类
2. 实现异步方法
3. 在 `services/__init__.py` 导出
4. 创建全局单例实例

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🔗 相关项目

- [prefab-template](https://github.com/your-org/prefab-template) - 预制件模板
- [prefab-factory](https://github.com/your-org/prefab-factory) - 部署服务
- [prefab-releases](https://github.com/your-org/prefab-releases) - 发布仓库

---

**Built with ❤️ for the AI Prefab Ecosystem**

