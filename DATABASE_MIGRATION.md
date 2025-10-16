# 数据库迁移指南

## 概述

prefab-gateway v2.0 引入了 MySQL 数据库持久化，取代了原有的纯内存存储方案。

## 新增特性

### 1. 数据库持久化
- **用户密钥**: 加密存储到 `user_secrets` 表
- **预制件规格**: 缓存到 `prefab_specs` 表
- **审计日志**: 记录到 `audit_logs` 表
- **Webhook 事件**: 存储到 `webhook_events` 表

### 2. 加密存储
- 使用 Fernet 对称加密保护用户密钥
- 支持密钥轮转（Key Rotation）
- 记录密钥使用时间和状态

### 3. 双层缓存
- **L1**: Redis（性能层，TTL 管理）
- **L2**: MySQL（持久层，数据库查询）

##前置要求

1. **MySQL 5.7+ 或 MariaDB 10.3+**
2. **Python 3.11+**
3. **依赖包**: `sqlalchemy`, `alembic`, `aiomysql`, `pymysql`, `cryptography`

## 配置

### 1. 环境变量

在 `.env` 文件中添加数据库配置：

```env
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=prefab_gateway
DB_PASSWORD=your-secure-password
DB_NAME=prefab_gateway

# 加密配置（必须修改！）
ENCRYPTION_KEY=your-32-byte-encryption-key-change-in-production-!!
```

### 2. 创建数据库

```bash
# 连接到 MySQL
mysql -u root -p

# 创建数据库和用户
CREATE DATABASE prefab_gateway CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'prefab_gateway'@'localhost' IDENTIFIED BY 'your-secure-password';
GRANT ALL PRIVILEGES ON prefab_gateway.* TO 'prefab_gateway'@'localhost';
FLUSH PRIVILEGES;
```

## 数据库迁移

### 方式 1: 使用 uv 命令（推荐）

```bash
# 1. 安装依赖
uv sync --dev

# 2. 初始化数据库（创建所有表）
uv run db-init

# 3. 或使用 Alembic 迁移
uv run db-migrate   # 生成迁移脚本
uv run db-upgrade   # 应用迁移
```

### 方式 2: 使用 Alembic 直接操作

```bash
# 生成迁移
uv run alembic revision --autogenerate -m "initial migration"

# 应用迁移
uv run alembic upgrade head

# 回滚
uv run alembic downgrade -1
```

## 数据模型

### user_secrets
存储用户的加密密钥

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 |
| user_id | VARCHAR(64) | 用户 ID |
| prefab_id | VARCHAR(128) | 预制件 ID |
| secret_name | VARCHAR(128) | 密钥名称 |
| secret_value | TEXT | 加密后的密钥值 |
| status | ENUM | active/disabled/expired |
| created_at | DATETIME | 创建时间 |
| last_used_at | DATETIME | 最后使用时间 |

### prefab_specs
缓存预制件规格

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 |
| prefab_id | VARCHAR(128) | 预制件 ID |
| version | VARCHAR(32) | 版本号 |
| spec_json | JSON | manifest.json 内容 |
| deployment_status | ENUM | pending/building/deployed/failed |
| knative_service_url | VARCHAR(512) | Knative 服务地址 |
| call_count | INT | 调用次数 |

### audit_logs
审计日志

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 |
| request_id | VARCHAR(64) | 请求 ID |
| user_id | VARCHAR(64) | 用户 ID |
| action | VARCHAR(64) | 操作类型 |
| success | BOOLEAN | 是否成功 |
| created_at | DATETIME | 操作时间 |

### webhook_events
Webhook 事件队列

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 |
| event_id | VARCHAR(64) | 事件 ID（唯一） |
| source | VARCHAR(64) | 事件来源（factory/github） |
| event_type | VARCHAR(64) | 事件类型 |
| payload | JSON | 事件载荷 |
| processed | BOOLEAN | 是否已处理 |

## 密钥加密

### 工作原理

1. **加密算法**: Fernet（AES-128-CBC + HMAC）
2. **密钥派生**: SHA256(ENCRYPTION_KEY) → Base64 URL-safe
3. **加密流程**:
   ```
   plaintext → Fernet.encrypt() → base64_ciphertext → DB
   ```
4. **解密流程**:
   ```
   DB → base64_ciphertext → Fernet.decrypt() → plaintext
   ```

### 安全建议

1. **ENCRYPTION_KEY 必须修改**: 至少 32 字节，随机生成
2. **定期轮转**: 支持使用旧密钥解密，新密钥加密
3. **环境隔离**: 开发/测试/生产使用不同的加密密钥
4. **备份**: 加密密钥丢失后数据无法恢复！

生成安全的加密密钥：

```python
import secrets
print(secrets.token_urlsafe(32))
```

## 迁移检查清单

- [ ] 创建 MySQL 数据库和用户
- [ ] 配置环境变量（DB_HOST, DB_USER, DB_PASSWORD, ENCRYPTION_KEY）
- [ ] 运行数据库初始化 (`uv run db-init`)
- [ ] 验证表是否创建成功
- [ ] 测试加密/解密功能
- [ ] 更新监控和告警配置

## 回滚方案

如果需要回滚到内存模式：

1. 切换到 v1.x 分支
2. 或保留数据库但使用旧版代码

**注意**: 回滚后数据库中的数据不会自动清除。

## 故障排查

### 连接失败

```
Error: Can't connect to MySQL server
```

- 检查 MySQL 是否运行: `systemctl status mysql`
- 检查端口: `netstat -tuln | grep 3306`
- 检查防火墙规则

### 加密失败

```
cryptography.fernet.InvalidToken
```

- ENCRYPTION_KEY 被修改或不正确
- 尝试使用旧密钥解密新数据

### 迁移冲突

```
alembic.util.exc.CommandError: Target database is not up to date
```

```bash
# 查看当前版本
uv run alembic current

# 查看历史
uv run alembic history

# 强制升级
uv run alembic upgrade head
```

## 性能优化

1. **索引**: 已在关键字段上创建索引
2. **连接池**: 使用 SQLAlchemy 连接池（默认 5-20 个连接）
3. **缓存**: Redis 作为第一层缓存，减少数据库查询

## 下一步

- [ ] 重构 SpecCacheService 使用数据库
- [ ] 更新路由以注入数据库会话
- [ ] 添加 Webhook 端点
- [ ] 完善审计日志记录
- [ ] 添加数据库监控

---

**版本**: v2.0-alpha  
**最后更新**: 2025-10-16

