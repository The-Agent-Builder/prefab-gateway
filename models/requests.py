"""
请求模型定义
"""
from pydantic import BaseModel, Field
from typing import Any, Dict


class PrefabInput(BaseModel):
    """
    预制件输入参数
    
    使用 extra='allow' 允许任意字段，因为不同预制件有不同的参数
    """
    
    class Config:
        extra = "allow"  # 允许额外字段
    
    def model_dump(self, **kwargs: Any) -> Dict[str, Any]:
        """重写 model_dump 以返回所有字段"""
        return super().model_dump(**kwargs)


class PrefabCall(BaseModel):
    """
    单个预制件调用请求
    """
    prefab_id: str = Field(..., description="预制件 ID", example="weather-api-v1")
    version: str = Field(..., description="版本号", example="1.0.0")
    function_name: str = Field(..., description="要调用的函数名", example="get_current_weather")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="函数输入参数")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prefab_id": "weather-api-v1",
                "version": "1.0.0",
                "function_name": "get_current_weather",
                "inputs": {
                    "city": "London"
                }
            }
        }


class RunRequestPayload(BaseModel):
    """
    /v1/run 端点的请求体
    """
    calls: list[PrefabCall] = Field(..., description="要执行的预制件调用列表")
    
    class Config:
        json_schema_extra = {
            "example": {
                "calls": [
                    {
                        "prefab_id": "weather-api-v1",
                        "version": "1.0.0",
                        "function_name": "get_current_weather",
                        "inputs": {
                            "city": "London"
                        }
                    }
                ]
            }
        }


class SecretPayload(BaseModel):
    """
    密钥配置请求体
    """
    prefab_id: str = Field(..., description="预制件 ID", example="weather-api-v1")
    secret_name: str = Field(..., description="密钥名称", example="API_KEY")
    secret_value: str = Field(..., description="密钥值", example="sk-...")
    
    class Config:
        json_schema_extra = {
            "example": {
                "prefab_id": "weather-api-v1",
                "secret_name": "API_KEY",
                "secret_value": "sk-real-api-key-xxxxxx"
            }
        }

