"""
认证和授权依赖
"""
import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from pydantic import BaseModel
from config.settings import settings

logger = logging.getLogger(__name__)

# HTTP Bearer token 安全方案
security = HTTPBearer()


class User(BaseModel):
    """用户信息"""
    user_id: str
    username: Optional[str] = None
    scopes: list[str] = []


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    从 JWT token 中解析当前用户
    
    Args:
        credentials: HTTP Authorization 凭证
    
    Returns:
        User 对象
    
    Raises:
        HTTPException: 如果 token 无效或过期
    """
    token = credentials.credentials
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # 解码 JWT（需要验证 audience）
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            audience='prefab-gateway'  # 验证 audience 字段
        )
        
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.warning("JWT payload missing 'sub' field")
            raise credentials_exception
        
        username: Optional[str] = payload.get("username")
        scopes: list[str] = payload.get("scopes", [])
        
        user = User(
            user_id=user_id,
            username=username,
            scopes=scopes
        )
        
        logger.debug(f"Authenticated user: {user_id}")
        return user
        
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise credentials_exception from e


def require_scope(required_scope: str):
    """
    创建一个依赖，要求用户具有特定的权限范围
    
    Args:
        required_scope: 所需的权限范围
    
    Returns:
        依赖函数
    """
    async def scope_checker(user: User = Depends(get_current_user)) -> User:
        if required_scope not in user.scopes and "admin" not in user.scopes:
            logger.warning(f"User {user.user_id} lacks required scope: {required_scope}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required scope: {required_scope}"
            )
        return user
    
    return scope_checker

