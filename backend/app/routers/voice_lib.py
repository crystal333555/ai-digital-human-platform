from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.avatar import Voice
from app.config import settings
from app.services.voice_library import (
    get_preset_voices, get_preset_voice, get_voice_categories, PRESET_VOICES
)
from app.services.voice_blending import VoiceBlendingService
from app.services.tts_service import TTSService

router = APIRouter(prefix="/voice-lib")

class BlendRequest(BaseModel):
    voice_ids: List[str]
    weights: List[float]
    text: str = "你好，这是混合音色的测试效果。"
    method: str = "audio"  # "audio" | "embedding"

class BlendPreviewRequest(BaseModel):
    voice_ids: List[str]
    weights: List[float]

# ========== 音色库查询 ==========

@router.get("/categories")
async def list_categories():
    """获取音色分类列表（参考豆包分类）"""
    return {
        "categories": get_voice_categories()
    }

@router.get("/presets")
async def list_preset_voices(
    category: Optional[str] = Query(None, description="按分类筛选: 温柔系/沉稳系/活力系/方言特色/AI/特殊"),
    gender: Optional[str] = Query(None, description="按性别筛选: male/female/neutral"),
):
    """获取预置音色列表"""
    voices = get_preset_voices(category=category, gender=gender)
    return {
        "total": len(voices),
        "voices": voices
    }

@router.get("/presets/{voice_id}")
async def get_preset_detail(voice_id: str):
    """获取单个预置音色详情"""
    voice = get_preset_voice(voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="预置音色不存在")
    return voice

@router.post("/presets/{voice_id}/test")
async def test_preset_voice(
    voice_id: str,
    text: str = "你好，我是AI数字人平台的测试音色。你能听到我的声音吗？"
):
    """试听单个预置音色"""
    voice = get_preset_voice(voice_id)
    if not voice:
        raise HTTPException(status_code=404, detail="预置音色不存在")
    
    import uuid, os
    from app.config import settings
    
    output_file = f"preset_test_{uuid.uuid4().hex[:8]}.mp3"
    output_path = os.path.join(settings.GENERATED_DIR, output_file)
    
    try:
        import edge_tts
        communicate = edge_tts.Communicate(
            text,
            voice["edge_tts_voice"],
            rate=voice.get("rate", "+0%"),
            pitch=voice.get("pitch", "+0Hz")
        )
        await communicate.save(output_path)
        
        return {
            "success": True,
            "voice_id": voice_id,
            "voice_name": voice["name"],
            "audio_url": f"/data/generated/{output_file}",
            "text": text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"合成失败: {str(e)}")


# ========== 音色混合 ==========

