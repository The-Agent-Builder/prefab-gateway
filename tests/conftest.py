"""
Pytest 配置和 fixtures
"""
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from datetime import datetime, timedelta

from app.main import app
from config.settings import settings
from services import vault_service, acl_service, spec_cache_service


@pytest.fixture
def client():
    """测试客户端"""
    return TestClient(app)


@pytest.fixture
def test_user_id():
    """测试用户 ID"""
    return "test-user-123"


@pytest.fixture
def test_token(test_user_id):
    """生成测试 JWT token"""
    payload = {
        "sub": test_user_id,
        "username": "testuser",
        "scopes": ["prefab:execute", "prefab:read"],
        "exp": datetime.utcnow() + timedelta(minutes=30)
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token


@pytest.fixture
def auth_headers(test_token):
    """认证请求头"""
    return {"Authorization": f"Bearer {test_token}"}


@pytest.fixture
async def sample_spec():
    """示例预制件规格"""
    return {
        "id": "test-prefab",
        "version": "1.0.0",
        "name": "测试预制件",
        "functions": [
            {
                "name": "test_function",
                "description": "测试函数",
                "parameters": [
                    {
                        "name": "input_text",
                        "type": "string",
                        "required": True
                    }
                ],
                "returns": {
                    "type": "object"
                },
                "secrets": [
                    {
                        "name": "TEST_API_KEY",
                        "description": "测试 API 密钥",
                        "required": True
                    }
                ]
            }
        ]
    }


@pytest.fixture(autouse=True)
async def setup_test_data(sample_spec):
    """每个测试前设置测试数据"""
    # 缓存测试规格
    await spec_cache_service.set_spec("test-prefab", "1.0.0", sample_spec)
    
    yield
    
    # 清理
    # 注意：实际生产中可能需要清理数据库

