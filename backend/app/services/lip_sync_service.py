import os
import subprocess
import asyncio
import httpx
import logging
import time
import uuid
from typing import Optional, List
from app.config import settings

logger = logging.getLogger(__name__)

_DEBUG_LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "lip_sync_debug.log")

def _log(msg: str):
    import datetime
    line = f"[{datetime.datetime.now().isoformat()}] {msg}\n"
    with open(_DEBUG_LOG, "a", encoding="utf-8") as f:
        f.write(line)
    logger.info(msg)


def _get_audio_duration_local(audio_path: str) -> float:
    """获取音频时长（秒）"""
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"
    try:
        result = subprocess.run(
            [ffmpeg_exe, "-i", audio_path, "-f", "null", "-"],
            capture_output=True, text=True, timeout=10
        )
        # 从stderr中提取时长
        import re
        match = re.search(r'Duration:\s*(\d+):(\d+):(\d+\.\d+)', result.stderr)
        if match:
            return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
    except Exception:
        pass
    return 0.0


def _get_gpu_memory_info():
    """获取GPU显存使用信息 (used_mb, total_mb)"""
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.used,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(',')
            return int(parts[0].strip()), int(parts[1].strip())
    except Exception:
        pass
    return None, None


class LipSyncService:
    """口型同步服务 - MuseTalk（带GPU锁和智能重启）"""
    
    def __init__(self):
        self.model = settings.LIP_SYNC_MODEL
        self.wav2lip_path = settings.WAV2LIP_MODEL_PATH
        self.musetalk_api_url = getattr(settings, 'MUSETALK_API_URL', 'http://localhost:7861')
        # GPU锁：确保同一时间只有一个MuseTalk推理任务
        self._gpu_lock = asyncio.Lock()
        # MuseTalk连续推理计数器，用于决定是否需要重启
        self._inference_count = 0
        self._max_inferences_before_restart = 5  # 每5次推理后重启一次防止内存碎片
    
    async def generate_lip_sync_video(
        self,
        image_path: str,
        audio_path: str,
        output_path: str,
        model: Optional[str] = None
    ) -> str:
        """
        生成口型同步视频（带GPU锁，防止并发OOM）
        """
        model = model or self.model
        
        async with self._gpu_lock:
            if model in ("musetalk", "wav2lip", "sadtalker"):
                max_retries = 3
                for attempt in range(1, max_retries + 1):
                    _log(f"Trying MuseTalk (attempt {attempt}/{max_retries}): image={image_path} audio={audio_path}")
                    result = await self._generate_with_musetalk(image_path, audio_path, output_path)
                    _log(f"MuseTalk attempt {attempt} result: {result}")
                    if result:
                        self._inference_count += 1
                        return result
                    if attempt < max_retries:
                        # 重试前先检查MuseTalk健康状态
                        _log(f"MuseTalk failed, checking health before retry...")
                        healthy = await self._ensure_musetalk_healthy()
                        if not healthy:
                            _log(f"MuseTalk unhealthy, restarting...")
                            await self.restart_musetalk()
                        await asyncio.sleep(3)
                
                raise RuntimeError(
                    f"MuseTalk口型视频生成失败（已重试{max_retries}次）。"
                    f"请检查MuseTalk服务是否正常运行（http://localhost:7861/health）。"
                )
            
            raise RuntimeError(f"不支持的口型模型: {model}")
    
    async def _ensure_musetalk_healthy(self) -> bool:
        """检查MuseTalk是否健康且模型已加载到GPU"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                health = await client.get(f"{self.musetalk_api_url}/health")
                if health.status_code == 200:
                    data = health.json()
                    return data.get("models_loaded", False)
        except Exception:
            pass
        return False
    
    async def maybe_restart_if_needed(self):
        """根据推理计数决定是否需要重启MuseTalk（防止GPU内存碎片化）"""
        if self._inference_count >= self._max_inferences_before_restart:
            _log(f"MuseTalk inference count={self._inference_count}, restarting to prevent GPU fragmentation")
            await self.restart_musetalk()
            self._inference_count = 0
    
    async def _generate_with_musetalk(
        self,
        image_path: str,
        audio_path: str,
        output_path: str
    ) -> Optional[str]:
        """使用MuseTalk生成口型同步视频"""
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # 检查MuseTalk API是否可用
                try:
                    health = await client.get(f"{self.musetalk_api_url}/health")
                    _log(f"MuseTalk health: status={health.status_code}")
                    if health.status_code != 200:
                        return None
                    health_data = health.json()
                    if not health_data.get("models_loaded"):
                        # 模型在CPU上，尝试重新加载到GPU
                        _log(f"MuseTalk models on CPU, reloading to GPU...")
                        try:
                            reload_resp = await client.post(f"{self.musetalk_api_url}/reload_gpu", timeout=30.0)
                            if reload_resp.status_code != 200:
                                _log(f"MuseTalk reload_gpu failed: {reload_resp.text}")
                                return None
                            await asyncio.sleep(2)
                        except Exception as re:
                            _log(f"MuseTalk reload_gpu error: {re}")
                            return None
                except httpx.TimeoutException:
                    _log(f"MuseTalk health check timed out - service may be stuck")
                    return None
                except Exception as he:
                    _log(f"MuseTalk health check error: {he}")
                    return None
                
                # 调用MuseTalk生成
                output_dir = os.path.dirname(output_path)
                abs_audio = os.path.abspath(audio_path)
                abs_image = os.path.abspath(image_path)
                abs_outdir = os.path.abspath(output_dir) if output_dir else None
                _log(f"Calling MuseTalk: image={abs_image} exists={os.path.exists(abs_image)}, audio={abs_audio} exists={os.path.exists(abs_audio)}")
                
                # 根据音频时长动态调整超时：每秒音频给20秒超时，最低120秒
                # MuseTalk首次推理需要加载模型，耗时较长
                audio_dur = _get_audio_duration_local(audio_path)
                timeout_seconds = max(120, int(audio_dur * 20)) if audio_dur else 180
                _log(f"MuseTalk timeout: {timeout_seconds}s (audio={audio_dur:.1f}s)")
                
                try:
                    response = await client.post(
                        f"{self.musetalk_api_url}/generate_by_path",
                        json={
                            "audio_path": abs_audio,
                            "image_path": abs_image,
                            "bbox_shift": 0,
                            "extra_margin": 10,
                            "parsing_mode": "jaw",
                            "output_dir": abs_outdir,
                            "enable_micro_expression": False
                        },
                        timeout=timeout_seconds
                    )
                except httpx.TimeoutException:
                    _log(f"MuseTalk request timed out after {timeout_seconds}s")
                    return None
                
                _log(f"MuseTalk response: status={response.status_code} body={response.text[:500]}")
                
                if response.status_code == 200:
                    data = response.json()
                    generated_path = data.get("output_path")
                    if generated_path and os.path.exists(generated_path):
                        if os.path.abspath(generated_path) != os.path.abspath(output_path):
                            import shutil
                            shutil.copy2(generated_path, output_path)
                        logger.info(f"[LipSync] MuseTalk success: {output_path}")
                        return output_path
                    else:
                        logger.warning(f"[LipSync] MuseTalk output file not found: {generated_path}")
                
                return None
                
        except Exception as e:
            logger.error(f"[LipSync] MuseTalk failed: {e}")
            return None
    
    async def restart_musetalk(self):
        """完全重启MuseTalk进程，解决GPU内存碎片化导致的卡死问题"""
        try:
            _log("Restarting MuseTalk...")
            
            # 1. 通过端口7861找到并杀掉MuseTalk进程
            try:
                net_result = subprocess.run(
                    ['netstat', '-ano'], capture_output=True, text=True, timeout=5
                )
                for line in net_result.stdout.split('\n'):
                    if ':7861' in line and 'LISTEN' in line:
                        parts = line.split()
                        pid = parts[-1].strip()
                        if pid.isdigit():
                            subprocess.run(['taskkill', '/f', '/pid', pid], capture_output=True, timeout=5)
                            _log(f"Killed MuseTalk by port: {pid}")
            except Exception as e:
                _log(f"Kill process error: {e}")
            
            # 也通过nvidia-smi查找GPU上的python进程
            try:
                result = subprocess.run(
                    ['nvidia-smi', '--query-compute-apps=pid,name', '--format=csv,noheader'],
                    capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.strip().split('\n'):
                    if 'python' in line.lower():
                        pid = line.split(',')[0].strip()
                        if pid.isdigit():
                            subprocess.run(['taskkill', '/f', '/pid', pid], capture_output=True, timeout=5)
                            _log(f"Killed GPU python process: {pid}")
            except:
                pass
            
            await asyncio.sleep(5)
            
            # 2. 重新启动MuseTalk
            musetalk_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
                "MuseTalk"
            )
            conda_exe = r"C:\Users\yj821\miniconda3\Scripts\conda.exe"
            
            subprocess.Popen(
                f'pushd "{musetalk_dir}" && {conda_exe} run -n musetalk python musetalk_api_server.py',
                shell=True,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            )
            
            # 3. 等待MuseTalk重新就绪（最多5分钟）
            for attempt in range(100):
                await asyncio.sleep(3)
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        h = await client.get(f"{self.musetalk_api_url}/health")
                        if h.status_code == 200 and h.json().get("models_loaded"):
                            _log(f"MuseTalk restarted successfully (attempt {attempt+1})")
                            return True
                except:
                    pass
            
            _log("MuseTalk restart failed after 100 attempts")
            return False
            
        except Exception as e:
            _log(f"MuseTalk restart error: {e}")
            return False

    async def _fallback_static_video(
        self,
        image_path: str,
        audio_path: str,
        output_path: str
    ) -> str:
        """
        降级方案：使用moviepy将静态图片+音频合成视频
        """
        try:
            from moviepy import ImageClip, AudioFileClip, CompositeVideoClip
            
            image_clip = ImageClip(image_path)
            audio_clip = AudioFileClip(audio_path)
            
            duration = audio_clip.duration
            video_clip = image_clip.with_duration(duration)
            video_clip = video_clip.with_audio(audio_clip)
            video_clip = video_clip.resized(height=720)
            
            video_clip.write_videofile(
                output_path,
                fps=24,
                codec='libx264',
                audio_codec='aac',
                temp_audiofile='temp-audio.m4a',
                remove_temp=True
            )
            
            video_clip.close()
            audio_clip.close()
            
            if os.path.exists(output_path):
                return output_path
            else:
                raise RuntimeError("moviepy 生成视频失败")
                
        except Exception as e:
            raise RuntimeError(f"降级视频生成失败: {str(e)}")


async def _generate_segmented_musetalk(
    image_path: str,
    audio_path: str,
    output_path: str,
    segment_duration: float = 20.0,
    output_dir: str = None,
    project_id: int = None,
    slide_index: int = None,
) -> str:
    """分段生成MuseTalk口型视频，避免长音频OOM
    
    将长音频按segment_duration切分，逐段生成MuseTalk视频，
    最后拼接为完整视频并附加原始音频。
    
    Args:
        image_path: 数字人图片路径
        audio_path: 完整音频路径
        output_path: 最终输出视频路径
        segment_duration: 每段最大时长（秒）
        output_dir: 临时文件目录
        project_id: PPT项目ID（用于日志）
        slide_index: PPT页码（用于日志）
    
    Returns:
        输出视频路径
    """
    from moviepy import AudioFileClip, VideoFileClip, concatenate_videoclips
    
    log_prefix = f"[SegmentedMuseTalk]"
    if project_id is not None:
        log_prefix = f"[PPT-{project_id}-Slide{slide_index}]"
    
    _log(f"{log_prefix} Starting segmented MuseTalk for audio: {audio_path}")
    
    # 1. 获取音频时长
    audio_clip = AudioFileClip(audio_path)
    total_duration = audio_clip.duration
    _log(f"{log_prefix} Total audio duration: {total_duration:.1f}s, segment_duration: {segment_duration}s")
    
    if total_duration <= segment_duration:
        # 不需要分段，直接调用MuseTalk
        audio_clip.close()
        service = LipSyncService()
        return await service.generate_lip_sync_video(
            image_path=image_path,
            audio_path=audio_path,
            output_path=output_path,
        )
    
    # 2. 分段切割音频
    if output_dir is None:
        output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)
    
    seg_dir = os.path.join(output_dir, f"seg_{uuid.uuid4().hex[:8]}")
    os.makedirs(seg_dir, exist_ok=True)
    
    num_segments = int(total_duration / segment_duration) + (1 if total_duration % segment_duration > 0.5 else 0)
    _log(f"{log_prefix} Splitting into {num_segments} segments")
    
    segment_videos = []
    service = LipSyncService()
    
    try:
        for i in range(num_segments):
            start = i * segment_duration
            end = min((i + 1) * segment_duration, total_duration)
            
            if end - start < 0.5:
                continue
            
            # 切割音频段
            seg_audio_path = os.path.join(seg_dir, f"seg_{i:03d}.wav")
            seg_audio = audio_clip.subclipped(start, end)
            seg_audio.write_audiofile(seg_audio_path, logger=None)
            seg_audio.close()
            
            _log(f"{log_prefix} Segment {i+1}/{num_segments}: {start:.1f}s-{end:.1f}s ({end-start:.1f}s)")
            
            # 生成口型视频
            seg_video_path = os.path.join(seg_dir, f"seg_{i:03d}.mp4")
            try:
                result = await service.generate_lip_sync_video(
                    image_path=image_path,
                    audio_path=seg_audio_path,
                    output_path=seg_video_path,
                )
                
                if result and os.path.exists(seg_video_path) and os.path.getsize(seg_video_path) > 1000:
                    segment_videos.append(seg_video_path)
                    _log(f"{log_prefix} Segment {i+1} OK: {os.path.getsize(seg_video_path)} bytes")
                else:
                    _log(f"{log_prefix} Segment {i+1} FAILED: invalid output")
                    raise RuntimeError(f"Segment {i+1} lip sync failed")
                    
            except Exception as e:
                _log(f"{log_prefix} Segment {i+1} error: {e}")
                raise
        
        # 3. 拼接所有段视频
        _log(f"{log_prefix} Concatenating {len(segment_videos)} segments")
        
        clips = []
        for vp in segment_videos:
            clips.append(VideoFileClip(vp))
        
        final_clip = concatenate_videoclips(clips, method="compose")
        
        # 4. 用原始完整音频替换拼接后的音频（确保音画同步）
        original_audio = AudioFileClip(audio_path)
        final_clip = final_clip.with_audio(original_audio)
        
        final_clip.write_videofile(
            output_path,
            fps=25,
            codec="libx264",
            audio_codec="aac",
            logger=None,
        )
        
        # 清理
        original_audio.close()
        for clip in clips:
            clip.close()
        final_clip.close()
        audio_clip.close()
        
        # 删除临时分段文件（保留最终输出）
        import shutil
        try:
            shutil.rmtree(seg_dir, ignore_errors=True)
        except Exception:
            pass
        
        _log(f"{log_prefix} Final video: {output_path} ({os.path.getsize(output_path)} bytes)")
        return output_path
        
    except Exception as e:
        audio_clip.close()
        _log(f"{log_prefix} FAILED: {e}")
        raise RuntimeError(f"分段MuseTalk生成失败: {str(e)}")
