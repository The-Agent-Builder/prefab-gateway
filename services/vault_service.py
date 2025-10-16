"""
密钥保管库服务

负责存储和检索用户的密钥
"""
import logging
from typing import Optional, Dict
from config.settings import settings

logger = logging.getLogger(__name__)


class VaultService:
    """
    密钥保管库服务
    
    当前使用内存存储作为演示实现
    生产环境应该集成 HashiCorp Vault 或 AWS Secrets Manager
    """
    
    def __init__(self) -> None:
        # 内存存储: {(user_id, prefab_id, secret_name): secret_value}
        self._secrets: Dict[tuple[str, str, str], str] = {}
        logger.info("VaultService initialized (in-memory mode)")
    
    async def store_secret(
        self,
        user_id: str,
        prefab_id: str,
        secret_name: str,
        secret_value: str
    ) -> None:
        """
        存储密钥
        
        Args:
            user_id: 用户 ID
            prefab_id: 预制件 ID
            secret_name: 密钥名称
            secret_value: 密钥值
        """
        key = (user_id, prefab_id, secret_name)
        self._secrets[key] = secret_value
        logger.info(f"Stored secret: user={user_id}, prefab={prefab_id}, name={secret_name}")
    
    async def get_secret(
        self,
        user_id: str,
        prefab_id: str,
        secret_name: str
    ) -> Optional[str]:
        """
        获取密钥
        
        Args:
            user_id: 用户 ID
            prefab_id: 预制件 ID
            secret_name: 密钥名称
        
        Returns:
            密钥值，如果不存在返回 None
        """
        key = (user_id, prefab_id, secret_name)
        secret_value = self._secrets.get(key)
        
        if secret_value:
            logger.debug(f"Retrieved secret: user={user_id}, prefab={prefab_id}, name={secret_name}")
        else:
            logger.warning(f"Secret not found: user={user_id}, prefab={prefab_id}, name={secret_name}")
        
        return secret_value
    
    async def delete_secret(
        self,
        user_id: str,
        prefab_id: str,
        secret_name: str
    ) -> bool:
        """
        删除密钥
        
        Args:
            user_id: 用户 ID
            prefab_id: 预制件 ID
            secret_name: 密钥名称
        
        Returns:
            True 如果成功删除，False 如果密钥不存在
        """
        key = (user_id, prefab_id, secret_name)
        if key in self._secrets:
            del self._secrets[key]
            logger.info(f"Deleted secret: user={user_id}, prefab={prefab_id}, name={secret_name}")
            return True
        return False
    
    async def list_secrets(
        self,
        user_id: str,
        prefab_id: Optional[str] = None
    ) -> list[tuple[str, str]]:
        """
        列出用户的所有密钥
        
        Args:
            user_id: 用户 ID
            prefab_id: 可选的预制件 ID 过滤器
        
        Returns:
            (prefab_id, secret_name) 元组列表
        """
        results = []
        for (uid, pid, sname), _ in self._secrets.items():
            if uid == user_id and (prefab_id is None or pid == prefab_id):
                results.append((pid, sname))
        return results


# 全局单例
vault_service = VaultService()

