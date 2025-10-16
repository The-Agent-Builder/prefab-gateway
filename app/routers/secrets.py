"""
/v1/secrets 端点 - 密钥管理
"""
import logging
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies.auth import get_current_user, User
from models.requests import SecretPayload
from services.vault_service import vault_service
from db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Secrets"])


@router.post("/secrets", status_code=status.HTTP_204_NO_CONTENT)
async def store_secret(
    payload: SecretPayload,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Response:
    """
    存储或更新用户的密钥
    
    Args:
        payload: 密钥信息
        user: 当前用户
        db: 数据库会话
    
    Returns:
        204 No Content
    """
    await vault_service.store_secret(
        user_id=user.user_id,
        prefab_id=payload.prefab_id,
        secret_name=payload.secret_name,
        secret_value=payload.secret_value,
        db=db
    )
    
    logger.info(f"User {user.user_id} stored secret {payload.secret_name} for prefab {payload.prefab_id}")
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/secrets")
async def list_all_secrets(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    列出用户配置的所有密钥（所有 prefab）
    
    注意：不返回密钥值，只返回密钥元信息
    """
    secrets = await vault_service.list_secrets(user.user_id, db)
    
    # 转换为前端期望的格式
    secrets_list = [
        {
            "prefab_id": prefab_id,
            "secret_name": secret_name
        }
        for prefab_id, secret_name in secrets
    ]
    
    return {
        "secrets": secrets_list
    }


@router.get("/secrets/{prefab_id}")
async def list_secrets_for_prefab(
    prefab_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    列出用户为指定预制件配置的所有密钥名称
    
    注意：不返回密钥值，只返回名称列表
    """
    secrets = await vault_service.list_secrets(user.user_id, db, prefab_id)
    secret_names = [name for _, name in secrets]
    
    return {
        "prefab_id": prefab_id,
        "secret_names": secret_names
    }


@router.delete("/secrets/{prefab_id}/{secret_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_secret(
    prefab_id: str,
    secret_name: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> Response:
    """
    删除用户的密钥
    """
    await vault_service.delete_secret(user.user_id, prefab_id, secret_name, db)
    
    logger.info(f"User {user.user_id} deleted secret {secret_name} for prefab {prefab_id}")
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)

