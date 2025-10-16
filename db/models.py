"""数据库模型定义"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime,
    Index, JSON, Enum as SQLEnum
)
from sqlalchemy.sql import func
from db.base import Base
import enum


class SecretStatus(enum.Enum):
    """密钥状态"""
    ACTIVE = "active"
    DISABLED = "disabled"
    EXPIRED = "expired"


class DeploymentStatus(enum.Enum):
    """部署状态"""
    PENDING = "pending"
    BUILDING = "building"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"


class UserSecret(Base):
    """用户密钥表 - 加密存储用户的 API Key 等敏感信息"""
    __tablename__ = "user_secrets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), nullable=False, index=True, comment="用户 ID")
    prefab_id = Column(String(128), nullable=False, index=True, comment="预制件 ID（如 weather-api-v1）")
    secret_name = Column(String(128), nullable=False, comment="密钥名称（如 API_KEY）")
    secret_value = Column(Text, nullable=False, comment="加密后的密钥值")
    encryption_key_id = Column(String(64), nullable=True, comment="加密密钥 ID（用于密钥轮转）")
    status = Column(SQLEnum(SecretStatus), default=SecretStatus.ACTIVE, nullable=False)
    
    # 元数据
    description = Column(String(255), nullable=True, comment="密钥描述")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=True, comment="过期时间")
    last_used_at = Column(DateTime, nullable=True, comment="最后使用时间")

    # 复合索引
    __table_args__ = (
        Index('idx_user_prefab_secret', 'user_id', 'prefab_id', 'secret_name', unique=True),
        Index('idx_status', 'status'),
        {'comment': '用户密钥表'}
    )


class PrefabSpec(Base):
    """预制件规格表 - 缓存预制件的 manifest.json"""
    __tablename__ = "prefab_specs"

    id = Column(Integer, primary_key=True, index=True)
    prefab_id = Column(String(128), nullable=False, index=True, comment="预制件 ID")
    version = Column(String(32), nullable=False, index=True, comment="版本号")
    spec_json = Column(JSON, nullable=False, comment="完整的 manifest.json 内容")
    
    # 部署信息
    knative_service_url = Column(String(512), nullable=True, comment="Knative 服务地址")
    deployment_status = Column(SQLEnum(DeploymentStatus), default=DeploymentStatus.PENDING, nullable=False)
    
    # 元数据
    artifact_url = Column(String(512), nullable=True, comment="制品 URL（GitHub Release）")
    source_repo = Column(String(256), nullable=True, comment="源代码仓库")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    deployed_at = Column(DateTime, nullable=True, comment="部署完成时间")
    
    # 统计信息
    call_count = Column(Integer, default=0, comment="调用次数")
    last_called_at = Column(DateTime, nullable=True, comment="最后调用时间")

    __table_args__ = (
        Index('idx_prefab_version', 'prefab_id', 'version', unique=True),
        Index('idx_deployment_status', 'deployment_status'),
        {'comment': '预制件规格表'}
    )


class AuditLog(Base):
    """审计日志表 - 记录所有重要操作"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(64), index=True, comment="请求 ID")
    user_id = Column(String(64), nullable=False, index=True, comment="用户 ID")
    
    # 操作信息
    action = Column(String(64), nullable=False, index=True, comment="操作类型（run, create_secret, delete_secret 等）")
    resource_type = Column(String(64), nullable=True, comment="资源类型（prefab, secret 等）")
    resource_id = Column(String(256), nullable=True, comment="资源 ID")
    
    # 请求详情
    endpoint = Column(String(256), nullable=True, comment="API 端点")
    method = Column(String(16), nullable=True, comment="HTTP 方法")
    ip_address = Column(String(64), nullable=True, comment="客户端 IP")
    user_agent = Column(String(512), nullable=True, comment="User Agent")
    
    # 结果
    success = Column(Boolean, nullable=False, default=True, comment="是否成功")
    error_code = Column(String(64), nullable=True, comment="错误代码")
    error_message = Column(Text, nullable=True, comment="错误消息")
    
    # 元数据
    extra_metadata = Column(JSON, nullable=True, comment="额外的元数据（JSON）")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, index=True)
    duration_ms = Column(Integer, nullable=True, comment="处理耗时（毫秒）")

    __table_args__ = (
        Index('idx_user_action_time', 'user_id', 'action', 'created_at'),
        Index('idx_request', 'request_id'),
        {'comment': '审计日志表'}
    )


class WebhookEvent(Base):
    """Webhook 事件表 - 记录来自 prefab-factory 的通知"""
    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True, comment="事件 ID（幂等性）")
    source = Column(String(64), nullable=False, comment="事件来源（factory, github 等）")
    event_type = Column(String(64), nullable=False, index=True, comment="事件类型（deployment.success, deployment.failed 等）")
    
    # 事件数据
    prefab_id = Column(String(128), nullable=True, index=True, comment="预制件 ID")
    version = Column(String(32), nullable=True, comment="版本号")
    payload = Column(JSON, nullable=False, comment="完整的事件载荷")
    
    # 处理状态
    processed = Column(Boolean, default=False, nullable=False, index=True, comment="是否已处理")
    processed_at = Column(DateTime, nullable=True, comment="处理时间")
    processing_error = Column(Text, nullable=True, comment="处理错误信息")
    retry_count = Column(Integer, default=0, comment="重试次数")
    
    # 元数据
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    signature = Column(String(256), nullable=True, comment="HMAC 签名（用于验证）")

    __table_args__ = (
        Index('idx_processed', 'processed', 'created_at'),
        Index('idx_prefab_event', 'prefab_id', 'event_type'),
        {'comment': 'Webhook 事件表'}
    )

