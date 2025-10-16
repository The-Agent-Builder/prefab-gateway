"""
/v1/run 端点 - 核心执行引擎
"""
import logging
import uuid
import httpx
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import get_current_user, User
from models import RunRequestPayload, RunResponsePayload, CallResult, CallStatus, ErrorResponse
from services import vault_service, acl_service, spec_cache_service
from config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["Execution"])


@router.post(
    "/run",
    response_model=RunResponsePayload,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    }
)
async def run_prefabs(
    payload: RunRequestPayload,
    user: User = Depends(get_current_user)
) -> RunResponsePayload:
    """
    执行一个或多个预制件调用
    
    这是网关的核心端点，负责：
    1. 验证用户身份和权限
    2. 获取并验证预制件规格
    3. 解析和注入密钥
    4. 路由到 Knative 服务
    5. 处理响应和文件权限
    """
    # 生成唯一的请求 ID
    request_id = str(uuid.uuid4())
    logger.info(f"[{request_id}] Processing run request with {len(payload.calls)} calls for user {user.user_id}")
    
    results: list[CallResult] = []
    
    # 串行处理每个调用
    for idx, call in enumerate(payload.calls):
        logger.info(f"[{request_id}] Processing call {idx + 1}/{len(payload.calls)}: {call.prefab_id}@{call.version}")
        
        try:
            # Step 1: 获取预制件规格
            spec = await spec_cache_service.get_spec(call.prefab_id, call.version)
            if not spec:
                logger.error(f"[{request_id}] Spec not found: {call.prefab_id}@{call.version}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Prefab {call.prefab_id}@{call.version} not found"
                )
            
            # 获取函数定义
            function_def = None
            for func in spec.get("functions", []):
                if func.get("name") == call.function_name:
                    function_def = func
                    break
            
            if not function_def:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Function {call.function_name} not found in prefab {call.prefab_id}"
                )
            
            # Step 2: 输入校验
            await validate_inputs(call.inputs, function_def, request_id)
            
            # Step 3: 权限检查（InputFile）
            await check_input_file_permissions(call.inputs, function_def, user.user_id, request_id)
            
            # Step 4: 密钥解析
            resolved_secrets = await resolve_secrets(
                user.user_id,
                call.prefab_id,
                function_def,
                request_id
            )
            
            # Step 5: 构建下游请求
            downstream_payload = {
                "inputs": call.inputs,
                "_secrets": resolved_secrets
            }
            
            # Step 6: 路由与调用
            output = await invoke_knative_service(
                call.prefab_id,
                call.version,
                call.function_name,
                downstream_payload,
                request_id
            )
            
            # Step 7: 响应处理（OutputFile）
            await handle_output_files(output, function_def, user.user_id, request_id)
            
            # 成功
            results.append(CallResult(
                status=CallStatus.SUCCESS,
                output=output
            ))
            logger.info(f"[{request_id}] Call {idx + 1} completed successfully")
            
        except HTTPException:
            # 已知错误，直接抛出
            raise
        except Exception as e:
            # 未知错误
            logger.error(f"[{request_id}] Call {idx + 1} failed with unexpected error: {e}", exc_info=True)
            results.append(CallResult(
                status=CallStatus.FAILED,
                error={"message": str(e), "type": type(e).__name__}
            ))
    
    # 构建响应
    overall_status = "COMPLETED" if all(r.status == CallStatus.SUCCESS for r in results) else "PARTIAL_SUCCESS"
    
    return RunResponsePayload(
        job_id=request_id,
        status=overall_status,
        results=results
    )


