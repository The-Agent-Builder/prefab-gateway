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
  - 下载 InputFile (TODO: S3 实现)
  - 上传 OutputFile (TODO: S3 实现)
  - 清理 workspace
- ✅ 自动清理守护进程（每 5 分钟，清理 1 小时前的目录）

### 3. Prefab Runtime
- ✅ 简化为只处理本地文件
- ✅ 接收 workspace 参数
- ✅ 自动注入密钥到环境变量

## 🔧 待实现功能

### S3 文件操作 (标记为 TODO)

在 `services/file_handler_service.py` 中：

```python
# TODO: 实现这两个方法
async def _download_from_s3(self, s3_url, workspace, filename, request_id) -> Path:
    # 使用 boto3 从 S3 下载文件到 PVC
    pass

async def _upload_to_s3(self, local_path, request_id) -> str:
    # 使用 boto3 上传文件到 S3，返回 S3 URL
    pass
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