@router.post("/blend")
async def blend_voices(request: BlendRequest):
    """
    混合2~3个音色生成新语音
    
    示例:
    {
        "voice_ids": ["gentle_peach", "intellectual_sister"],
        "weights": [0.6, 0.4],
        "text": "你好，我是一个融合了温柔与知性的新音色。"
    }
    """
    if len(request.voice_ids) < 2 or len(request.voice_ids) > 3:
        raise HTTPException(status_code=400, detail="仅支持2~3个音色混合")
    
    if len(request.voice_ids) != len(request.weights):
        raise HTTPException(status_code=400, detail="音色ID与权重数量不匹配")
    
    service = VoiceBlendingService()
    
    try:
        import uuid, os
        output_file = f"blended_{uuid.uuid4().hex[:8]}.mp3"
        output_path = os.path.join(settings.GENERATED_DIR, output_file)
        
        await service.blend_voices(
            text=request.text,
            voice_ids=request.voice_ids,
            weights=request.weights,
            output_path=output_path,
            method=request.method
        )
        
        return {
            "success": True,
            "audio_url": f"/data/generated/{output_file}",
            "text": request.text,
            "blend_info": {
                "voice_ids": request.voice_ids,
                "weights": request.weights,
                "normalized_weights": service._normalize_weights(request.weights),
                "method": request.method
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"混合失败: {str(e)}")

@router.post("/blend/preview")
async def preview_blend(request: BlendPreviewRequest):
    """快速预览混合音色效果"""
    if len(request.voice_ids) < 2 or len(request.voice_ids) > 3:
        raise HTTPException(status_code=400, detail="仅支持2~3个音色混合")
    
    service = VoiceBlendingService()
    
    try:
        audio_url = await service.preview_blend(
            voice_ids=request.voice_ids,
            weights=request.weights
        )
        return {
            "success": True,
            "audio_url": audio_url,
            "blend_info": {
                "voice_ids": request.voice_ids,
                "weights": request.weights
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"预览失败: {str(e)}")

@router.post("/blend/suggest")
async def suggest_blend_ratios(
    voice_ids: List[str] = Query(..., description="音色ID列表")
):
    """获取推荐的混合比例"""
    try:
        service = VoiceBlendingService()
        suggestions = service.suggest_blend_ratios(voice_ids)
        return {
            "voice_ids": voice_ids,
            "suggestions": suggestions
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== 导出/收藏音色 ==========

@router.post("/presets/{voice_id}/clone-to-mine")
async def clone_preset_to_mine(
    voice_id: str,
    custom_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """将预置音色复制到我的音色库"""
    preset = get_preset_voice(voice_id)
    if not preset:
        raise HTTPException(status_code=404, detail="预置音色不存在")
    
    # 创建新音色记录
    from app.models.avatar import User
    user = db.query(User).first()
    if not user:
        user = User(username="admin", email="admin@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
    
    voice = Voice(
        name=custom_name or f"我的{preset['name']}",
        description=preset["description"],
        source="edge-tts",
        tts_config={
            "voice_name": preset["edge_tts_voice"],
            "rate": preset.get("rate", "+0%"),
            "pitch": preset.get("pitch", "+0Hz"),
            "preset_id": voice_id,
            "category": preset["category"]
        },
        owner_id=user.id
    )
    
    db.add(voice)
    db.commit()
    db.refresh(voice)
    
    return {
        "success": True,
        "voice_id": voice.id,
        "preset_based_on": voice_id,
        "name": voice.name,
        "message": f"已将 {preset['name']} 复制到你的音色库"
    }


class SaveBlendRequest(BaseModel):
    name: str
    description: str = ""
    voice_ids: List[str]
    weights: List[float]
    method: str = "audio"


@router.post("/blend/save")
async def save_blend_voice(
    request: SaveBlendRequest,
    db: Session = Depends(get_db)
):
    """将混合音色保存到我的音色库，可在其他模块中使用"""
    if len(request.voice_ids) < 2:
        raise HTTPException(status_code=400, detail="至少需要2个音色")

    # 验证音色存在
    for vid in request.voice_ids:
        if not get_preset_voice(vid):
            raise HTTPException(status_code=400, detail=f"音色不存在: {vid}")

    # 归一化权重
    total = sum(request.weights)
    norm_weights = [w / total for w in request.weights] if total > 0 else [1.0 / len(request.weights)] * len(request.weights)

    # 获取音色名称用于描述
    voice_names = [get_preset_voice(vid)["name"] for vid in request.voice_ids]
    blend_desc = " + ".join([f"{name}({int(w*100)}%)" for name, w in zip(voice_names, norm_weights)])

    from app.models.avatar import User
    user = db.query(User).first()
    if not user:
        user = User(username="admin", email="admin@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)

    voice = Voice(
        name=request.name,
        description=request.description or f"混合音色: {blend_desc}",
        source="blended",
        tts_config={
            "type": "blend",
            "voice_ids": request.voice_ids,
            "weights": norm_weights,
            "method": request.method,
            "voice_names": voice_names,
        },
        owner_id=user.id
    )

    db.add(voice)
    db.commit()
    db.refresh(voice)

    return {
        "success": True,
        "voice_id": voice.id,
        "name": voice.name,
        "message": f"混合音色「{request.name}」已保存到我的音色库"
    }
