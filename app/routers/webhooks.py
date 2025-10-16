"""
Webhook 路由 - 接收来自 prefab-factory 的通知
"""
import logging
import hashlib
import hmac
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from db.models import WebhookEvent, DeploymentStatus
from services.spec_cache_service import spec_cache_service
from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    验证 HMAC 签名
    
    Args:
        payload: 请求体字节
        signature: 请求头中的签名
        secret: 共享密钥
    
    Returns:
        True 如果签名有效
    """
    if not signature:
        return False
    
    # 计算期望的签名
    expected = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    # 安全比较
    return hmac.compare_digest(signature, expected)


@router.post(
    "/factory",
    summary="接收 Factory 部署通知",
    description="Prefab Factory 在部署完成后调用此端点通知 Gateway"
)
async def receive_factory_webhook(
    request: Request,
    x_webhook_signature: str = Header(None, alias="X-Webhook-Signature"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """
    接收来自 prefab-factory 的 webhook 通知
    
    事件类型：
    - deployment.success: 部署成功
    - deployment.failed: 部署失败
    - deployment.started: 开始部署
    
    载荷示例：
    ```json
    {
        "event_id": "deploy-123",
        "event_type": "deployment.success",
        "prefab_id": "weather-api-v1",
        "version": "1.0.0",
        "knative_service_url": "http://weather-api-v1.prefab.svc.cluster.local",
        "deployment_status": "deployed",
        "timestamp": "2025-10-16T10:30:00Z"
    }
    ```
    """
    # 读取原始请求体
    body = await request.body()
    
    # 验证签名（如果配置了 webhook secret）
    webhook_secret = getattr(settings, 'WEBHOOK_SECRET', None)
    if webhook_secret:
        if not verify_signature(body, x_webhook_signature or "", webhook_secret):
            logger.warning("Invalid webhook signature")
            raise HTTPException(status_code=401, detail="Invalid signature")
    
    # 解析 JSON
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")
    
    # 提取事件信息
    event_id = payload.get("event_id")
    event_type = payload.get("event_type")
    prefab_id = payload.get("prefab_id")
    version = payload.get("version")
    knative_service_url = payload.get("knative_service_url")
    deployment_status_str = payload.get("deployment_status")
    
    if not all([event_id, event_type, prefab_id, version]):
        raise HTTPException(
            status_code=400,
            detail="Missing required fields: event_id, event_type, prefab_id, version"
        )
    
    logger.info(
        f"Received webhook: event_id={event_id}, type={event_type}, "
        f"prefab={prefab_id}:{version}"
    )
    
    # 检查事件是否已处理（幂等性）
    from sqlalchemy import select
    stmt = select(WebhookEvent).where(WebhookEvent.event_id == event_id)
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    
    if existing:
        if existing.processed:
            logger.info(f"Webhook event already processed: {event_id}")
            return {
                "status": "already_processed",
                "event_id": event_id
            }
        else:
            logger.warning(f"Webhook event exists but not processed: {event_id}")
    else:
        # 创建新的 webhook 事件记录
        new_event = WebhookEvent(
            event_id=event_id,
            source="factory",
            event_type=event_type,
            prefab_id=prefab_id,
            version=version,
            payload=payload,
            signature=x_webhook_signature
        )
        db.add(new_event)
        await db.commit()
        await db.refresh(new_event)
        existing = new_event
    
    # 处理事件
    try:
        if event_type == "deployment.success":
            # 更新部署状态为 DEPLOYED
            success = await spec_cache_service.update_deployment_status(
                prefab_id=prefab_id,
                version=version,
                status=DeploymentStatus.DEPLOYED,
                db=db,
                knative_service_url=knative_service_url
            )
            
            if success:
                logger.info(f"Updated spec deployment status: {prefab_id}:{version} → DEPLOYED")
            else:
                logger.warning(f"Failed to update spec deployment status: {prefab_id}:{version}")
        
        elif event_type == "deployment.failed":
            # 更新部署状态为 FAILED
            await spec_cache_service.update_deployment_status(
                prefab_id=prefab_id,
                version=version,
                status=DeploymentStatus.FAILED,
                db=db
            )
            logger.info(f"Updated spec deployment status: {prefab_id}:{version} → FAILED")
        
        elif event_type == "deployment.started":
            # 更新部署状态为 DEPLOYING
            await spec_cache_service.update_deployment_status(
                prefab_id=prefab_id,
                version=version,
                status=DeploymentStatus.DEPLOYING,
                db=db
            )
            logger.info(f"Updated spec deployment status: {prefab_id}:{version} → DEPLOYING")
        
        # 标记事件为已处理
        existing.processed = True
        existing.processed_at = None  # SQLAlchemy will set this
        await db.commit()
        
        return {
            "status": "processed",
            "event_id": event_id,
            "event_type": event_type,
            "prefab_id": prefab_id,
            "version": version
        }
        
    except Exception as e:
        logger.error(f"Error processing webhook event: {e}")
        existing.processing_error = str(e)
        existing.retry_count += 1
        await db.commit()
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process webhook: {str(e)}"
        )


@router.get(
    "/events/{event_id}",
    summary="查询 Webhook 事件状态"
)
async def get_webhook_event(
    event_id: str,
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """查询特定 webhook 事件的处理状态"""
    from sqlalchemy import select
    
    stmt = select(WebhookEvent).where(WebhookEvent.event_id == event_id)
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return {
        "event_id": event.event_id,
        "source": event.source,
        "event_type": event.event_type,
        "prefab_id": event.prefab_id,
        "version": event.version,
        "processed": event.processed,
        "processed_at": event.processed_at.isoformat() if event.processed_at else None,
        "retry_count": event.retry_count,
        "processing_error": event.processing_error,
        "created_at": event.created_at.isoformat()
    }

