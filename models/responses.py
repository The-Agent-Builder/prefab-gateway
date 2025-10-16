"""
响应模型定义
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, Optional
from enum import Enum


class CallStatus(str, Enum):
    """调用状态枚举"""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class CallResult(BaseModel):
    """
    单个调用结果
    """
    status: CallStatus = Field(..., description="调用状态")
    output: Optional[Dict[str, Any]] = Field(None, description="函数输出（成功时）")
    error: Optional[Dict[str, Any]] = Field(None, description="错误信息（失败时）")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "SUCCESS",
                "output": {
                    "success": True,
                    "city": "London",
                    "temperature": 15.5,
                    "condition": "Cloudy"
                }
            }
        }


class RunResponsePayload(BaseModel):
    """
    /v1/run 端点的响应体
    """
    job_id: str = Field(..., description="任务 ID")
    status: str = Field(..., description="总体状态", example="COMPLETED")
    results: list[CallResult] = Field(..., description="每个调用的结果")
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "COMPLETED",
                "results": [
                    {
                        "status": "SUCCESS",
                        "output": {
                            "success": True,
                            "city": "London",
                            "temperature": 15.5
                        }
                    }
                ]
            }
        }


class ErrorResponse(BaseModel):
    """
    错误响应
    """
    error_code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    details: Optional[Dict[str, Any]] = Field(None, description="错误详情")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error_code": "VALIDATION_ERROR",
                "message": "输入参数与预制件规格不匹配",
                "details": {
                    "field": "city",
                    "issue": "required field missing"
                }
            }
        }

