好的，完全理解。您需要一份**从零开始的、完整的、与我们最终确定的密钥管理架构完全对齐的** `prefab-gateway` PRD。之前版本中的残留信息确实会造成混淆。

这份全新的 v1.0 文档将是我们 API 网关开发的最终“宪法”。

---

### **PRD: API 网关 (`prefab-gateway`)**

**版本:** 1.0 (最终工程实现版)
**负责人:** [平台工程团队]

#### **1. 概述 (Overview)**

*   **使命:** 作为 AI 预制件生态系统**唯一、安全、可控的流量入口**。它负责认证、授权、路由、校验，并执行最核心的**运行时密钥注入**，将外部的用户意图安全地转化为对内部 Knave 服务的可信调用。
*   **技术栈:** Python 3.11+, FastAPI, Pydantic, httpx (for async downstream calls)。
*   **核心原则:** 零信任、无状态、高可用、低延迟、可观测性。

---

#### **2. 模块一: API 端点定义 (The Contract)**

**FR-1.1: 认证与授权**
*   **机制:** 所有端点都必须通过 FastAPI `Security` 依赖进行保护，该依赖从 `Authorization: Bearer <TOKEN>` 请求头中解析 JWT。
*   **Token 载荷:** JWT 必须包含 `user_id` 和 `scopes` (权限范围)。
*   **失败响应:** Token 无效、过期或权限不足，将返回 `401 Unauthorized` 或 `403 Forbidden`。

**FR-1.2: 核心执行端点 (`/v1/run`)**
*   **Endpoint:** `POST /v1/run`
*   **职责:** 接收并串行执行一个或多个预制件调用。
*   **成功响应:** `200 OK` - `{"job_id": "<uuid>", "status": "COMPLETED", "results": [...]}`
*   **错误响应:** (详见 FR-6 错误处理规范)
    *   `4xx`: 客户端错误，如认证、授权、格式或校验失败。
    *   `5xx`: 服务端错误，如内部错误或下游服务不可用。

**FR-1.3: 预制件规格查询端点 (`/v1/prefabs/.../spec`)**
*   **Endpoint:** `GET /v1/prefabs/{prefab_id}/{version}/spec`
*   **职责:** 为 Code AI 提供指定预制件的详细接口规格。
*   **成功响应:** `200 OK` - 返回 `prefab-manifest.json` 中 `functions` 部分的 JSON 对象。

**FR-1.4: 密钥管理端点 (`/v1/secrets`)**
*   **Endpoint:** `POST /v1/secrets`
*   **职责:** 供平台前端调用，用于用户安全地创建或更新其密钥。
*   **输入体:** `{"prefab_id": "weather-api-v1", "secret_name": "API_KEY", "secret_value": "sk-..."}`
*   **行为:** 调用密钥保管库服务，将 `secret_value` 与 `(user_id, prefab_id, secret_name)` 绑定。
*   **成功响应:** `204 No Content`

---

#### **3. 模块二: 核心处理逻辑 (`/v1/run` Deep Dive)**

1.  **初始化:** 生成唯一的 `request_id` 用于全链路日志追踪。

2.  **认证 & 授权:** FastAPI 安全依赖自动执行，获得 `user_id`。

3.  **请求体验证:** FastAPI 使用 Pydantic 模型自动验证请求体的基本结构。

