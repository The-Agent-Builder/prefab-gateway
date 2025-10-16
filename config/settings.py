"""
应用配置
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用基础配置
    app_name: str = "Prefab Gateway"
    app_version: str = "1.0.0"
    debug: bool = False
    
    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000
    
    # JWT 配置
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 30
    
    # 数据库配置（MySQL）
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "prefab_gateway"
    DB_PASSWORD: str = "change-me-in-production"
    DB_NAME: str = "prefab_gateway"
    
    # 数据加密配置（用于加密用户密钥）
    ENCRYPTION_KEY: str = "your-32-byte-encryption-key-change-in-production"  # 至少 32 字节
    
    # Redis 配置（用于 SpecCache）
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    
    # 密钥保管库配置
    vault_url: Optional[str] = None  # 如果为 None，使用内存模拟
    vault_token: Optional[str] = None
    
    # 访问控制服务配置
    acl_service_url: Optional[str] = None  # 如果为 None，使用内存模拟
    
    # Knative 服务配置
    knative_domain_suffix: str = "prefab.svc.cluster.local"
    knative_namespace: str = "default"
    
    # HTTP 客户端配置
    http_timeout: int = 30  # 秒
    http_max_retries: int = 2
    
    # 日志配置
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()

