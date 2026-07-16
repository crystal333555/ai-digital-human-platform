import os
import json
import shutil
import subprocess
import tempfile
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from app.config import settings

# 参考豆包音色分类，构建预置音色库
# 映射到 Edge-TTS 的预置声音
PRESET_VOICES = {
    # === 温柔系 ===
    "gentle_peach": {
        "name": "温柔桃子",
        "edge_tts_voice": "zh-CN-XiaoxiaoNeural",
        "category": "温柔系",
        "description": "温柔亲切，亲和力强，语速适中，如沐春风",
        "gender": "female",
        "age_group": "young",
        "mood_tags": ["温柔", "治愈", "亲切"],
        "rate": "+0%",
        "pitch": "+0Hz"
    },
    "neighboring_girl": {
        "name": "邻家女孩",
        "edge_tts_voice": "zh-CN-XiaoyiNeural",
        "category": "温柔系",
        "description": "活泼可爱，天真俏皮，适合短视频/儿童内容",
        "gender": "female",
        "age_group": "young",
        "mood_tags": ["活泼", "可爱", "轻甜"],
        "rate": "+5%",
        "pitch": "+2Hz"
    },
    "northeast_girl": {
        "name": "东北小甜",
        "edge_tts_voice": "zh-CN-liaoning-XiaobeiNeural",
        "category": "温柔系",
        "description": "东北幽默女声，亲切接地气，自带笑点",
        "gender": "female",
        "age_group": "young",
        "mood_tags": ["幽默", "亲切", "接地气"],
        "rate": "+0%",
        "pitch": "+0Hz"
    },
    
    # === 沉稳系 ===
    "calm_professor": {
        "name": "沉稳教授",
        "edge_tts_voice": "zh-CN-YunyangNeural",
        "category": "沉稳系",
        "description": "沉稳专业，语调稳定，适合知识讲解/新闻播报",
        "gender": "male",
        "age_group": "adult",
        "mood_tags": ["沉稳", "专业", "可靠"],
        "rate": "-5%",
        "pitch": "-2Hz"
    },
    "techy_male": {
        "name": "科技感男声",
        "edge_tts_voice": "zh-CN-YunyangNeural",
        "category": "沉稳系",
        "description": "干净利索，专业可靠，适合导航/播报/AI助手",
        "gender": "male",
        "age_group": "adult",
        "mood_tags": ["科技", "冷静", "利落"],
        "rate": "+0%",
        "pitch": "+0Hz"
    },
    "cool_uncle": {
        "name": "冷静大叔",
        "edge_tts_voice": "zh-CN-YunxiNeural",
        "category": "沉稳系",
        "description": "阳光沉稳，低沉稳重，适合叙事/电台/有声书",
        "gender": "male",
        "age_group": "adult",
        "mood_tags": ["冷静", "沉稳", "成熟"],
        "rate": "-8%",
        "pitch": "-4Hz"
    },
    
    # === 活力系 ===
    "energetic_youth": {
        "name": "活力少年",
        "edge_tts_voice": "zh-CN-YunjianNeural",
        "category": "活力系",
        "description": "充满激情，节奏明快，适合体育赛事/游戏解说",
        "gender": "male",
        "age_group": "young",
        "mood_tags": ["活力", "激情", "热情"],
        "rate": "+10%",
        "pitch": "+3Hz"
    },
    "cute_boy": {
        "name": "元气正太",
        "edge_tts_voice": "zh-CN-YunxiaNeural",
        "category": "活力系",
        "description": "天真俏皮，元气满满，适合儿童内容/动画配音",
        "gender": "male",
        "age_group": "child",
        "mood_tags": ["元气", "俏皮", "天真"],
        "rate": "+15%",
        "pitch": "+8Hz"
    },
    "sweet_girl": {
        "name": "甜妹",
        "edge_tts_voice": "zh-CN-XiaoyiNeural",
        "category": "活力系",
        "description": "甜美可爱，语气俏皮，适合直播/陪玩/短视频",
        "gender": "female",
        "age_group": "young",
        "mood_tags": ["甜美", "可爱", "俏皮"],
        "rate": "+8%",
        "pitch": "+4Hz"
    },
    
    # === 方言特色 ===
    "cantonese_girl": {
        "name": "粤语港风女声",
        "edge_tts_voice": "zh-HK-HiuMaanNeural",
        "category": "方言特色",
        "description": "港风粤语女声，温柔有韵味",
        "gender": "female",
        "age_group": "adult",
        "mood_tags": ["港风", "粤语", "复古"],
        "rate": "+0%",
        "pitch": "+0Hz"
    },
    "cantonese_boy": {
        "name": "粤语暖男",
        "edge_tts_voice": "zh-HK-WanLungNeural",
        "category": "方言特色",
        "description": "粤语男声，温暖稳重",
        "gender": "male",
        "age_group": "adult",
        "mood_tags": ["粤语", "温暖", "稳重"],
        "rate": "+0%",
        "pitch": "+0Hz"
    },
    "tw_girl": {
        "name": "台湾小姊",
        "edge_tts_voice": "zh-TW-HsiaoChenNeural",
        "category": "方言特色",
        "description": "台湾腔女声，温柔细腻",
        "gender": "female",
        "age_group": "young",
        "mood_tags": ["台湾腔", "温柔", "细腻"],
        "rate": "+0%",
        "pitch": "+2Hz"
    },
    "shaanxi_girl": {
        "name": "陕西女娃",
        "edge_tts_voice": "zh-CN-shaanxi-XiaoniNeural",
        "category": "方言特色",
        "description": "陕西方言女声，明亮活泼，秦韵十足",
        "gender": "female",
        "age_group": "young",
        "mood_tags": ["陕西", "明亮", "秦韵"],
        "rate": "+0%",
        "pitch": "+0Hz"
    },
    
    # === AI/特殊 ===
    "ai_robot": {
        "name": "AI电子音",
        "edge_tts_voice": "en-US-AriaNeural",
        "category": "AI/特殊",
        "description": "电子合成感，赛博朋克风格",
        "gender": "neutral",
        "age_group": "adult",
        "mood_tags": ["AI", "电子", "赛博朋克"],
        "rate": "+0%",
        "pitch": "+0Hz"
    }
}