async def validate_inputs(
    inputs: Dict[str, Any],
    function_def: Dict[str, Any],
    request_id: str
) -> None:
    """验证输入参数"""
    parameters = function_def.get("parameters", [])
    
    for param in parameters:
        param_name = param.get("name")
        param_required = param.get("required", True)
        param_type = param.get("type", "string")
        
        if param_required and param_name not in inputs:
            logger.error(f"[{request_id}] Missing required parameter: {param_name}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Missing required parameter: {param_name}"
            )
        
        # 简化的类型检查
        if param_name in inputs:
            value = inputs[param_name]
            type_check_map = {
                "string": str,
                "number": (int, float),
                "integer": int,
                "boolean": bool,
                "array": list,
                "object": dict,
            }
            expected_type = type_check_map.get(param_type)
            if expected_type and not isinstance(value, expected_type):
                logger.error(f"[{request_id}] Type mismatch for {param_name}: expected {param_type}, got {type(value)}")
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Type mismatch for parameter {param_name}: expected {param_type}"
                )


async def check_input_file_permissions(
    inputs: Dict[str, Any],
    function_def: Dict[str, Any],
    user_id: str,
    request_id: str
) -> None:
    """检查 InputFile 类型参数的权限"""
    parameters = function_def.get("parameters", [])
    
    for param in parameters:
        if param.get("type") == "InputFile":
            param_name = param.get("name")
            if param_name in inputs:
                s3_uri = inputs[param_name]
                if not await acl_service.can_read(user_id, s3_uri):
                    logger.error(f"[{request_id}] User {user_id} lacks read permission for {s3_uri}")
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied for file: {s3_uri}"
                    )


async def resolve_secrets(
    user_id: str,
    prefab_id: str,
    function_def: Dict[str, Any],
    request_id: str
) -> Dict[str, str]:
    """解析函数所需的所有密钥"""
    resolved_secrets = {}
    secrets = function_def.get("secrets", [])
    
    for secret in secrets:
        secret_name = secret.get("name")
        secret_required = secret.get("required", True)
        
        secret_value = await vault_service.get_secret(user_id, prefab_id, secret_name)
        
        if secret_value is None and secret_required:
            logger.error(f"[{request_id}] Required secret not configured: {secret_name}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Secret '{secret_name}' for prefab '{prefab_id}' is not configured"
            )
        
        if secret_value:
            resolved_secrets[secret_name] = secret_value
            logger.debug(f"[{request_id}] Resolved secret: {secret_name}")
    
    return resolved_secrets


async def invoke_knative_service(
    prefab_id: str,
    version: str,
    function_name: str,
    payload: Dict[str, Any],
    request_id: str
) -> Dict[str, Any]:
    """调用 Knative 服务"""
    # 构建服务 URL
    service_url = f"http://{prefab_id}.{settings.knative_namespace}.{settings.knative_domain_suffix}"
    endpoint_url = f"{service_url}/invoke/{function_name}"
    
    logger.info(f"[{request_id}] Invoking: {endpoint_url}")
    
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        try:
            response = await client.post(endpoint_url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"[{request_id}] Knative response: {result}")
            return result
            
        except httpx.HTTPStatusError as e:
            logger.error(f"[{request_id}] Knative service returned error {e.response.status_code}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Downstream service error: {e.response.status_code}"
            )
        except httpx.TimeoutException:
            logger.error(f"[{request_id}] Knative service timeout")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Downstream service timeout"
            )
        except Exception as e:
            logger.error(f"[{request_id}] Failed to invoke Knative service: {e}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to invoke service: {str(e)}"
            )


async def handle_output_files(
    output: Dict[str, Any],
    function_def: Dict[str, Any],
    user_id: str,
    request_id: str
) -> None:
    """处理 OutputFile 类型的输出，授予用户所有权"""
    returns = function_def.get("returns", {})
    properties = returns.get("properties", {})
    
    for field_name, field_def in properties.items():
        if field_def.get("type") == "OutputFile" and field_name in output:
            s3_uri = output[field_name]
            await acl_service.grant_ownership(user_id, s3_uri)
            logger.info(f"[{request_id}] Granted ownership: user={user_id}, file={s3_uri}")

