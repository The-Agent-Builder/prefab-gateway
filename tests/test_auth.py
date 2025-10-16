"""
认证和授权测试
"""
import pytest
from fastapi import status


def test_health_check_no_auth(client):
    """健康检查端点不需要认证"""
    response = client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "healthy"


def test_run_without_token(client):
    """没有 token 应该返回 401"""
    response = client.post("/v1/run", json={"calls": []})
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_run_with_invalid_token(client):
    """无效 token 应该返回 401"""
    headers = {"Authorization": "Bearer invalid-token"}
    response = client.post("/v1/run", json={"calls": []}, headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_run_with_valid_token(client, auth_headers):
    """有效 token 应该通过认证"""
    response = client.post("/v1/run", json={"calls": []}, headers=auth_headers)
    # 空调用列表也应该返回 200（不是认证错误）
    assert response.status_code == status.HTTP_200_OK

