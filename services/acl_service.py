"""
访问控制服务 (ACL Service)

负责验证用户对 S3 资源的访问权限
"""
import logging
from typing import Set
from config.settings import settings

logger = logging.getLogger(__name__)


class AccessControlService:
    """
    访问控制服务
    
    当前使用内存存储作为演示实现
    生产环境应该集成真实的 ACL 系统
    """
    
    def __init__(self) -> None:
        # 内存存储: {user_id: set(s3_uris)}
        self._user_files: dict[str, Set[str]] = {}
        logger.info("AccessControlService initialized (in-memory mode)")
    
    async def can_read(self, user_id: str, s3_uri: str) -> bool:
        """
        检查用户是否有权限读取指定的 S3 对象
        
        Args:
            user_id: 用户 ID
            s3_uri: S3 URI (例如: s3://bucket/path/to/file)
        
        Returns:
            True 如果有权限，False 否则
        """
        user_files = self._user_files.get(user_id, set())
        has_permission = s3_uri in user_files
        
        if has_permission:
            logger.debug(f"User {user_id} has read permission for {s3_uri}")
        else:
            logger.warning(f"User {user_id} does NOT have read permission for {s3_uri}")
        
        return has_permission
    
    async def can_write(self, user_id: str, s3_uri: str) -> bool:
        """
        检查用户是否有权限写入指定的 S3 对象
        
        当前实现：与 can_read 相同
        生产环境可能需要更细粒度的权限控制
        
        Args:
            user_id: 用户 ID
            s3_uri: S3 URI
        
        Returns:
            True 如果有权限，False 否则
        """
        return await self.can_read(user_id, s3_uri)
    
    async def grant_ownership(self, user_id: str, s3_uri: str) -> None:
        """
        授予用户对 S3 对象的所有权
        
        这通常在创建新文件时调用
        
        Args:
            user_id: 用户 ID
            s3_uri: S3 URI
        """
        if user_id not in self._user_files:
            self._user_files[user_id] = set()
        
        self._user_files[user_id].add(s3_uri)
        logger.info(f"Granted ownership: user={user_id}, file={s3_uri}")
    
    async def revoke_access(self, user_id: str, s3_uri: str) -> bool:
        """
        撤销用户对 S3 对象的访问权限
        
        Args:
            user_id: 用户 ID
            s3_uri: S3 URI
        
        Returns:
            True 如果成功撤销，False 如果用户本来就没有权限
        """
        if user_id in self._user_files and s3_uri in self._user_files[user_id]:
            self._user_files[user_id].remove(s3_uri)
            logger.info(f"Revoked access: user={user_id}, file={s3_uri}")
            return True
        return False
    
    async def list_user_files(self, user_id: str) -> list[str]:
        """
        列出用户有权访问的所有文件
        
        Args:
            user_id: 用户 ID
        
        Returns:
            S3 URI 列表
        """
        return list(self._user_files.get(user_id, set()))


# 全局单例
acl_service = AccessControlService()

