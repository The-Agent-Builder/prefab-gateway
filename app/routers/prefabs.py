"""
/v1/prefabs 端点 - 预制件规格查询
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, User
from services import spec_cache_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/prefabs", tags=["Prefabs"])


@router.get("/{prefab_id}/{version}/spec")
async def get_prefab_spec(
    prefab_id: str,
    version: str,
    user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    """
    获取预制件的接口规格
    
    为 Code AI 提供详细的函数签名信息
    
    Args:
        prefab_id: 预制件 ID
        version: 版本号
        user: 当前用户
    
    Returns:
        预制件的 functions 规格
    """
    spec = await spec_cache_service.get_spec(prefab_id, version)
    
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
    user: User = Depends(get_current_user)
) -> None:
    """
    缓存预制件规格（管理员端点）
    
    这个端点通常由 prefab-factory 在部署完成后调用
    """
    # 简化实现：这里应该检查用户是否有管理员权限
    await spec_cache_service.set_spec(prefab_id, version, spec)
    logger.info(f"Cached spec for {prefab_id}@{version}")

