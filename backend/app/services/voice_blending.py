import os
import json
import shutil
import tempfile
from typing import List, Dict, Optional
import subprocess
import edge_tts
from app.config import settings
from app.services.voice_library import PRESET_VOICES, get_preset_voice


class VoiceBlendingService:
    """音色混合服务 - 支持2~3个音色混合"""
    
    def __init__(self):
        self.method = "audio"  # "audio" | "embedding" (GPT-SoVITS)
        self.temp_dir = tempfile.gettempdir()
    
    async def blend_voices(
        self,
        text: str,
        voice_ids: List[str],
        weights: List[float],
        output_path: str,
        method: str = "audio"
    ) -> str:
        """
        混合多个音色生成新语音
        
        Args:
            text: 要合成的文本
            voice_ids: 音色ID列表（2~3个）
            weights: 每个音色的权重列表，总和应为1.0
            output_path: 输出文件路径
            method: "audio" 音频混合 | "embedding" 向量插值（需GPT-SoVITS）
        """
        if len(voice_ids) < 2 or len(voice_ids) > 3:
            raise ValueError("仅支持2~3个音色混合")
        
        if len(voice_ids) != len(weights):
            raise ValueError("音色ID与权重数量必须一致")
        
        # 归一化权重
        total = sum(weights)
        weights = [w / total for w in weights]
        
        if method == "embedding":
            return await self._blend_with_embedding(text, voice_ids, weights, output_path)
        else:
            return await self._blend_with_audio(text, voice_ids, weights, output_path)
    
    async def _blend_with_audio(
        self,
        text: str,
        voice_ids: List[str],
        weights: List[float],
        output_path: str
    ) -> str:
        """
        音频混合方案：分别合成每个音色的音频，然后加权叠加
        
        原理：对多条音频的波形/频谱进行加权平均
        优点：不依赖GPU模型，Edge-TTS即可实现
        缺点：效果不如向量插值自然，可能带混响感
        """
        
        # 1. 分别合成每个音色的音频
        audio_files = []
        for i, vid in enumerate(voice_ids):
            voice_config = get_preset_voice(vid)
            if not voice_config:
                raise ValueError(f"音色不存在: {vid}")
            
            temp_file = os.path.join(self.temp_dir, f"blend_{i}_{os.path.basename(output_path)}")
            
            try:
                communicate = edge_tts.Communicate(
                    text,
                    voice_config["edge_tts_voice"],
                    rate=voice_config.get("rate", "+0%"),
                    pitch=voice_config.get("pitch", "+0Hz")
                )
                await communicate.save(temp_file)
                audio_files.append((temp_file, weights[i]))
            except Exception as e:
                # 如果某个音色合成失败，跳过或报错
                raise RuntimeError(f"音色 {voice_config['name']} 合成失败: {str(e)}")
        
        # 2. 使用FFmpeg进行加权混合
        if len(audio_files) == 1:
            # 只有一个音频，直接复制
            shutil.copy2(audio_files[0][0], output_path)
        else:
            await self._ffmpeg_mix(audio_files, output_path)
        
        # 3. 清理临时文件
        for f, _ in audio_files:
            if os.path.exists(f):
                os.remove(f)
        
        return output_path
    
    async def _ffmpeg_mix(
        self,
        audio_files: List[tuple],
        output_path: str
    ):
        """使用FFmpeg或moviepy混合多个音频文件"""
        try:
            await self._ffmpeg_mix_ffmpeg(audio_files, output_path)
        except (FileNotFoundError, RuntimeError):
            # FFmpeg不可用，降级到moviepy
            await self._ffmpeg_mix_moviepy(audio_files, output_path)
    
    async def _ffmpeg_mix_ffmpeg(
        self,
        audio_files: List[tuple],
        output_path: str
    ):
        """使用FFmpeg混合音频"""
        import subprocess
        
        inputs = []
        filters = []
        
        for i, (file_path, weight) in enumerate(audio_files):
            inputs.extend(["-i", file_path])
            filters.append(f"[{i}]volume={weight}[a{i}]")
        
        n = len(audio_files)
        mix_inputs = "".join([f"[a{i}]" for i in range(n)])
        filters.append(f"{mix_inputs}amix=inputs={n}:duration=first:dropout_transition=0[mix]")
        
        cmd = [
            "ffmpeg", "-y",
            *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[mix]",
            "-c:a", "libmp3lame",
            "-q:a", "2",
            output_path
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg混合失败: {result.stderr}")
    
    async def _ffmpeg_mix_moviepy(
        self,
        audio_files: List[tuple],
        output_path: str
    ):
        """使用moviepy混合音频（纯Python，无需FFmpeg）"""
        try:
            from moviepy import AudioFileClip, CompositeAudioClip
        except ImportError:
            try:
                from moviepy.editor import AudioFileClip, CompositeAudioClip
            except ImportError:
                raise RuntimeError("moviepy未安装，无法混合音频")
        
        import math, random
        
        # 加载所有音频并按权重调整音量
        clips = []
        for i, (file_path, weight) in enumerate(audio_files):
            clip = AudioFileClip(file_path)
            
            # 1. 根据权重调整音量
            if weight > 0:
                volume_db = 20 * math.log10(weight)
            else:
                volume_db = -60
            clip = clip.with_volume_scaled(10 ** (volume_db / 20))
            
            # 2. 添加微小随机延迟（20-80ms），避免完全同步的"机器人感"
            delay = random.uniform(0.02, 0.08)  # 20-80ms
            clip = clip.with_start(delay)
            
            # 3. 轻微音高偏移（±1.5%），让声音更自然不同
            speed_factor = 1.0 + random.uniform(-0.015, 0.015)
            if abs(speed_factor - 1.0) > 0.001:
                clip = clip.with_speed_scaled(speed_factor)
            
            clips.append(clip)
        
        # 混合所有音频
        if len(clips) == 1:
            mixed = clips[0]
        else:
            mixed = CompositeAudioClip(clips)
        
        # 导出
        mixed.write_audiofile(output_path, fps=44100, nbytes=2, codec='libmp3lame')
        
        # 清理
        for c in clips:
            c.close()
        mixed.close()
    
    
    async def _blend_with_embedding(
        self,
        text: str,
        voice_ids: List[str],
        weights: List[float],
        output_path: str
    ) -> str:
        """
        GPT-SoVITS 向量插值方案（推荐）
        
        原理：提取每个音色的 spk_emb（speaker embedding），在向量空间做加权插值
        hybrid_speaker = w1 * emb_A + w2 * emb_B + w3 * emb_C
        
        优点：效果最自然，生成全新音色
        缺点：需要部署GPT-SoVITS服务，且音色需已训练模型
        """
        
        # 检查GPT-SoVITS是否可用
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.GPT_SOVITS_API_URL}/",
                    timeout=5.0
                )
                if response.status_code != 200:
                    raise RuntimeError("GPT-SoVITS服务未响应")
        except Exception:
            # 降级到音频混合
            return await self._blend_with_audio(text, voice_ids, weights, output_path)
        
        # TODO: 实现GPT-SoVITS spk_emb插值
        # 这需要调用GPT-SoVITS的API，传入多个参考音频和权重
        # 当前版本暂用音频混合降级
        return await self._blend_with_audio(text, voice_ids, weights, output_path)
    
    async def preview_blend(
        self,
        voice_ids: List[str],
        weights: List[float],
        preview_text: str = "你好，这是混合音色的试听效果。"
    ) -> str:
        """快速预览混合音色效果"""
        import uuid
        output_file = f"blend_preview_{uuid.uuid4().hex[:8]}.mp3"
        output_path = os.path.join(settings.GENERATED_DIR, output_file)
        
        await self.blend_voices(preview_text, voice_ids, weights, output_path)
        return f"/data/generated/{output_file}"
    
    def suggest_blend_ratios(
        self,
        voice_ids: List[str]
    ) -> List[Dict]:
        """
        根据音色特征推荐混合比例
        
        例如：
        - 温柔桃子(0.6) + 知性姐姐(0.4) = 温柔知性女声
        - 活力少年(0.5) + 沉稳教授(0.5) = 阳光成熟男声
        """
        voices = [get_preset_voice(vid) for vid in voice_ids]
        if None in voices:
            raise ValueError("部分音色不存在")
        
        # 获取音色特征
        genders = [v["gender"] for v in voices]
        categories = [v["category"] for v in voices]
        
        suggestions = []
        
        # 同性别推荐
        if len(set(genders)) == 1:
            if len(voice_ids) == 2:
                suggestions.append({
                    "name": f"{voices[0]['name']}x{voices[1]['name']}",
                    "weights": [0.5, 0.5],
                    "description": f"均衡混合，兼具{voices[0]['name']}和{voices[1]['name']}的特色"
                })
                suggestions.append({
                    "name": f"偏{voices[0]['name']}",
                    "weights": [0.7, 0.3],
                    "description": f"偏向{voices[0]['name']}风格，带一点{voices[1]['name']}的韵味"
                })
                suggestions.append({
                    "name": f"偏{voices[1]['name']}",
                    "weights": [0.3, 0.7],
                    "description": f"偏向{voices[1]['name']}风格，带一点{voices[0]['name']}的韵味"
                })
            elif len(voice_ids) == 3:
                suggestions.append({
                    "name": "均衡三音色",
                    "weights": [0.34, 0.33, 0.33],
                    "description": "三音色均衡混合，创造独特新声线"
                })
        
        # 跨性别推荐
        if len(set(genders)) > 1:
            suggestions.append({
                "name": "中性音色",
                "weights": [0.5, 0.5] if len(voice_ids) == 2 else [0.34, 0.33, 0.33],
                "description": "跨性别混合，产生中性、富有磁性的新声线"
            })
        
        return suggestions

    @staticmethod
    def _normalize_weights(weights: List[float]) -> List[float]:
        """将权重归一化为概率分布"""
        total = sum(weights)
        if total == 0:
            return [1.0 / len(weights) for _ in weights]
        return [w / total for w in weights]
