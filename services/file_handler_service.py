"""
文件处理服务 - 处理 InputFile 和 OutputFile

负责：
1. 从 S3 下载 InputFile 到共享 PVC
2. 上传 OutputFile 从共享 PVC 到 S3
3. 管理临时工作目录的生命周期
"""
import asyncio
import logging
import shutil
import time
import uuid
from pathlib import Path
from typing import Dict, Any, Optional

import aioboto3
from botocore.exceptions import ClientError

from config.settings import settings

logger = logging.getLogger(__name__)


class FileHandlerService:
    """文件处理服务"""
    
    def __init__(
        self, 
        workspace_root: str = "/mnt/prefab-workspace",
        s3_bucket: Optional[str] = None,
        s3_endpoint_url: Optional[str] = None,
        s3_region: Optional[str] = None
    ):
        """
        初始化文件处理服务
        
        Args:
            workspace_root: PVC 挂载路径
            s3_bucket: S3 存储桶名称（用于上传 OutputFile）
            s3_endpoint_url: S3 自定义 endpoint（用于阿里云 OSS 等 S3 兼容存储）
            s3_region: S3 区域名称
        """
        self.workspace_root = Path(workspace_root)
        self._cleanup_task = None
        self.s3_bucket = s3_bucket or "prefab-outputs"  # 默认输出桶
        self.s3_endpoint_url = s3_endpoint_url
        self.s3_region = s3_region
        
        # 初始化 aioboto3 session
        self.s3_session = aioboto3.Session()
        
        # 确保根目录存在
        if not self.workspace_root.exists():
            logger.warning(f"Workspace root does not exist: {self.workspace_root}")
            logger.warning("File handling will be disabled (PVC not mounted)")
            self.workspace_root = None
        else:
            logger.info(f"File handler initialized with workspace: {self.workspace_root}")
            logger.info(f"S3 output bucket: {self.s3_bucket}")
            if self.s3_endpoint_url:
                logger.info(f"S3 custom endpoint: {self.s3_endpoint_url}")
    
    def create_workspace(self, job_id: Optional[str] = None) -> Path:
        """
        为任务创建独立的工作目录
        
        Args:
            job_id: 任务ID，如果为 None 则自动生成
        
        Returns:
            工作目录路径
        """
        if not self.workspace_root:
            raise RuntimeError("PVC not mounted, cannot create workspace")
        
        if not job_id:
            job_id = str(uuid.uuid4())
        
        workspace = self.workspace_root / job_id
        workspace.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Created workspace: {workspace}")
        return workspace
    
    async def download_input_files(
        self,
        function_def: Dict[str, Any],
        inputs: Dict[str, Any],
        workspace: Path,
        request_id: str
    ) -> Dict[str, Any]:
        """
        下载 InputFile 类型的输入参数到 workspace
        
        Args:
            function_def: 函数定义（来自 manifest）
            inputs: 用户输入参数
            workspace: 工作目录
            request_id: 请求 ID
        
        Returns:
            处理后的输入参数（S3 URL 替换为本地路径）
        """
        if not self.workspace_root:
            logger.warning(f"[{request_id}] PVC not mounted, skipping file download")
            return inputs
        
        processed_inputs = inputs.copy()
        parameters = function_def.get("parameters", [])
        
        for param in parameters:
            param_name = param.get("name")
            param_type = param.get("type")
            
            if param_type == "InputFile" and param_name in inputs:
                s3_url = inputs[param_name]
                logger.info(f"[{request_id}] Processing InputFile: {param_name} = {s3_url}")
                
                # 从 S3 下载到 workspace
                local_path = await self._download_from_s3(s3_url, workspace, param_name, request_id)
                processed_inputs[param_name] = str(local_path)
        
        return processed_inputs
    
    async def upload_output_files(
        self,
        function_def: Dict[str, Any],
        output: Dict[str, Any],
        workspace: Path,
        request_id: str
    ) -> Dict[str, Any]:
        """
        上传 OutputFile 类型的输出到 S3
        
        Args:
            function_def: 函数定义
            output: 函数返回值
            workspace: 工作目录
            request_id: 请求 ID
        
        Returns:
            处理后的输出（本地路径替换为 S3 URL）
        """
        if not self.workspace_root:
            logger.warning(f"[{request_id}] PVC not mounted, skipping file upload")
            return output
        
        processed_output = output.copy()
        returns = function_def.get("returns", {})
        properties = returns.get("properties", {})
        
        for field_name, field_def in properties.items():
            if field_def.get("type") == "OutputFile" and field_name in output:
                local_path = Path(output[field_name])
                logger.info(f"[{request_id}] Processing OutputFile: {field_name} = {local_path}")
                
                # 验证文件存在
                if not local_path.exists():
                    logger.error(f"[{request_id}] Output file not found: {local_path}")
                    raise FileNotFoundError(f"Output file not found: {local_path}")
                
                # 上传到 S3
                s3_url = await self._upload_to_s3(local_path, request_id)
                processed_output[field_name] = s3_url
        
        return processed_output
    
    def cleanup_workspace(self, workspace: Path, request_id: str) -> None:
        """
        清理工作目录
        
        Args:
            workspace: 要清理的工作目录
            request_id: 请求 ID
        """
        if not workspace or not workspace.exists():
            return
        
        try:
            shutil.rmtree(workspace)
            logger.info(f"[{request_id}] Cleaned up workspace: {workspace}")
        except Exception as e:
            logger.error(f"[{request_id}] Failed to cleanup workspace {workspace}: {e}")
    
    async def _download_from_s3(
        self,
        s3_url: str,
        workspace: Path,
        param_name: str,
        request_id: str
    ) -> Path:
        """
        从 S3 下载文件到 workspace
        
        Args:
            s3_url: S3 URL (格式: s3://bucket/path/to/file.ext)
            workspace: 工作目录
            param_name: 参数名（用于生成本地文件名）
            request_id: 请求 ID
        
        Returns:
            本地文件路径
        """
        # 解析 S3 URL
        if not s3_url.startswith("s3://"):
            raise ValueError(f"Invalid S3 URL: {s3_url}")
        
        url_parts = s3_url[5:].split("/", 1)
        bucket = url_parts[0]
        key = url_parts[1] if len(url_parts) > 1 else ""
        
        if not key:
            raise ValueError(f"Invalid S3 URL (missing key): {s3_url}")
        
        # 生成本地文件路径（保留原文件扩展名）
        file_ext = Path(key).suffix
        local_filename = f"input_{param_name}{file_ext}"
        local_path = workspace / local_filename
        
        logger.info(f"[{request_id}] Downloading from S3: {bucket}/{key} -> {local_path}")
        
        try:
            # 构建 client 参数
            client_kwargs = {}
            if self.s3_endpoint_url:
                client_kwargs['endpoint_url'] = self.s3_endpoint_url
            if self.s3_region:
                client_kwargs['region_name'] = self.s3_region
            
            async with self.s3_session.client('s3', **client_kwargs) as s3:
                await s3.download_file(bucket, key, str(local_path))
            
            file_size = local_path.stat().st_size
            logger.info(f"[{request_id}] Downloaded successfully: {file_size} bytes")
            return local_path
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"[{request_id}] S3 download failed: {error_code} - {e}")
            raise RuntimeError(f"Failed to download file from S3: {error_code}") from e
        except Exception as e:
            logger.error(f"[{request_id}] Unexpected error during S3 download: {e}")
            raise
    
    async def _upload_to_s3(
        self,
        local_path: Path,
        request_id: str
    ) -> str:
        """
        上传文件到 S3
        
        Args:
            local_path: 本地文件路径
            request_id: 请求 ID
        
        Returns:
            S3 URL (格式: s3://bucket/path/to/file.ext)
        """
        # 生成唯一的 S3 key
        file_ext = local_path.suffix
        unique_id = str(uuid.uuid4())
        s3_key = f"outputs/{request_id}/{unique_id}{file_ext}"
        
        logger.info(f"[{request_id}] Uploading to S3: {local_path} -> {self.s3_bucket}/{s3_key}")
        
        try:
            file_size = local_path.stat().st_size
            
            # 构建 client 参数
            client_kwargs = {}
            if self.s3_endpoint_url:
                client_kwargs['endpoint_url'] = self.s3_endpoint_url
            if self.s3_region:
                client_kwargs['region_name'] = self.s3_region
            
            async with self.s3_session.client('s3', **client_kwargs) as s3:
                await s3.upload_file(str(local_path), self.s3_bucket, s3_key)
            
            s3_url = f"s3://{self.s3_bucket}/{s3_key}"
            logger.info(f"[{request_id}] Uploaded successfully: {file_size} bytes -> {s3_url}")
            return s3_url
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            logger.error(f"[{request_id}] S3 upload failed: {error_code} - {e}")
            raise RuntimeError(f"Failed to upload file to S3: {error_code}") from e
        except Exception as e:
            logger.error(f"[{request_id}] Unexpected error during S3 upload: {e}")
            raise
    
    async def start_cleanup_daemon(
        self,
        interval_seconds: int = 300,
        max_age_seconds: int = 3600
    ) -> None:
        """
        启动清理守护进程
        
        Args:
            interval_seconds: 清理间隔（默认 5 分钟）
            max_age_seconds: 工作目录最大保留时间（默认 1 小时）
        """
        if not self.workspace_root:
            logger.info("Workspace not available, cleanup daemon disabled")
            return
        
        logger.info(f"Starting cleanup daemon (interval={interval_seconds}s, max_age={max_age_seconds}s)")
        
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                await self._run_cleanup(max_age_seconds)
            except Exception as e:
                logger.error(f"Cleanup daemon error: {e}", exc_info=True)
    
    async def _run_cleanup(self, max_age_seconds: int) -> None:
        """执行一次清理"""
        if not self.workspace_root or not self.workspace_root.exists():
            return
        
        now = time.time()
        cutoff_time = now - max_age_seconds
        
        cleaned_count = 0
        total_size = 0
        
        try:
            for job_dir in self.workspace_root.iterdir():
                if not job_dir.is_dir():
                    continue
                
                # 检查修改时间
                mtime = job_dir.stat().st_mtime
                if mtime < cutoff_time:
                    # 计算目录大小（用于日志）
                    try:
                        dir_size = sum(f.stat().st_size for f in job_dir.rglob('*') if f.is_file())
                        total_size += dir_size
                    except:
                        pass
                    
                    # 删除目录
                    shutil.rmtree(job_dir)
                    cleaned_count += 1
                    logger.info(f"Cleaned expired workspace: {job_dir.name}")
            
            if cleaned_count > 0:
                size_mb = total_size / (1024 * 1024)
                logger.info(f"Cleanup summary: removed {cleaned_count} workspaces, freed {size_mb:.2f} MB")
            
            # 检查磁盘使用率
            usage = shutil.disk_usage(self.workspace_root)
            usage_percent = (usage.used / usage.total) * 100
            
            if usage_percent > 80:
                logger.warning(f"Workspace disk usage high: {usage_percent:.1f}%")
                if usage_percent > 90:
                    logger.error(f"Workspace disk usage critical: {usage_percent:.1f}%, emergency cleanup recommended")
        
        except Exception as e:
            logger.error(f"Cleanup failed: {e}", exc_info=True)


# 创建全局单例（从配置文件读取设置）
file_handler_service = FileHandlerService(
    workspace_root=settings.workspace_root,
    s3_bucket=settings.s3_bucket,
    s3_endpoint_url=settings.s3_endpoint_url,
    s3_region=settings.s3_region
)

