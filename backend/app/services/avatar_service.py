import os
import shutil
from typing import Optional
from pathlib import Path
from app.config import settings
from app.utils.file_storage import FileStorage

class AvatarService:
    """数字人形象服务 - 处理照片风格化、3D模型配置等"""
    
    def __init__(self):
        self.file_storage = FileStorage()
    
    async def styleize_image(
        self,
        image_path: str,
        style: str = "realistic",
        output_path: Optional[str] = None
    ) -> str:
        """
        对上传照片进行风格化处理
        
        目前使用降级方案：直接复制原图（风格化需要GPU + Stable Diffusion）
        后续可接入：Stable Diffusion API / ComfyUI / Fooocus
        """
        if not output_path:
            import uuid
            output_path = os.path.join(
                settings.AVATAR_DIR,
                f"styled_{uuid.uuid4().hex}.png"
            )
        
        # 降级方案：复制原图作为风格化结果
        # 实际部署时应调用 SD API 或本地 ComfyUI
        shutil.copy2(image_path, output_path)
        
        return output_path
    
    async def generate_3d_config(
        self,
        image_path: str,
        style: str = "realistic"
    ) -> dict:
        """
        生成3D模型配置参数
        
        返回Three.js可用的配置对象，用于驱动3D渲染
        """
        config = {
            "type": "3d",
            "base_image": image_path,
            "style": style,
            "model_url": None,  # 如果有3D模型文件路径则填入
            "blendshapes": {
                "eyes_open": 1.0,
                "mouth_open": 0.0,
                "smile": 0.0,
                "brow_raise": 0.0,
                "surprise": 0.0
            },
            "animation_rig": "standard_human",
            "skin_tone": "medium",
            "hair_color": "black",
            "eye_color": "brown"
        }
        
        # 根据风格调整配置
        if style == "anime":
            config["animation_rig"] = "anime_face"
            config["eye_size"] = 1.3
        elif style == "cartoon":
            config["animation_rig"] = "cartoon_face"
            config["eye_size"] = 1.5
        
        return config
    
    async def update_expression(
        self,
        avatar_id: int,
        emotion: str,
        mouth_open: float = 0.0
    ) -> dict:
        """
        根据情感状态更新表情参数
        
        返回表情驱动数据，用于前端3D/2D渲染
        """
        emotion_map = {
            "happy": {"smile": 1.0, "brow_raise": 0.2, "mouth_open": 0.3},
            "sad": {"smile": 0.0, "brow_raise": -0.3, "mouth_open": 0.1},
            "angry": {"smile": 0.0, "brow_raise": -0.5, "mouth_open": 0.2},
            "surprised": {"smile": 0.0, "brow_raise": 0.8, "mouth_open": 0.6},
            "neutral": {"smile": 0.0, "brow_raise": 0.0, "mouth_open": mouth_open},
        }
        
        blend = emotion_map.get(emotion, emotion_map["neutral"])
        blend["mouth_open"] = max(blend["mouth_open"], mouth_open)
        
        return {
            "avatar_id": avatar_id,
            "emotion": emotion,
            "blendshapes": blend,
            "timestamp": None  # 可由调用方填充
        }
    
    async def process_avatar_pipeline(
        self,
        image_path: str,
        style: str = "realistic",
        display_mode: str = "both"
    ) -> dict:
        """
        完整的形象处理流水线
        
        1. 风格化照片
        2. 生成3D配置
        3. 返回处理结果
        """
        import uuid
        
        styled_path = os.path.join(
            settings.AVATAR_DIR,
            f"styled_{uuid.uuid4().hex}.png"
        )
        
        # 步骤1: 风格化
        styled_image = await self.styleize_image(image_path, style, styled_path)
        
        # 步骤2: 生成3D配置
        model_3d_config = await self.generate_3d_config(styled_image, style)
        
        return {
            "original_image": image_path,
            "styled_image": styled_image,
            "model_3d_config": model_3d_config,
            "display_mode": display_mode
        }

avatar_service = AvatarService()
