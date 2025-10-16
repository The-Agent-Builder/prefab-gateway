"""
密钥保管库服务

负责存储和检索用户的密钥（加密存储到数据库）
"""
import logging
from typing import Optional
from datetime import datetime
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import UserSecret, SecretStatus
from services.encryption import encryption_service

logger = logging.getLogger(__name__)


class VaultService:
    """
    密钥保管库服务
    
    使用数据库持久化用户密钥，并通过 Fernet 对称加密保护敏感信息
    """
    
    def __init__(self) -> None:
        self.encryption = encryption_service
        logger.info("VaultService initialized (database + encryption mode)")
    
    async def store_secret(
        self,
        user_id: str,
        prefab_id: str,
        secret_name: str,
        secret_value: str,
        db: AsyncSession,
        description: Optional[str] = None
    ) -> None:
        """
        存储密钥（加密后存储到数据库）
        
        Args:
            user_id: 用户 ID
            prefab_id: 预制件 ID
            secret_name: 密钥名称
            secret_value: 密钥值
            db: 数据库会话
            description: 可选的密钥描述
        """
        # 加密密钥值
        encrypted_value = self.encryption.encrypt(secret_value)
        
        # 查找是否已存在
        stmt = select(UserSecret).where(
            and_(
                UserSecret.user_id == user_id,
                UserSecret.prefab_id == prefab_id,
                UserSecret.secret_name == secret_name
            )
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            # 更新现有密钥
            existing.secret_value = encrypted_value
            existing.updated_at = datetime.utcnow()
            existing.status = SecretStatus.ACTIVE
            if description:
                existing.description = description
            logger.info(f"Updated secret: user={user_id}, prefab={prefab_id}, name={secret_name}")
        else:
            # 创建新密钥
            new_secret = UserSecret(
                user_id=user_id,
                prefab_id=prefab_id,
                secret_name=secret_name,
                secret_value=encrypted_value,
                description=description,
                status=SecretStatus.ACTIVE
            )
            db.add(new_secret)
            logger.info(f"Created secret: user={user_id}, prefab={prefab_id}, name={secret_name}")
        
        await db.commit()
    
    async def get_secret(
        self,
        user_id: str,
        prefab_id: str,
        secret_name: str,
        db: AsyncSession
    ) -> Optional[str]:
        """
        获取密钥（从数据库读取并解密）
        
        Args:
            user_id: 用户 ID
            prefab_id: 预制件 ID
            secret_name: 密钥名称
            db: 数据库会话
        
        Returns:
            密钥值（明文），如果不存在返回 None
        """
        stmt = select(UserSecret).where(
            and_(
                UserSecret.user_id == user_id,
                UserSecret.prefab_id == prefab_id,
                UserSecret.secret_name == secret_name,
                UserSecret.status == SecretStatus.ACTIVE
            )
        )
        result = await db.execute(stmt)
        secret_record = result.scalar_one_or_none()
        
        if secret_record:
            # 更新最后使用时间
            secret_record.last_used_at = datetime.utcnow()
            await db.commit()
            
            # 解密并返回
            plaintext = self.encryption.decrypt(secret_record.secret_value)
            logger.debug(f"Retrieved secret: user={user_id}, prefab={prefab_id}, name={secret_name}")
            return plaintext
        else:
            logger.warning(f"Secret not found: user={user_id}, prefab={prefab_id}, name={secret_name}")
            return None
    
    async def delete_secret(
        self,
        user_id: str,
        prefab_id: str,
        secret_name: str,
        db: AsyncSession
    ) -> bool:
        """
        删除密钥（软删除，标记为 DISABLED）
        
        Args:
            user_id: 用户 ID
            prefab_id: 预制件 ID
            secret_name: 密钥名称
            db: 数据库会话
        
        Returns:
            True 如果成功删除，False 如果密钥不存在
        """
        stmt = select(UserSecret).where(
            and_(
                UserSecret.user_id == user_id,
                UserSecret.prefab_id == prefab_id,
                UserSecret.secret_name == secret_name
            )
        )
        result = await db.execute(stmt)
        secret_record = result.scalar_one_or_none()
        
        if secret_record:
            secret_record.status = SecretStatus.DISABLED
            secret_record.updated_at = datetime.utcnow()
            await db.commit()
            logger.info(f"Deleted secret: user={user_id}, prefab={prefab_id}, name={secret_name}")
            return True
        return False
    
    async def list_secrets(
        self,
        user_id: str,
        db: AsyncSession,
        prefab_id: Optional[str] = None
    ) -> list[tuple[str, str]]:
        """
        列出用户的所有密钥
        
        Args:
            user_id: 用户 ID
            db: 数据库会话
            prefab_id: 可选的预制件 ID 过滤器
        
        Returns:
            (prefab_id, secret_name) 元组列表
        """
        stmt = select(UserSecret.prefab_id, UserSecret.secret_name).where(
            and_(
                UserSecret.user_id == user_id,
                UserSecret.status == SecretStatus.ACTIVE
            )
        )
        
        if prefab_id:
            stmt = stmt.where(UserSecret.prefab_id == prefab_id)
        
        result = await db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]


# 全局单例
vault_service = VaultService()

