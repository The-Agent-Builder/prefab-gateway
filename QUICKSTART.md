# 快速开始指南

## 前置要求

1. **MySQL 5.7+ 或 MariaDB 10.3+**
2. **Python 3.11+**
3. **uv** (已安装)

## 步骤 1: 创建 MySQL 数据库

```bash
# 连接到 MySQL
mysql -u root -p

# 在 MySQL 命令行中执行：
CREATE DATABASE prefab_gateway CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'prefab_gateway'@'localhost' IDENTIFIED BY 'your-secure-password';
GRANT ALL PRIVILEGES ON prefab_gateway.* TO 'prefab_gateway'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

## 步骤 2: 配置环境变量

```bash
# 复制配置示例
cp .env.example .env

# 编辑 .env 文件，修改以下关键配置：
```

**最小配置（用于测试）：**

```env
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=prefab_gateway
DB_PASSWORD=your-secure-password
DB_NAME=prefab_gateway

# 加密密钥（生成一个）
ENCRYPTION_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
```

**生成安全密钥：**

```bash
# 生成加密密钥
python3 -c "import secrets; print('ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"

# 生成 JWT 密钥
python3 -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(32))"

# 生成 Webhook 密钥
python3 -c "import secrets; print('WEBHOOK_SECRET=' + secrets.token_hex(32))"
```

## 步骤 3: 安装依赖

```bash
uv sync --dev
```

## 步骤 4: 初始化数据库

```bash
# 创建所有表
uv run db-init
```

**成功输出示例：**
```
🔧 初始化数据库...
✅ 数据库表创建成功！

📋 已创建的表：
  - user_secrets
  - prefab_specs
  - audit_logs
  - webhook_events
```

## 步骤 5: 启动服务

```bash
# 开发模式（自动重载）
uv run dev

# 或标准模式
uv run start
```

**成功输出示例：**
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

## 步骤 6: 验证服务

```bash
# 健康检查
curl http://localhost:8000/health

# 查看 API 文档
open http://localhost:8000/docs
```

---

## 常见问题

### Q1: 数据库连接失败？

**错误**: `(1049, "Unknown database 'prefab_gateway'")`

**解决**: 确保已创建数据库（参见步骤 1）

---

**错误**: `(1045, "Access denied for user 'prefab_gateway'@'localhost'")`

**解决**: 检查 `.env` 中的 `DB_USER` 和 `DB_PASSWORD`

---

### Q2: 加密密钥错误？

**错误**: `cryptography.fernet.InvalidToken`

**解决**: 
1. 确保 `ENCRYPTION_KEY` 已配置
2. 不要修改已有的 `ENCRYPTION_KEY`，否则无法解密旧数据
3. 如果是测试环境，可以删除数据库重新初始化

---

### Q3: Redis 连接失败？

**信息**: `Failed to connect to Redis: ... Using in-memory cache as fallback.`

**说明**: 这是正常的，服务会自动使用内存缓存。如果需要 Redis，请安装并启动：

```bash
# macOS
brew install redis
brew services start redis

# 或 Docker
docker run -d -p 6379:6379 redis:7-alpine
```

---

## 数据库管理命令

```bash
# 初始化数据库（创建表）
uv run db-init

# 生成迁移脚本
uv run db-migrate

# 应用迁移
uv run db-upgrade

# 回滚迁移
uv run db-downgrade
```

---

## 开发工作流

```bash
# 1. 启动开发服务器
uv run dev

# 2. 在另一个终端查看日志
# 日志会输出到控制台

# 3. 测试 API
curl -X POST http://localhost:8000/v1/secrets \
  -H "Authorization: Bearer your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "prefab_id": "test-prefab",
    "secret_name": "API_KEY",
    "secret_value": "test-secret-value"
  }'
```

---

## 下一步

- 📚 阅读 [DATABASE_MIGRATION.md](DATABASE_MIGRATION.md) 了解数据库架构
- 📖 查看 [API 文档](http://localhost:8000/docs)
- 🔧 配置与 prefab-factory 的集成
- 🧪 编写自动化测试

---

**需要帮助？** 查看完整文档或提交 Issue。

