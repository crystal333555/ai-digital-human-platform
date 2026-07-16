import os
from pydantic_settings import BaseSettings
from functools import lru_cache

# 项目根目录（backend/app/config.py -> backend/ -> 项目根）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# D盘数据目录（大文件存储：视频、PPT、模型等）
_DATA_ROOT = os.environ.get("AI_AVATAR_DATA_ROOT", r"D:\AI_Avatar_Data")

class Settings(BaseSettings):
    """应用配置"""
    # 基础配置
    APP_NAME: str = "AI Avatar Platform"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"
    
    # 数据库
    DATABASE_URL: str = "sqlite:///./app.db"
    
    # 文件存储 - 小文件留在项目目录（头像、音色样本等）
    UPLOAD_DIR: str = os.path.join(_PROJECT_ROOT, "uploads")
    AVATAR_DIR: str = os.path.join(_PROJECT_ROOT, "uploads", "avatars")
    VOICE_DIR: str = os.path.join(_PROJECT_ROOT, "uploads", "voices")
    
    # 大文件存储 - D盘（生成视频、PPT文件等）
    GENERATED_DIR: str = os.path.join(_DATA_ROOT, "generated")
    PPT_DIR: str = os.path.join(_DATA_ROOT, "ppt")
    MODELS_DIR: str = os.path.join(_DATA_ROOT, "models")
    
    # LLM配置 (支持多厂商)
    LLM_PROVIDER: str = "openai"  # openai, azure, qwen, etc.
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4"
    
    # Qwen配置
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/api/v1"
    QWEN_MODEL: str = "qwen-max"
    
    # TTS配置
    TTS_PROVIDER: str = "edge-tts"  # edge-tts, gpt-sovits
    GPT_SOVITS_API_URL: str = "http://localhost:9880"
    
    # 口型同步配置
    LIP_SYNC_MODEL: str = "musetalk"  # musetalk, wav2lip, sadtalker
    WAV2LIP_MODEL_PATH: str = "models/wav2lip.pth"
    MUSETALK_API_URL: str = "http://localhost:7861"
    
    # 3D渲染配置
    ENABLE_3D: bool = True
    THREE_JS_CDN: str = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
