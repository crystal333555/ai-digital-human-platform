import os
import uuid
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import edge_tts
import asyncio

from app.config import settings

router = APIRouter(prefix="/tts")

class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = "zh-CN-XiaoxiaoNeural"
    rate: Optional[str] = "+0%"
    pitch: Optional[str] = "+0Hz"

class TTSTestRequest(BaseModel):
    text: str = "你好，这是AI数字人平台的语音测试。"
    voice_id: Optional[int] = None

@router.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """Edge-TTS语音合成"""
    
    output_file = f"{uuid.uuid4().hex}.mp3"
    output_path = os.path.join(settings.GENERATED_DIR, output_file)
    
    try:
        communicate = edge_tts.Communicate(
            request.text,
            request.voice,
            rate=request.rate,
            pitch=request.pitch
        )
        await communicate.save(output_path)
        
        return {
            "success": True,
            "audio_url": f"/uploads/generated/{output_file}",
            "voice": request.voice,
            "text_length": len(request.text)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"语音合成失败: {str(e)}")

@router.get("/voices")
async def list_voices(
    language: Optional[str] = Query("zh-CN", description="语言代码")
):
    """获取Edge-TTS可用声音列表"""
    
    # Edge-TTS中文常用声音
    zh_voices = [
        {"name": "zh-CN-XiaoxiaoNeural", "gender": "Female", "description": "晓晓 - 年轻女声，自然友好"},
        {"name": "zh-CN-YunyangNeural", "gender": "Male", "description": "云扬 - 男声，沉稳专业"},
        {"name": "zh-CN-YunxiNeural", "gender": "Male", "description": "云希 - 年轻男声，活泼阳光"},
        {"name": "zh-CN-XiaoyiNeural", "gender": "Female", "description": "晓伊 - 女童声，天真可爱"},
        {"name": "zh-CN-YunxiaNeural", "gender": "Male", "description": "云夏 - 男童声，活泼俏皮"},
        {"name": "zh-CN-XiaohanNeural", "gender": "Female", "description": "晓涵 - 温柔女声，知性优雅"},
        {"name": "zh-CN-XiaomengNeural", "gender": "Female", "description": "晓梦 - 甜美女声，亲切自然"},
        {"name": "zh-TW-HsiaoChenNeural", "gender": "Female", "description": "小臻 - 台湾女声"},
        {"name": "zh-TW-YunJheNeural", "gender": "Male", "description": "云哲 - 台湾男声"},
        {"name": "zh-HK-HiuMaanNeural", "gender": "Female", "description": "晓曼 - 粤语女声"},
        {"name": "zh-HK-WanLungNeural", "gender": "Male", "description": "云龙 - 粤语男声"},
    ]
    
    en_voices = [
        {"name": "en-US-AriaNeural", "gender": "Female", "description": "Aria - 美式英语女声"},
        {"name": "en-US-GuyNeural", "gender": "Male", "description": "Guy - 美式英语男声"},
        {"name": "en-GB-SoniaNeural", "gender": "Female", "description": "Sonia - 英式英语女声"},
        {"name": "en-GB-RyanNeural", "gender": "Male", "description": "Ryan - 英式英语男声"},
    ]
    
    if language.startswith("zh"):
        return {"voices": zh_voices}
    elif language.startswith("en"):
        return {"voices": en_voices}
    else:
        return {"voices": zh_voices + en_voices}

@router.post("/test")
async def test_tts(request: TTSTestRequest):
    """测试语音合成，用于快速验证音色"""
    
    output_file = f"tts_test_{uuid.uuid4().hex[:8]}.mp3"
    output_path = os.path.join(settings.GENERATED_DIR, output_file)
    
    try:
        communicate = edge_tts.Communicate(
            request.text,
            "zh-CN-XiaoxiaoNeural"
        )
        await communicate.save(output_path)
        
        return {
            "success": True,
            "audio_url": f"/uploads/generated/{output_file}",
            "text": request.text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"测试失败: {str(e)}")
