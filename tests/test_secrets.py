"""
密钥管理测试
"""
import pytest
from fastapi import status


def test_store_secret(client, auth_headers, test_user_id):
    """测试存储密钥"""
    payload = {
        "prefab_id": "test-prefab",
        "secret_name": "API_KEY",
        "secret_value": "sk-test-12345"
    }
    
    response = client.post("/v1/secrets", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT


def test_list_secrets(client, auth_headers, test_user_id):
    """测试列出密钥"""
    # 先存储一个密钥
    payload = {
        "prefab_id": "test-prefab",
        "secret_name": "API_KEY",
        "secret_value": "sk-test-12345"
    }
    client.post("/v1/secrets", json=payload, headers=auth_headers)
    
    # 列出密钥
    response = client.get("/v1/secrets/test-prefab", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["prefab_id"] == "test-prefab"
    assert "API_KEY" in data["secret_names"]


def test_delete_secret(client, auth_headers):
    """测试删除密钥"""
    # 先存储
    payload = {
        "prefab_id": "test-prefab",
        "secret_name": "API_KEY",
        "secret_value": "sk-test-12345"
    }
    client.post("/v1/secrets", json=payload, headers=auth_headers)
    
    # 删除
    response = client.delete("/v1/secrets/test-prefab/API_KEY", headers=auth_headers)
    assert response.status_code == status.HTTP_204_NO_CONTENT

