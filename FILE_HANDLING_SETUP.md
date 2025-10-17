# InputFile/OutputFile 文件处理架构部署指南

## 📋 架构概述

Gateway 和 Prefab 通过**共享 PVC (ReadWriteMany)** 传递文件：

```
用户 → Gateway [下载到 PVC] → Prefab [处理] → Gateway [上传到 S3]
          ↓                           ↓
       [清理]                    [读写 PVC]
```

## ✅ 已完成的工作

### 1. 基础设施 (K8s/Knative)
- ✅ 创建共享 PVC: `prefab-workspace` (200Gi, alicloud-nas-subpath)
- ✅ Deployer 自动为所有 Prefab 挂载 `/mnt/prefab-workspace`
- ✅ PVC 已绑定并可用

### 2. Gateway 代码
- ✅ 创建文件处理服务: `services/file_handler_service.py`
- ✅ 集成到 `app/routers/run.py`：
  - 创建独立 workspace
  - 下载 InputFile（S3 → PVC）
  - 上传 OutputFile（PVC → S3）
  - 清理 workspace
- ✅ 自动清理守护进程（每 5 分钟，清理 1 小时前的目录）
- ✅ S3 文件操作（使用 aioboto3 异步上传下载）

### 3. Prefab Runtime
- ✅ 简化为只处理本地文件
- ✅ 接收 workspace 参数
- ✅ 自动注入密钥到环境变量

## 🔧 S3 配置指南

### 1. 安装依赖

已完成，使用异步 S3 客户端：

```bash
uv add boto3 aioboto3
```

### 2. 环境变量配置

Gateway 需要以下环境变量才能访问 S3：

```bash
# AWS 凭证（必需）
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"

# AWS 区域（可选，默认从 AWS CLI 配置读取）
export AWS_DEFAULT_REGION="cn-northwest-1"

# S3 存储桶（可选，默认: prefab-outputs）
export S3_BUCKET="prefab-outputs"

# S3 路径前缀（可选，用于共享存储桶时区分项目）
# 留空: s3://bucket/prefab-outputs/...
# 设置: s3://bucket/{prefix}/prefab-outputs/...
export S3_PREFIX="gtplanner"  # 或 "project-a", "team-x" 等

# PVC 挂载路径（可选，默认: /mnt/prefab-workspace）
export WORKSPACE_ROOT="/mnt/prefab-workspace"
```

### 3. 配置文件

在 `config/settings.py` 中已添加：

```python
class Settings(BaseSettings):
    workspace_root: str = "/mnt/prefab-workspace"
    s3_bucket: str = "prefab-outputs"
    s3_prefix: str = ""  # 路径前缀
    s3_region: Optional[str] = None
    s3_endpoint_url: Optional[str] = None
```

### 3.1 共享存储桶场景

如果多个项目共享同一个 S3 存储桶，强烈推荐使用 `S3_PREFIX` 区分项目：

**场景 1: 多项目共享桶**
```bash
# 项目 A (GTPlanner)
S3_BUCKET=company-shared-bucket
S3_PREFIX=gtplanner

# 项目 B (其他项目)
S3_BUCKET=company-shared-bucket
S3_PREFIX=project-b
```

**存储结构**:
```
company-shared-bucket/
├── gtplanner/
│   └── prefab-outputs/
│       └── 2025/10/17/...
├── project-b/
│   └── prefab-outputs/
│       └── 2025/10/17/...
```

**场景 2: 独立存储桶（无需前缀）**
```bash
S3_BUCKET=prefab-outputs
S3_PREFIX=  # 留空
```

**存储结构**:
```
prefab-outputs/
└── prefab-outputs/
    └── 2025/10/17/...
```

### 4. S3 文件操作实现

已在 `services/file_handler_service.py` 中实现：

- **`_download_from_s3()`**: 从 S3 下载文件到 PVC
  - 解析 `s3://bucket/key` 格式
  - 异步下载到 workspace
  - 错误处理和日志记录

- **`_upload_to_s3()`**: 上传文件从 PVC 到 S3
  - 生成唯一 S3 key: `prefab-outputs/{year}/{month}/{day}/{request_id}/{uuid}.ext`
  - 按日期组织，便于管理
  - 异步上传
  - 返回 S3 URL

### 5. S3 路径规范

#### 5.1 OutputFile（Gateway 自动上传）

Gateway 按日期组织输出文件：

