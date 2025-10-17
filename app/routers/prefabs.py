"""
/v1/prefabs 端点 - 预制件规格查询
"""
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies.auth import get_current_user, User
from services.spec_cache_service import spec_cache_service
from db.session import get_db
from db.models import PrefabSpec, DeploymentStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/prefabs", tags=["Prefabs"])


@router.get("")
async def list_prefabs(
    status: str = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> List[Dict[str, Any]]:
    """
    列出所有预制件
    
    Args:
        status: 可选，筛选部署状态 (deployed, deploying, failed 等)
        user: 当前用户
        db: 数据库会话
    
    Returns:
        预制件列表
    """
    query = select(PrefabSpec)
    
    # 筛选状态
    if status:
        try:
            deployment_status = DeploymentStatus(status)
            query = query.where(PrefabSpec.deployment_status == deployment_status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}"
            )
    
    # 按更新时间降序排序
    query = query.order_by(PrefabSpec.updated_at.desc())
    
    result = await db.execute(query)
    specs = result.scalars().all()
    
    # 转换为响应格式
    prefabs = []
    for spec in specs:
        spec_data = spec.spec_json if spec.spec_json else {}
        prefabs.append({
            "id": spec.prefab_id,
            "version": spec.version,
            "name": spec_data.get("name", spec.prefab_id),
            "description": spec_data.get("description", ""),
            "tags": spec_data.get("tags", []),
            "deployment_status": spec.deployment_status.value,
            "knative_service_url": spec.knative_service_url,
            "functions": spec_data.get("functions", []),
            "deployed_at": spec.deployed_at.isoformat() if spec.deployed_at else None,
            "updated_at": spec.updated_at.isoformat() if spec.updated_at else None
        })
    
    logger.info(f"Listed {len(prefabs)} prefabs for user {user.user_id}")
    return prefabs


@router.get("/{prefab_id}/{version}/spec")
async def get_prefab_spec(
    prefab_id: str,
    version: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    获取预制件的接口规格
    
    为 Code AI 提供详细的函数签名信息
    
    Args:
        prefab_id: 预制件 ID
        version: 版本号
        user: 当前用户
        db: 数据库会话
    
    Returns:
        预制件的 functions 规格
    """
    spec = await spec_cache_service.get_spec(prefab_id, version, db)
    
    if not spec:
        logger.warning(f"Spec not found: {prefab_id}@{version}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prefab {prefab_id}@{version} not found"
        )
    
    # 只返回 functions 部分（Code AI 需要的信息）
    return {
        "id": spec.get("id", prefab_id),
        "version": spec.get("version", version),
        "name": spec.get("name", ""),
        "description": spec.get("description", ""),
        "functions": spec.get("functions", [])
    }


@router.post("/{prefab_id}/{version}/spec", status_code=status.HTTP_204_NO_CONTENT)
async def cache_prefab_spec(
    prefab_id: str,
    version: str,
    spec: Dict[str, Any],
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> None:
    """
    缓存预制件规格（管理员端点）
    
    这个端点通常由 prefab-factory 在部署完成后调用
    """
    # 简化实现：这里应该检查用户是否有管理员权限
    await spec_cache_service.set_spec(prefab_id, version, spec, db)
    logger.info(f"Cached spec for {prefab_id}@{version}")