4.  **串行处理 `calls` 列表:**
    a. **获取规格 (Spec Fetching):**
        *   从 **SpecCache (Redis)** 中读取 `spec:{id}:{version}` 的接口规格。
        *   **失败:** 缓存未命中 -> 返回 `404 Not Found`。
    b. **输入校验 (Input Validation):**
        *   **[核心]** 遍历预制件规格中定义的 `parameters`，与用户提供的 `inputs` 进行严格比对 (类型、必填项等)。
        *   **失败:** 不匹配 -> 返回 `422 Unprocessable Entity`。
    c. **权限检查 (ACL Check):**
        *   **[核心]** 对于 `InputFile` 类型的参数，调用 `AccessControlService.can_read(user_id, s3_uri)` 验证用户对该 S3 对象的读取权限。
        *   **失败:** 无权限 -> 返回 `403 Forbidden`。
    d. **密钥解析 (Secret Resolution):**
        *   **[核心]** 遍历预制件规格中 `functions[].secrets` 声明的**每一个** `secret`。
        *   对于每一个声明的 `secret.name` (e.g., `"API_KEY"`), 调用**密钥保管库**服务: `real_secret = Vault.get_secret(user_id, prefab_id, secret.name)`。
        *   **失败:** 密钥未配置 -> 返回 `400 Bad Request`，错误信息为 "Secret `API_KEY` for prefab `weather-api-v1` is not configured."。
        *   将解析出的真实密钥存入一个临时的 `resolved_secrets` 字典中。
    e. **构建下游请求 (Downstream Payload Construction):**
        *   创建一个新的 JSON 载荷。
        *   将用户提供的 `inputs` 复制到载荷中。
        *   **将 `resolved_secrets` 字典作为一个特殊的 `_secrets` 字段注入到载荷中。**
            ```json
            {
              "inputs": { "city": "London" },
              "_secrets": {
                "API_KEY": "sk-real-weather-api-key-xxxxxx"
              }
            }
            ```
    f. **路由与调用 (Routing & Invocation):**
        *   从服务发现机制解析出 Knative 服务地址。
        *   使用 `httpx.AsyncClient` 将**构建好的下游请求**发送给 Knative 服务。
        *   **失败:** 下游服务返回非 2xx 响应 -> 终止执行，返回 `503 Service Unavailable`。
    g. **响应处理 (Response Handling):**
        *   接收到 Knative 服务的响应。
        *   **[核心]** 对于 `OutputFile` 类型的字段，调用 `AccessControlService.grant_ownership(user_id, new_s3_uri)`，为新生成的文件赋予用户所有权。

5.  **聚合与返回:** 将所有 `calls` 的执行结果聚合到 `results` 数组中，构建 `200 OK` 响应。

---

#### **4. 模块三: 预留的扩展能力 (Extensibility Hooks)**

为了支持未来的业务发展，`prefab-gateway` 的设计中必须预留以下逻辑钩子点：

*   **FR-4.1: 计费与审计 (Metering & Auditing):**
    *   在核心逻辑的 **4.c** 和 **4.f** 步骤，必须预留出可以轻松添加异步调用 `MeteringService` 的位置。这将用于记录每次 API 调用的详细信息，为未来的计费和用量分析打下基础。

*   **FR-4.2: 结果缓存 (Result Caching):**
    *   在核心逻辑的 **4.b** 步骤之后，可以增加一个检查点：`if CachingService.has_result(prefab_id, version, inputs)`，如果对于完全相同的输入已经有了缓存的结果，可以直接从缓存返回，而无需调用下游的 Knative 服务。

*   **FR-4.3: A/B 测试与灰度发布 (A/B Testing & Canary Releases):**
    *   在核心逻辑的 **4.d** 步骤，路由逻辑可以被扩展。除了直接解析服务地址，还可以调用一个 `ExperimentationService`，根据 `user_id` 或其他请求特征，动态地将流量路由到不同版本的预制件（例如，将 10% 的流量路由到 `v1.2.0-beta`）。

---

#### **5. 数据模型 (Pydantic Models)**

```python
# --- Request Models ---
class PrefabInput(BaseModel):
    class Config:
        extra = 'allow'

class PrefabCall(BaseModel):
    prefab_id: str
    version: str
    inputs: PrefabInput
    # 注意：密钥信息不由客户端在此处提供

class RunRequestPayload(BaseModel):
    calls: list[PrefabCall]

# --- Response Models ---
class CallResult(BaseModel):
    status: str
    output: dict | None = None
    error: dict | None = None

class RunResponsePayload(BaseModel):
    job_id: str
    status: str
    results: list[CallResult]

# --- Secret Management Models ---
class SecretPayload(BaseModel):
    prefab_id: str
    secret_name: str
    secret_value: str
```

---

#### **6. 错误处理规范 (Error Handling)**

| Status Code | Error Code (in body) | 描述 |
| :--- | :--- | :--- |
| 400 | `BAD_REQUEST` | 请求 JSON 格式无效，或**请求了需要但未配置的密钥**。 |
| 401 | `UNAUTHENTICATED` | JWT 无效或缺失。 |
| 403 | `PERMISSION_DENIED` | JWT 有效但权限不足，或试图访问不属于自己的 S3 资源。 |
| 404 | `NOT_FOUND` | 请求的 `prefab_id` 或 `version` 不存在。 |
| 422 | `VALIDATION_ERROR` | `inputs` 与预制件规格不匹配。 |
| 503 | `SERVICE_UNAVAILABLE` | 下游 Knative 服务无响应、超时或返回内部错误。 |
| 500 | `INTERNAL_SERVER_ERROR` | 网关发生未捕获的意外错误。 |