**无前缀**:
```
s3://bucket/prefab-outputs/{year}/{month}/{day}/{request_id}/{uuid}.ext
```

**带前缀** (推荐用于共享存储桶):
```
s3://bucket/{prefix}/prefab-outputs/{year}/{month}/{day}/{request_id}/{uuid}.ext
```

**示例**:
```
# 独立存储桶
s3://prefab-outputs/prefab-outputs/2025/10/17/abc123-def456/uuid-xxx.pdf

# 共享存储桶（设置 S3_PREFIX=gtplanner）
s3://company-bucket/gtplanner/prefab-outputs/2025/10/17/abc123-def456/uuid-xxx.pdf
```

**优势**:
- ✅ 按日期分组，便于管理和清理
- ✅ 避免单个目录文件过多
- ✅ 支持按时间范围查询
- ✅ 前缀隔离，多项目安全共享存储桶

#### 5.2 InputFile（前端上传，推荐规范）

**推荐路径结构**:

```
# 无前缀
s3://bucket/prefab-inputs/{user_id}/{year}/{month}/{day}/{filename}

# 带前缀（多项目共享桶）
s3://bucket/{prefix}/prefab-inputs/{user_id}/{year}/{month}/{day}/{filename}
```

**示例**:
```
# 独立存储桶
s3://prefab-outputs/prefab-inputs/user-123/2025/10/17/document.pdf

# 共享存储桶（GTPlanner 项目）
s3://company-bucket/gtplanner/prefab-inputs/user-123/2025/10/17/document.pdf
```

**前端上传示例（GTPlanner-frontend）**:

```typescript
// 配置（从环境变量读取）
const S3_BUCKET = process.env.NEXT_PUBLIC_S3_BUCKET;  // 如: "company-bucket"
const S3_PREFIX = process.env.NEXT_PUBLIC_S3_PREFIX;  // 如: "gtplanner" 或 ""

// 生成 S3 key
const now = new Date();
const datePath = `${now.getFullYear()}/${(now.getMonth()+1).toString().padStart(2,'0')}/${now.getDate().toString().padStart(2,'0')}`;

// 构建完整路径（自动处理前缀）
const prefix = S3_PREFIX ? `${S3_PREFIX}/` : '';
const s3Key = `${prefix}prefab-inputs/${userId}/${datePath}/${file.name}`;

// 上传到 S3
await s3Client.putObject({
  Bucket: S3_BUCKET,
  Key: s3Key,
  Body: file
});

// 传递给 Gateway
const s3Url = `s3://${S3_BUCKET}/${s3Key}`;
// 结果: s3://company-bucket/gtplanner/prefab-inputs/user-123/2025/10/17/file.pdf
```

**临时文件（可选）**:

如果不需要长期保存，可使用 `temp/` 前缀：

```
s3://bucket/prefab-inputs/temp/{uuid}/{filename}
```

然后配置 S3 生命周期策略自动删除 7 天前的文件。

### 6. S3 兼容存储支持

#### 6.1 阿里云 OSS 配置（推荐）

阿里云 OSS 完全兼容 S3 协议，配置示例：

```bash
# 从阿里云控制台获取 AccessKey
export AWS_ACCESS_KEY_ID="LTAI5t..."           # 替换为你的 AccessKey ID
export AWS_SECRET_ACCESS_KEY="xxx..."          # 替换为你的 AccessKey Secret

# 指定 OSS 区域和 Endpoint
export S3_REGION="oss-cn-hangzhou"             # OSS 区域
export S3_ENDPOINT_URL="https://oss-cn-hangzhou.aliyuncs.com"

# 存储桶名称
export S3_BUCKET="prefab-outputs"              # 替换为你的 Bucket 名称
```

**阿里云区域列表**:
- `oss-cn-hangzhou`: 华东1（杭州）
- `oss-cn-shanghai`: 华东2（上海）
- `oss-cn-beijing`: 华北2（北京）
- `oss-cn-shenzhen`: 华南1（深圳）
- [更多区域](https://help.aliyun.com/document_detail/31837.html)

#### 6.2 AWS S3 配置

```bash
export AWS_ACCESS_KEY_ID="your-access-key"
export AWS_SECRET_ACCESS_KEY="your-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
export S3_BUCKET="prefab-outputs"
# 不设置 S3_ENDPOINT_URL（使用 AWS 默认）
```

#### 6.3 MinIO 配置

```bash
export AWS_ACCESS_KEY_ID="minioadmin"
export AWS_SECRET_ACCESS_KEY="minioadmin"
export S3_ENDPOINT_URL="http://minio:9000"
export S3_BUCKET="prefab-outputs"
```

## 📦 部署步骤

### 1. Gateway 部署

Gateway 需要挂载相同的 PVC。如果使用 Knative：

```yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: prefab-gateway
  namespace: prefab-functions