def get_preset_voices(
    category: Optional[str] = None,
    gender: Optional[str] = None
) -> List[Dict]:
    """获取预置音色列表，支持按分类/性别筛选"""
    result = []
    for key, voice in PRESET_VOICES.items():
        if category and voice["category"] != category:
            continue
        if gender and voice["gender"] != gender:
            continue
        item = dict(voice)
        item["id"] = key
        result.append(item)
    return result


def get_preset_voice(voice_id: str) -> Optional[Dict]:
    """获取单个预置音色详情"""
    if voice_id in PRESET_VOICES:
        item = dict(PRESET_VOICES[voice_id])
        item["id"] = voice_id
        return item
    return None


def get_voice_categories() -> List[Dict]:
    """获取音色分类列表"""
    categories = {}
    for voice in PRESET_VOICES.values():
        cat = voice["category"]
        if cat not in categories:
            categories[cat] = {
                "name": cat,
                "description": _get_category_desc(cat),
                "count": 0
            }
        categories[cat]["count"] += 1
    return list(categories.values())


def _get_category_desc(category: str) -> str:
    """获取分类描述"""
    desc_map = {
        "温柔系": "温柔亲切、知性优雅的声音，适合陪伴、教育、阅读场景",
        "沉稳系": "沉稳专业、冷静成熟的声音，适合知识讲解、播报、叙事",
        "活力系": "阳光活泼、甜美俏皮的声音，适合游戏、娱乐、直播场景",
        "方言特色": "粤语、台湾腔等方言特色声音，适合本地化内容",
        "AI/特殊": "电子合成等特殊风格声音，适合创意、科技内容"
    }
    return desc_map.get(category, "")
