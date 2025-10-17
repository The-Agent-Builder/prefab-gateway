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

logger = logging.getLogger(__name__)


class FileHandlerService:
    """文件处理服务"""
    
    def __init__(self, workspace_root: str = "/mnt/prefab-workspace"):
        """
        初始化文件处理服务
        
        Args:
            workspace_root: PVC 挂载路径
        """
        self.workspace_root = Path(workspace_root)
        self._cleanup_task = None
        
        # 确保根目录存在
        if not self.workspace_root.exists():
            logger.warning(f"Workspace root does not exist: {self.workspace_root}")
            logger.warning("File handling will be disabled (PVC not mounted)")
            self.workspace_root = None
        else:
            logger.info(f"File handler initialized with workspace: {self.workspace_root}")
    
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
                
                # TODO: 实现 S3 下载逻辑
                # local_path = await self._download_from_s3(s3_url, workspace, param_name)
                # processed_inputs[param_name] = str(local_path)
                
                # 临时：直接传递 S3 URL（待实现）
                logger.warning(f"[{request_id}] S3 download not implemented yet, passing URL as-is")
                processed_inputs[param_name] = s3_url
        
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
                
                # TODO: 实现 S3 上传逻辑
                # s3_url = await self._upload_to_s3(local_path, request_id)
                # processed_output[field_name] = s3_url
                
                # 临时：返回本地路径（待实现）
                logger.warning(f"[{request_id}] S3 upload not implemented yet, returning local path")
                processed_output[field_name] = str(local_path)
        
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
    
    # TODO: 实现 S3 交互方法
    # async def _download_from_s3(
    #     self,
    #     s3_url: str,
    #     workspace: Path,
    #     filename: str
    #     request_id: str
    # ) -> Path:
    #     """从 S3 下载文件到 workspace"""
    #     # 解析 S3 URL: s3://bucket/path/to/file.ext
    #     # 使用 boto3 下载
    #     # 返回本地路径
    #     pass
    
    # async def _upload_to_s3(
    #     self,
    #     local_path: Path,
    #     request_id: str
    # ) -> str:
    #     """上传文件到 S3"""
    #     # 生成唯一的 S3 key
    #     # 使用 boto3 上传
    #     # 返回 S3 URL
    #     pass
    
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


# 创建全局单例
file_handler_service = FileHandlerService()

