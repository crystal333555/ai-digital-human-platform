import os
import tempfile
from typing import List, Dict, Optional
from app.services.voice_library import PRESET_VOICES
import edge_tts
import asyncio
from app.config import settings

def list_voice_names() -> List[str]:
    """返回所有可用音色名称列表"""
    return [v["name"] for v in PRESET_VOICES.values()]

def get_voice_by_name(name: str) -> Optional[Dict]:
    """根据名称查找音色"""
    for vid, v in PRESET_VOICES.items():
        if v["name"] == name:
            return {**v, "id": vid}
    return None

async def test_tts(text: str = "你好，这是测试音色。"):
    """测试TTS是否可用"""
    tmp = os.path.join(tempfile.gettempdir(), "test_tts.mp3")
    try:
        communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
        await communicate.save(tmp)
        return True, tmp
    except Exception as e:
        return False, str(e)
