import os
import shutil
from pathlib import Path
from typing import Optional
from app.config import settings

class FileStorage:
    """文件存储工具类"""
    
    @staticmethod
    def save_upload(file_obj, dest_path: str) -> str:
        """保存上传文件"""
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file_obj, f)
        return dest_path
    
    @staticmethod
    def delete_file(file_path: str) -> bool:
        """删除文件"""
        if os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    
    @staticmethod
    def get_file_url(file_path: str) -> Optional[str]:
        """获取文件访问URL"""
        if not file_path or not os.path.exists(file_path):
            return None
        
        # 转换为相对路径
        abs_path = os.path.abspath(file_path)
        base_dir = os.path.abspath(os.getcwd())
        
        if abs_path.startswith(base_dir):
            rel_path = os.path.relpath(abs_path, base_dir)
            return f"/uploads/{rel_path.replace('uploads/', '')}"
        
        return None
    
    @staticmethod
    def ensure_dirs():
        """确保所有上传目录存在"""
        dirs = [
            settings.AVATAR_DIR,
            settings.VOICE_DIR,
            settings.GENERATED_DIR
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)
