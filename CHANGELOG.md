# Changelog

本文档记录 Prefab Gateway 的所有重要变更。

## [1.0.0] - 2025-10-16

### 🎉 初始版本发布

这是 Prefab Gateway 的首个完整实现版本，完全符合 PRD v1.0 规范。

### 核心功能

- **认证与授权系统**
  - JWT 基于的用户认证
  - Bearer Token 安全方案
  - 权限范围（scopes）验证
  - 自动化的依赖注入

- **API 端点**
  - `POST /v1/run` - 核心执行引擎，支持串行调用多个预制件
  - `POST /v1/secrets` - 密钥配置端点
  - `GET /v1/secrets/{prefab_id}` - 列出用户密钥
  - `DELETE /v1/secrets/{prefab_id}/{secret_name}` - 删除密钥
  - `GET /v1/prefabs/{id}/{version}/spec` - 获取预制件规格
  - `POST /v1/prefabs/{id}/{version}/spec` - 缓存预制件规格
  - `GET /health` - 健康检查
  - `GET /` - 系统信息

- **服务层**
  - **VaultService** - 密钥保管库（当前为内存实现）
  - **AccessControlService** - 访问控制服务（ACL）
  - **SpecCacheService** - 预制件规格缓存（Redis + 内存回退）

- **核心处理流程 (/v1/run)**
  1. 认证和授权验证
  2. 从 Redis 获取预制件规格
  3. 严格的输入参数验证
  4. InputFile 权限检查
  5. **密钥解析和注入**（核心安全特性）
  6. 路由到 Knative 服务
  7. OutputFile 权限授予
  8. 结果聚合和返回

### 安全特性

- ✅ 密钥仅在运行时传递，永不持久化到 Gateway
- ✅ 完整的请求 ID 追踪
- ✅ 严格的类型验证
- ✅ 基于 ACL 的文件访问控制
- ✅ 作用域化的密钥管理

### 技术栈

- Python 3.11+
- FastAPI 0.104+
- Pydantic 2.0+
- httpx (异步 HTTP 客户端)
- python-jose (JWT)
- Redis (规格缓存)

### 数据模型

- **请求模型**: `PrefabInput`, `PrefabCall`, `RunRequestPayload`, `SecretPayload`
- **响应模型**: `CallResult`, `RunResponsePayload`, `ErrorResponse`
- **认证模型**: `User`

### 测试

- 认证和授权测试
- 密钥管理测试
- 完整的 fixtures 和测试配置

### 文档

- 完整的 README.md 包含快速开始和架构说明
- API 文档（Swagger UI 和 ReDoc）
- 详细的代码注释和文档字符串

### 配置

- 通过环境变量或 `.env` 文件配置
- 支持的配置项：
  - JWT 密钥和算法
  - Redis 连接
  - Knative 服务发现
  - HTTP 超时和重试
  - 日志级别

### 兼容性

- ✅ 与 prefab-template v3.0 完全兼容
- ✅ 与 prefab-factory v2.1 完全兼容
- ✅ 支持 v3.0 密钥管理规范

### 架构优势

- 无状态设计，易于水平扩展
- 异步处理，高并发能力
- 零信任架构
- 完整的可观测性支持

### 未来计划

- [ ] 集成真实的 Vault 服务（HashiCorp Vault/AWS Secrets Manager）
- [ ] 完善 ACL 服务集成
- [ ] 结果缓存（幂等性支持）
- [ ] A/B 测试和灰度发布
- [ ] 计费和审计日志
- [ ] 性能监控和告警
- [ ] API 限流和配额管理
- [ ] WebSocket 支持（长时间运行任务）

---

**密钥流架构完整打通**: prefab-template → prefab-factory → prefab-gateway ✅

**这是一个重要的里程碑！** 🎉

