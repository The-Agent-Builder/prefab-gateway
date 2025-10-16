"""
预制件规格缓存服务 (SpecCache Service)

负责缓存和检索预制件的接口规格（manifest）
双层缓存架构：L1=Redis, L2=MySQL
"""
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import redis.asyncio as redis
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings
from db.models import PrefabSpec, DeploymentStatus

logger = logging.getLogger(__name__)


class SpecCacheService:
    """
    预制件规格缓存服务
    
    双层缓存架构：
    - L1 (Redis): 快速访问，TTL 管理
    - L2 (MySQL): 持久化存储，包含部署状态
    """
    
    def __init__(self) -> None:
        self._redis: Optional[redis.Redis] = None
        # 内存回退存储（Redis 不可用时使用）
        self._memory_cache: Dict[str, Dict[str, Any]] = {}
        self._use_memory = False
        self._redis_ttl = 3600  # Redis 缓存 1 小时
    
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
    
    async def get_spec(
        self,
        prefab_id: str,
        version: str,
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """
        获取预制件规格（双层缓存）
        
        查询顺序：Redis → MySQL → None
        
        Args:
            prefab_id: 预制件 ID
            version: 版本号
            db: 数据库会话
        
        Returns:
            预制件规格字典，如果不存在返回 None
        """
        key = self._make_key(prefab_id, version)
        
        # L1: 尝试从 Redis/内存获取
        try:
            if self._use_memory:
                spec_json = self._memory_cache.get(key)
                if spec_json:
                    logger.debug(f"Spec cache HIT (L1-memory): {key}")
                    return spec_json
            else:
                if self._redis:
                    spec_json_str = await self._redis.get(key)
                    if spec_json_str:
                        logger.debug(f"Spec cache HIT (L1-redis): {key}")
                        return json.loads(spec_json_str)
        except Exception as e:
            logger.warning(f"L1 cache read error: {e}, falling back to L2")
        
        # L2: 从数据库获取
        try:
            stmt = select(PrefabSpec).where(
                and_(
                    PrefabSpec.prefab_id == prefab_id,
                    PrefabSpec.version == version
                )
            )
            result = await db.execute(stmt)
            record = result.scalar_one_or_none()
            
            if record:
                logger.debug(f"Spec cache HIT (L2-db): {key}")
                spec = record.spec_json
                
                # 更新统计
                record.last_called_at = datetime.utcnow()
                record.call_count += 1
                await db.commit()
                
                # 写回 L1 缓存
                await self._set_redis_cache(key, spec)
                
                return spec
            else:
                logger.debug(f"Spec cache MISS (all layers): {key}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting spec from database: {e}")
            return None
    
    async def set_spec(
        self,
        prefab_id: str,
        version: str,
        spec: Dict[str, Any],
        db: AsyncSession,
        knative_service_url: Optional[str] = None,
        deployment_status: DeploymentStatus = DeploymentStatus.PENDING,
        artifact_url: Optional[str] = None
    ) -> bool:
        """
        缓存预制件规格（双层写入）
        
        写入顺序：MySQL → Redis
        
        Args:
            prefab_id: 预制件 ID
            version: 版本号
            spec: 预制件规格
            db: 数据库会话
            knative_service_url: Knative 服务地址
            deployment_status: 部署状态
            artifact_url: 制品 URL
        
        Returns:
            True 如果成功，False 否则
        """
        key = self._make_key(prefab_id, version)
        
        try:
            # L2: 写入数据库（或更新）
            stmt = select(PrefabSpec).where(
                and_(
                    PrefabSpec.prefab_id == prefab_id,
                    PrefabSpec.version == version
                )
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if existing:
                # 更新现有记录
                existing.spec_json = spec
                existing.updated_at = datetime.utcnow()
                if knative_service_url:
                    existing.knative_service_url = knative_service_url
                if deployment_status:
                    existing.deployment_status = deployment_status
                if artifact_url:
                    existing.artifact_url = artifact_url
                if deployment_status == DeploymentStatus.DEPLOYED:
                    existing.deployed_at = datetime.utcnow()
                logger.info(f"Updated spec in DB: {key}")
            else:
                # 创建新记录
                new_spec = PrefabSpec(
                    prefab_id=prefab_id,
                    version=version,
                    spec_json=spec,
                    knative_service_url=knative_service_url,
                    deployment_status=deployment_status,
                    artifact_url=artifact_url
                )
                db.add(new_spec)
                logger.info(f"Created spec in DB: {key}")
            
            await db.commit()
            
            # L1: 写入 Redis
            await self._set_redis_cache(key, spec)
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting spec: {e}")
            await db.rollback()
            return False
    
    async def _set_redis_cache(self, key: str, spec: Dict[str, Any]) -> None:
        """写入 Redis 缓存（内部方法）"""
        try:
            if self._use_memory:
                self._memory_cache[key] = spec
            else:
                if self._redis:
                    spec_json_str = json.dumps(spec)
                    await self._redis.setex(key, self._redis_ttl, spec_json_str)
        except Exception as e:
            logger.warning(f"Failed to set Redis cache: {e}")
    
    async def delete_spec(
        self,
        prefab_id: str,
        version: str,
        db: AsyncSession
    ) -> bool:
        """
        删除缓存的规格（双层删除）
        
        Args:
            prefab_id: 预制件 ID
            version: 版本号
            db: 数据库会话
        
        Returns:
            True 如果成功删除，False 如果不存在
        """
        key = self._make_key(prefab_id, version)
        deleted = False
        
        try:
            # L2: 从数据库删除
            stmt = select(PrefabSpec).where(
                and_(
                    PrefabSpec.prefab_id == prefab_id,
                    PrefabSpec.version == version
                )
            )
            result = await db.execute(stmt)
            record = result.scalar_one_or_none()
            
            if record:
                await db.delete(record)
                await db.commit()
                logger.info(f"Deleted spec from DB: {key}")
                deleted = True
            
            # L1: 从 Redis 删除
            if self._use_memory:
                if key in self._memory_cache:
                    del self._memory_cache[key]
            else:
                if self._redis:
                    await self._redis.delete(key)
            
            return deleted
            
        except Exception as e:
            logger.error(f"Error deleting spec: {e}")
            await db.rollback()
            return False
    
    async def update_deployment_status(
        self,
        prefab_id: str,
        version: str,
        status: DeploymentStatus,
        db: AsyncSession,
        knative_service_url: Optional[str] = None
    ) -> bool:
        """
        更新部署状态（供 webhook 调用）
        
        Args:
            prefab_id: 预制件 ID
            version: 版本号
            status: 新的部署状态
            db: 数据库会话
            knative_service_url: Knative 服务地址（可选）
        
        Returns:
            True 如果成功，False 否则
        """
        try:
            stmt = select(PrefabSpec).where(
                and_(
                    PrefabSpec.prefab_id == prefab_id,
                    PrefabSpec.version == version
                )
            )
            result = await db.execute(stmt)
            record = result.scalar_one_or_none()
            
            if record:
                record.deployment_status = status
                record.updated_at = datetime.utcnow()
                if knative_service_url:
                    record.knative_service_url = knative_service_url
                if status == DeploymentStatus.DEPLOYED:
                    record.deployed_at = datetime.utcnow()
                
                await db.commit()
                logger.info(f"Updated deployment status: {prefab_id}:{version} → {status.value}")
                
                # 使 Redis 缓存失效（下次查询时会从数据库重新加载）
                key = self._make_key(prefab_id, version)
                if self._use_memory:
                    self._memory_cache.pop(key, None)
                else:
                    if self._redis:
                        await self._redis.delete(key)
                
                return True
            else:
                logger.warning(f"Spec not found for status update: {prefab_id}:{version}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating deployment status: {e}")
            await db.rollback()
            return False


# 全局单例
spec_cache_service = SpecCacheService()

