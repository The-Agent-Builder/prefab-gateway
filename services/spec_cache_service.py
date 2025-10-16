"""
预制件规格缓存服务 (SpecCache Service)

负责缓存和检索预制件的接口规格（manifest）
"""
import json
import logging
from typing import Optional, Dict, Any
import redis.asyncio as redis
from config.settings import settings

logger = logging.getLogger(__name__)


class SpecCacheService:
    """
    预制件规格缓存服务
    
    使用 Redis 作为缓存存储
    """
    
    def __init__(self) -> None:
        self._redis: Optional[redis.Redis] = None
        # 内存回退存储（Redis 不可用时使用）
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._use_memory = False
    
    async def connect(self) -> None:
        """连接到 Redis"""
        try:
            self._redis = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=True,
            )
            # 测试连接
            await self._redis.ping()
            logger.info(f"SpecCacheService connected to Redis at {settings.redis_host}:{settings.redis_port}")
        except Exception as e:
            logger.warning(f"Failed to connect to Redis: {e}. Using in-memory cache as fallback.")
            self._use_memory = True
    
    async def close(self) -> None:
        """关闭 Redis 连接"""
        if self._redis:
            await self._redis.close()
            logger.info("SpecCacheService disconnected from Redis")
    
    def _make_key(self, prefab_id: str, version: str) -> str:
        """生成缓存键"""
        return f"spec:{prefab_id}:{version}"
    
    async def get_spec(self, prefab_id: str, version: str) -> Optional[Dict[str, Any]]:
        """
        获取预制件规格
        
        Args:
            prefab_id: 预制件 ID
            version: 版本号
        
        Returns:
            预制件规格字典，如果不存在返回 None
        """
        key = self._make_key(prefab_id, version)
        
        try:
            if self._use_memory:
                spec_json = self._memory_cache.get(key)
                if spec_json:
                    logger.debug(f"Spec cache HIT (memory): {key}")
                    return spec_json
            else:
                spec_json_str = await self._redis.get(key)  # type: ignore
                if spec_json_str:
                    logger.debug(f"Spec cache HIT (redis): {key}")
                    return json.loads(spec_json_str)
            
            logger.debug(f"Spec cache MISS: {key}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting spec from cache: {e}")
            return None
    
    async def set_spec(
        self,
        prefab_id: str,
        version: str,
        spec: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        缓存预制件规格
        
        Args:
            prefab_id: 预制件 ID
            version: 版本号
            spec: 预制件规格
            ttl: 过期时间（秒），None 表示不过期
        
        Returns:
            True 如果成功，False 否则
        """
        key = self._make_key(prefab_id, version)
        
        try:
            if self._use_memory:
                self._memory_cache[key] = spec
                logger.info(f"Cached spec (memory): {key}")
            else:
                spec_json_str = json.dumps(spec)
                if ttl:
                    await self._redis.setex(key, ttl, spec_json_str)  # type: ignore
                else:
                    await self._redis.set(key, spec_json_str)  # type: ignore
                logger.info(f"Cached spec (redis): {key}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting spec in cache: {e}")
            return False
    
    async def delete_spec(self, prefab_id: str, version: str) -> bool:
        """
        删除缓存的规格
        
        Args:
            prefab_id: 预制件 ID
            version: 版本号
        
        Returns:
            True 如果成功删除，False 如果不存在
        """
        key = self._make_key(prefab_id, version)
        
        try:
            if self._use_memory:
                if key in self._memory_cache:
                    del self._memory_cache[key]
                    logger.info(f"Deleted spec (memory): {key}")
                    return True
            else:
                result = await self._redis.delete(key)  # type: ignore
                if result > 0:
                    logger.info(f"Deleted spec (redis): {key}")
                    return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting spec from cache: {e}")
            return False


# 全局单例
spec_cache_service = SpecCacheService()

