import os
import edge_tts
import httpx
from typing import Optional

from app.config import settings

class TTSService:
    """TTS语音合成服务"""
    
    def __init__(self):
        self.provider = settings.TTS_PROVIDER
        self.gpt_sovits_url = settings.GPT_SOVITS_API_URL
    
    async def synthesize_with_edge(
        self,
        text: str,
        output_path: str,
        voice_name: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz"
    ):
        """使用Edge-TTS合成语音"""
        
        try:
            communicate = edge_tts.Communicate(
                text,
                voice_name,
                rate=rate,
                pitch=pitch
            )
            await communicate.save(output_path)
            return output_path
        except Exception as e:
            raise RuntimeError(f"Edge-TTS合成失败: {str(e)}")
    
    async def synthesize_with_cloned(
        self,
        text: str,
        voice_id: str,
        output_path: str,
        ref_audio_path: str = None,
        prompt_text: str = None,
        **kwargs
    ):
        """使用GPT-SoVITS克隆音色合成"""
        
        try:
            # 如果没有提供参考音频路径，尝试从voice_id查找
            if not ref_audio_path:
                ref_audio_path = self._get_ref_audio_path(voice_id)
            
            if not ref_audio_path or not os.path.exists(ref_audio_path):
                print(f"[TTS] 未找到参考音频 {voice_id}，降级到Edge-TTS")
                return await self.synthesize_with_edge(text, output_path)
            
            # GPT-SoVITS 需要 wav 格式，如果不是 wav 则转换
            ref_audio_path = self._ensure_wav(ref_audio_path)
            
            # GPT-SoVITS 要求参考音频 3~10 秒，自动裁剪
            ref_audio_path = self._trim_ref_audio(ref_audio_path)
            
            if not prompt_text:
                prompt_text = ""
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.gpt_sovits_url}/tts",
                    params={
                        "text": text,
                        "text_lang": "zh",
                        "ref_audio_path": ref_audio_path,
                        "prompt_lang": "zh",
                        "prompt_text": prompt_text,
                        "top_k": 20,
                        "top_p": 0.6,
                        "temperature": 0.6,
                        "speed": kwargs.get("speed", 1.0),
                    },
                    timeout=120.0
                )
                
                content_type = response.headers.get("content-type", "")
                # GPT-SoVITS 有时返回 content-type: application/json 但实际是音频数据
                # 用内容大小判断：>1KB 大概率是音频，<1KB 大概率是错误JSON
                is_audio = (content_type.startswith("audio") or 
                           (response.status_code == 200 and len(response.content) > 1000))
                
                if is_audio:
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                    print(f"[TTS] GPT-SoVITS合成成功: {len(response.content)} bytes -> {output_path}")
                    return output_path
                else:
                    # GPT-SoVITS返回错误，解析错误信息
                    error_msg = ""
                    try:
                        err_data = response.json()
                        if isinstance(err_data, list) and len(err_data) > 0:
                            error_msg = err_data[0].get("error", str(err_data))
                        elif isinstance(err_data, dict):
                            error_msg = err_data.get("error", err_data.get("message", str(err_data)))
                        else:
                            error_msg = str(err_data)
                    except Exception:
                        error_msg = response.text[:200] if response.text else f"HTTP {response.status_code}, {len(response.content)} bytes"
                    
                    print(f"[TTS] GPT-SoVITS失败: {error_msg}")
                    
                    # 设备不匹配错误需要重启GPT-SoVITS，不能静默降级
                    if "device" in error_msg.lower() or "cuda" in error_msg.lower() or "cpu" in error_msg.lower():
                        raise RuntimeError(f"GPT-SoVITS设备错误(需重启): {error_msg}")
                    
                    # 其他错误降级到Edge-TTS
                    print(f"[TTS] 降级到Edge-TTS")
                    return await self.synthesize_with_edge(text, output_path)
                    
        except Exception as e:
            print(f"[TTS] GPT-SoVITS异常: {e}，降级到Edge-TTS")
            return await self.synthesize_with_edge(text, output_path)
    
    def _ensure_wav(self, audio_path: str) -> str:
        """确保音频是wav格式，如果不是则转换"""
        if audio_path.lower().endswith(".wav"):
            return audio_path
        
        wav_path = os.path.splitext(audio_path)[0] + ".wav"
        if os.path.exists(wav_path):
            return wav_path
        
        # 优先用 moviepy 转换
        try:
            from moviepy import AudioFileClip
            clip = AudioFileClip(audio_path)
            clip.write_audiofile(wav_path, logger=None)
            clip.close()
            print(f"[TTS] moviepy 音频转换: {audio_path} -> {wav_path}")
            return wav_path
        except Exception as e:
            print(f"[TTS] moviepy 转换失败: {e}")
        
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(audio_path)
            audio.export(wav_path, format="wav")
            print(f"[TTS] pydub 音频转换: {audio_path} -> {wav_path}")
            return wav_path
        except ImportError:
            pass
        
        try:
            import subprocess
            result = subprocess.run(
                ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", wav_path],
                capture_output=True, timeout=30
            )
            if result.returncode == 0 and os.path.exists(wav_path):
                print(f"[TTS] ffmpeg 音频转换: {audio_path} -> {wav_path}")
                return wav_path
        except Exception:
            pass
        
        print(f"[TTS] 无法转换音频格式 {audio_path}，降级到Edge-TTS")
        return audio_path
    
    def _trim_ref_audio(self, audio_path: str) -> str:
        """裁剪参考音频到 3~10 秒范围（GPT-SoVITS 要求）"""
        try:
            from moviepy import AudioFileClip
            clip = AudioFileClip(audio_path)
            duration = clip.duration
            
            if 3.0 <= duration <= 10.0:
                clip.close()
                return audio_path
            
            # 裁剪到 3~8 秒（取中间段，留余量）
            target_duration = min(8.0, max(3.0, duration))
            start = max(0, (duration - target_duration) / 2)
            end = start + target_duration
            
            trimmed_path = os.path.splitext(audio_path)[0] + "_trimmed.wav"
            trimmed = clip.subclipped(start, end)
            trimmed.write_audiofile(trimmed_path, logger=None)
            clip.close()
            trimmed.close()
            
            print(f"[TTS] 参考音频裁剪: {duration:.1f}s -> {target_duration:.1f}s -> {trimmed_path}")
            return trimmed_path
        except Exception as e:
            print(f"[TTS] 参考音频裁剪失败: {e}，使用原始音频")
            return audio_path
    
    def _get_ref_audio_path(self, voice_id: str) -> str:
        """根据voice_id查找参考音频文件路径"""
        voices_dir = os.path.join(settings.UPLOAD_DIR, "voices")
        if not os.path.exists(voices_dir):
            return None
        
        # 先按 voice_id 精确匹配文件名
        for ext in [".wav", ".mp3", ".flac", ".m4a"]:
            path = os.path.join(voices_dir, f"{voice_id}{ext}")
            if os.path.exists(path):
                return os.path.abspath(path)
        
        # 搜索包含 voice_id 的文件
        for f in os.listdir(voices_dir):
            fpath = os.path.join(voices_dir, f)
            if os.path.isfile(fpath) and f.lower().endswith(('.wav', '.mp3', '.flac', '.m4a')):
                return os.path.abspath(fpath)
        
        return None
    
    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice_source: str = "edge-tts",
        voice_id: Optional[str] = None,
        **kwargs
    ):
        """根据配置选择TTS引擎合成"""
        
        if voice_source == "cloned" and voice_id:
            return await self.synthesize_with_cloned(text, voice_id, output_path, **kwargs)
        else:
            voice_name = kwargs.get("voice_name", "zh-CN-XiaoxiaoNeural")
            return await self.synthesize_with_edge(text, output_path, voice_name)