spec:
  template:
    spec:
      containers:
      - image: prefab-gateway:latest
        volumeMounts:
        - name: workspace
          mountPath: /mnt/prefab-workspace
      volumes:
      - name: workspace
        persistentVolumeClaim:
          claimName: prefab-workspace
```

如果使用普通 Deployment，类似配置即可。

### 2. 重新部署 Prefab

运行一次部署任务，Deployer 会自动为新 Prefab 挂载 PVC：

```bash
# 触发 prefab-factory 重新构建和部署
curl -X POST http://prefab-factory/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "id": "hello-world-prefab",
    "version": "1.0.0",
    "repo_url": "https://github.com/ketd/Hello-World"
  }'
```

### 3. 验证 PVC 挂载

```bash
# 检查 Prefab Pod 是否挂载了 PVC
kubectl get pod -n prefab-functions -l serving.knative.dev/service=hello-world-prefab
POD_NAME=<从上面获取>
kubectl describe pod $POD_NAME -n prefab-functions | grep -A 5 "Volumes:"

# 应该能看到 prefab-workspace PVC
```

### 4. 测试文件处理

```bash
# 1. 前端上传文件到 S3，获得 URL: s3://bucket/files/test.mp4

# 2. 调用 Gateway
curl -X POST http://gateway/v1/run \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "calls": [{
      "prefab_id": "hello-world-prefab",
      "version": "1.0.0",
      "function_name": "process_video",
      "inputs": {
        "input_video": "s3://bucket/files/test.mp4"
      }
    }]
  }'

# 3. 查看日志
kubectl logs -n prefab-functions -l app=prefab-gateway --tail=100
```

## 🔍 监控与调试

### 检查 PVC 使用情况

```bash
# 查看 PVC 状态
kubectl get pvc -n prefab-functions prefab-workspace

# 查看磁盘使用（需要进入 Gateway Pod）
kubectl exec -it <gateway-pod> -n prefab-functions -- df -h /mnt/prefab-workspace
kubectl exec -it <gateway-pod> -n prefab-functions -- du -sh /mnt/prefab-workspace/*
```

### 查看清理日志

```bash
# Gateway 日志中搜索清理记录
kubectl logs -n prefab-functions <gateway-pod> | grep -i "cleanup"

# 应该能看到：
# - "Cleanup summary: removed N workspaces, freed X.XX MB"
# - "Workspace disk usage: XX.X%"
```

### 手动清理（紧急情况）

```bash
# 进入任意挂载了 PVC 的 Pod
kubectl exec -it <pod-name> -n prefab-functions -- sh

# 手动清理
cd /mnt/prefab-workspace
find . -type d -mtime +1 -exec rm -rf {} +
```

## ⚠️ 注意事项

1. **S3 操作待实现**：目前文件下载/上传逻辑只是占位，需要实现 boto3 集成

2. **Gateway 必须挂载 PVC**：否则无法创建 workspace

3. **存储容量规划**：
   - 当前：200Gi
   - 估算：并发任务数 × 平均文件大小 × 2
   - 建议：监控使用率，超过 70% 时扩容

4. **清理策略**：
   - 自动清理：每 5 分钟，删除 1 小时前的目录
   - 可在 `app/main.py` 中调整参数

5. **成本**：
   - 阿里云 NAS (200Gi 性能型)：约 ¥70/月
   - 容量型更便宜但性能较低

## 🚀 下一步

1. 实现 S3 下载/上传逻辑（需要 AWS/阿里云 credentials）
2. 部署 Gateway 并挂载 PVC
3. 重新部署现有 Prefab
4. 编写端到端测试

## 📚 相关文件

- PVC 配置: `prefab-factory/k8s/prefab-workspace-pvc.yaml`
- 文件处理服务: `prefab-gateway/services/file_handler_service.py`
- Gateway 路由: `prefab-gateway/app/routers/run.py`
- Prefab Runtime: `prefab-factory/runtime/handler.py`
- Deployer: `prefab-factory/app/deployer.py`

