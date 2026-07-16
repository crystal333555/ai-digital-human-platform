import os
import re
import uuid
import asyncio
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.avatar import Avatar, Voice
from app.services.tts_service import TTSService
from app.services.lip_sync_service import LipSyncService, _generate_segmented_musetalk
from app.config import settings

# 项目根目录（backend/app/routers/ -> backend/app/ -> backend/ -> 项目根）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _resolve_path(rel_path: str) -> str:
    """将相对路径解析为基于项目根目录的绝对路径"""
    if not rel_path:
        return ""
    if len(rel_path) >= 2 and rel_path[1] == ':':
        return rel_path
    clean = rel_path.replace("\\", "/")
    while clean.startswith("/") or clean.startswith("./") or clean.startswith("../"):
        if clean.startswith("/"):
            clean = clean[1:]
        elif clean.startswith("./"):
            clean = clean[2:]
        elif clean.startswith("../"):
            clean = clean[3:]
    return os.path.join(_PROJECT_ROOT, clean)


def _path_to_url(abs_path: str) -> str:
    """将绝对文件路径转为前端可访问的URL路径"""
    if not abs_path:
        return ""
    p = abs_path.replace("\\", "/")
    # D:\AI_Avatar_Data\generated\... -> /data/generated/...
    data_root = settings.GENERATED_DIR.replace("\\", "/")
    if p.startswith(data_root):
        return "/data/generated/" + p[len(data_root)+1:]
    # 项目根目录下的 uploads/... -> /uploads/...
    uploads_root = settings.UPLOAD_DIR.replace("\\", "/")
    if p.startswith(uploads_root):
        return "/uploads/" + p[len(uploads_root)+1:]
    # 降级：返回最后 uploads/ 或 generated/ 之后的部分
    for prefix in ["/uploads/", "/data/generated/", "/generated/"]:
        idx = p.find(prefix)
        if idx >= 0:
            return prefix + p[idx+len(prefix):]
    return p

router = APIRouter()

tts_service = TTSService()

# 演讲视频生成串行锁 - 同一时间只允许一个视频生成
_speech_generation_lock = asyncio.Lock()


def _get_audio_duration_local(audio_path: str) -> float:
    """获取音频文件时长（秒）"""
    try:
        from moviepy import AudioFileClip
        clip = AudioFileClip(audio_path)
        dur = clip.duration
        clip.close()
        return dur
    except Exception:
        return 0.0
lip_sync_service = LipSyncService()


class SpeechGenerateRequest(BaseModel):
    avatar_id: int
    voice_id: Optional[int] = None
    voice_config: Optional[dict] = None  # {"type": "preset", "id": "xxx", "edge_voice": "...", "rate": "+0%", "pitch": "+0Hz"}
    text: str
    title: Optional[str] = "演讲视频"
    segment_strategy: Optional[str] = "sentence"  # sentence | paragraph
    model: Optional[str] = "musetalk"
    speed: Optional[float] = 1.0  # TTS语速倍率 (0.5~2.0, 默认1.0)


class SpeechSegment(BaseModel):
    index: int
    text: str
    audio_path: Optional[str] = None
    video_path: Optional[str] = None
    status: str = "pending"  # pending | processing | done | error


class SpeechTaskResponse(BaseModel):
    task_id: str
    status: str
    message: str
    segments: List[SpeechSegment]
    output_video: Optional[str] = None


# 内存中存储任务状态（生产环境应使用 Redis/DB）
_speech_tasks: dict = {}


def split_text(text: str, strategy: str = "sentence") -> List[str]:
    """将长文本分割为多段"""
    text = text.strip()
    if not text:
        return []

    if strategy == "paragraph":
        # 按段落分割（空行分隔）
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if p.strip()]
    else:
        # 按句子分割（中文标点：。！？；）
        sentences = re.split(r'(?<=[。！？；!?;])\s*', text)
        # 合并过短的句子（<10字的合并到上一句）
        merged = []
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if merged and len(s) < 10:
                merged[-1] += s
            else:
                merged.append(s)
        return merged


async def generate_speech_video_task(
    task_id: str,
    segments: List[str],
    avatar: Avatar,
    voice: Voice,
    model: str,
    output_dir: str,
    speed: float = 1.0,
):
    """后台任务：串行生成音频+视频，避免GPU显存冲突
    
    流程：Phase1 生成所有TTS音频 → Phase2 生成所有口型视频 → Phase3 拼接
    GPT-SoVITS和MuseTalk不会同时推理，避免4090 16GB显存OOM
    
    同时只允许一个视频生成任务运行（串行锁）
    """
    # 串行锁：等待其他视频生成任务完成
    if _speech_generation_lock.locked():
        task = _speech_tasks[task_id]
        task["message"] = "等待其他视频生成任务完成..."
    
    async with _speech_generation_lock:
        await _generate_speech_video_inner(
            task_id, segments, avatar, voice, model, output_dir, speed
        )


async def _generate_speech_video_inner(
    task_id: str,
    segments: List[str],
    avatar: Avatar,
    voice: Voice,
    model: str,
    output_dir: str,
    speed: float = 1.0,
):
    """演讲视频生成实际逻辑"""
    task = _speech_tasks[task_id]
    task["status"] = "processing"

    # 解析图片路径（支持 ../uploads/ /uploads/ uploads/ 等多种格式）
    image_path = avatar.styled_image_path or avatar.original_image_path
    if image_path:
        image_path = _resolve_path(image_path)
    
    if not image_path or not os.path.exists(image_path):
        image_path = _resolve_path(avatar.original_image_path) if avatar.original_image_path else ""

    if not image_path or not os.path.exists(image_path):
        task["status"] = "error"
        task["message"] = "数字人形象图片不存在"
        return

    image_path = _resolve_path(image_path)

    # ============ GPU协调调度 ============
    from app.services.gpu_coordinator import GPUCoordinator
    gpu_coord = GPUCoordinator.get_instance()

    # ============ Phase 1: 生成所有TTS音频（GPT-SoVITS占用显存）============
    task["message"] = f"Phase 0: 协调GPU显存，释放MuseTalk..."
    await gpu_coord.acquire_for_tts()
    
    task["message"] = f"Phase 1: 生成TTS音频 (0/{len(segments)})"
    audio_files = []
    
    for i, seg_text in enumerate(segments):
        seg = task["segments"][i]
        seg["status"] = "processing"
        task["current_segment"] = i
        task["message"] = f"Phase 1: 生成TTS音频 ({i+1}/{len(segments)})"

        try:
            audio_filename = f"seg_{i:03d}_{uuid.uuid4().hex[:8]}.wav"
            audio_path = os.path.join(output_dir, audio_filename)

            if voice.source == "cloned" and voice.reference_audio_path:
                ref_audio = _resolve_path(voice.reference_audio_path)
                # GPT-SoVITS prompt_text 应为参考音频中说的文字，留空比乱填好
                prompt_text = ""
                if voice.tts_config and isinstance(voice.tts_config, dict):
                    prompt_text = voice.tts_config.get("prompt_text", "")
                result_path = await tts_service.synthesize_with_cloned(
                    text=seg_text,
                    voice_id=str(voice.id),
                    output_path=audio_path,
                    ref_audio_path=ref_audio,
                    prompt_text=prompt_text,
                    speed=speed,
                )
                # 验证音频文件确实存在且有效
                if not result_path or not os.path.exists(audio_path) or os.path.getsize(audio_path) < 1000:
                    raise RuntimeError("TTS音频生成失败: 文件无效或不存在")
            else:
                edge_voice = "zh-CN-XiaoxiaoNeural"
                if voice.tts_config and isinstance(voice.tts_config, dict):
                    edge_voice = voice.tts_config.get("edge_voice_name", "zh-CN-XiaoxiaoNeural")
                await tts_service.synthesize_with_edge(
                    text=seg_text,
                    output_path=audio_path,
                    voice_name=edge_voice
                )

            seg["audio_path"] = audio_path
            audio_files.append(audio_path)

        except Exception as e:
            seg["status"] = "error"
            seg["error"] = f"TTS失败: {str(e)}"
            audio_files.append(None)

    # 检查是否有有效音频
    valid_audio = [a for a in audio_files if a is not None]
    if not valid_audio:
        task["status"] = "error"
        task["message"] = "所有TTS音频生成失败"
        return

    # ============ Phase 2: 生成所有口型视频（MuseTalk占用显存）============
    task["message"] = f"Phase 2: 协调GPU，加载MuseTalk模型..."
    tts_released = await gpu_coord.release_from_tts()
    lipsync_ready = await gpu_coord.acquire_for_lipsync()
    if not lipsync_ready:
        task["status"] = "error"
        task["message"] = "MuseTalk模型加载失败，无法生成口型视频。请检查MuseTalk服务是否正常运行。"
        return
    
    task["message"] = f"Phase 2: 生成口型视频 (0/{len(valid_audio)})"
    video_files = []

    for i, seg_text in enumerate(segments):
        seg = task["segments"][i]
        
        if seg["status"] == "error" or not seg.get("audio_path"):
            continue

        task["message"] = f"Phase 2: 生成口型视频 ({len(video_files)+1}/{len(valid_audio)})"

        try:
            audio_path = seg["audio_path"]
            audio_dur = _get_audio_duration_local(audio_path)
            
            # 长音频分段处理，避免MuseTalk OOM
            if audio_dur > 25.0:
                logger.info(f"[Speech] Segment {i}: audio {audio_dur:.1f}s > 25s, splitting for MuseTalk")
                video_filename = f"seg_{i:03d}_{uuid.uuid4().hex[:8]}.mp4"
                video_path = os.path.join(output_dir, video_filename)
                result = await _generate_segmented_musetalk(
                    image_path=image_path,
                    audio_path=audio_path,
                    output_path=video_path,
                    segment_duration=20.0,
                    output_dir=output_dir,
                )
                if result and os.path.exists(video_path) and os.path.getsize(video_path) > 1000:
                    seg["video_path"] = video_path
                    seg["status"] = "done"
                    video_files.append(video_path)
                else:
                    raise RuntimeError("分段口型视频生成失败")
            else:
                video_filename = f"seg_{i:03d}_{uuid.uuid4().hex[:8]}.mp4"
                video_path = os.path.join(output_dir, video_filename)

                result = await lip_sync_service.generate_lip_sync_video(
                    image_path=image_path,
                    audio_path=audio_path,
                    output_path=video_path,
                    model=model
                )
                
                if not result or not os.path.exists(video_path) or os.path.getsize(video_path) < 1000:
                    raise RuntimeError("口型视频生成失败: 输出文件无效")

                seg["video_path"] = video_path
                seg["status"] = "done"
                video_files.append(video_path)

        except Exception as e:
            seg["status"] = "error"
            seg["error"] = f"口型视频失败: {str(e)}"

    # 3. 拼接所有视频片段
    if not video_files:
        task["status"] = "error"
        task["message"] = "所有片段生成失败"
        return

    try:
        final_filename = f"speech_{task_id}.mp4"
        final_path = os.path.join(output_dir, final_filename)

        if len(video_files) == 1:
            # 只有一段，直接复制
            import shutil
            shutil.copy2(video_files[0], final_path)
        else:
            # 使用 moviepy 拼接
            from moviepy import VideoFileClip, concatenate_videoclips

            clips = []
            for vf in video_files:
                clip = VideoFileClip(vf)
                clips.append(clip)

            final_clip = concatenate_videoclips(clips, method="compose")
            final_clip.write_videofile(
                final_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                temp_audiofile=os.path.join(output_dir, "temp-audio.m4a"),
                remove_temp=True,
                logger=None
            )

            for clip in clips:
                clip.close()
            final_clip.close()

        task["output_video"] = _path_to_url(final_path)
        task["status"] = "completed"
        task["message"] = f"演讲视频生成完成，共 {len(video_files)} 段"

        # 保留所有中间文件（用户要求不删除已生成的视频和音频）
        # 仅清理拼接时的临时音频文件
        try:
            temp_audio = os.path.join(output_dir, "temp-audio.m4a")
            if os.path.exists(temp_audio):
                os.remove(temp_audio)
        except Exception:
            pass

    except Exception as e:
        task["status"] = "error"
        task["message"] = f"视频拼接失败: {str(e)}"


@router.post("/generate", response_model=SpeechTaskResponse)
async def generate_speech(
    request: SpeechGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """生成数字人演讲视频
    
    输入长文本/材料 → 自动分段 → 逐段 TTS → 口型同步视频 → 拼接完整演讲视频
    """
    # 验证形象
    avatar = db.query(Avatar).filter(Avatar.id == request.avatar_id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="数字人形象不存在")

    # 获取音色：支持 voice_id（我的音色）或 voice_config（预置音色）
    voice = None
    voice_config = request.voice_config

    if request.voice_id:
        voice = db.query(Voice).filter(Voice.id == request.voice_id).first()
        if not voice:
            raise HTTPException(status_code=404, detail="音色不存在")
    elif voice_config and voice_config.get("type") == "preset":
        # 从预置音色构建虚拟 Voice 对象
        from app.services.voice_library import get_preset_voice
        preset_id = voice_config.get("id", "calm_professor")  # 默认用calm_professor
        preset = get_preset_voice(preset_id)
        if not preset:
            # 找不到指定音色，用第一个预置音色
            from app.services.voice_library import get_all_preset_voices
            all_presets = get_all_preset_voices()
            preset = all_presets[0] if all_presets else None
        if not preset:
            raise HTTPException(status_code=404, detail="预置音色不存在")
        # 创建一个临时 Voice 对象用于后续处理
        voice = Voice(
            name=preset["name"],
            description=preset["description"],
            source="edge-tts",
            tts_config={
                "edge_voice_name": voice_config.get("edge_voice", preset["edge_tts_voice"]),
                "rate": voice_config.get("rate", preset.get("rate", "+0%")),
                "pitch": voice_config.get("pitch", preset.get("pitch", "+0Hz")),
                "preset_id": voice_config["id"],
                "category": preset["category"]
            }
        )
    else:
        # 默认音色
        voice = db.query(Voice).first()
        if not voice:
            voice = Voice(name="默认", source="edge-tts", tts_config={"edge_voice_name": "zh-CN-XiaoxiaoNeural"})

    # 分割文本
    segments_text = split_text(request.text, request.segment_strategy)
    if not segments_text:
        raise HTTPException(status_code=400, detail="文本内容为空")

    # 创建任务
    task_id = uuid.uuid4().hex[:12]
    output_dir = os.path.join(settings.GENERATED_DIR, "speech")
    os.makedirs(output_dir, exist_ok=True)

    segments = [
        SpeechSegment(index=i, text=t).dict()
        for i, t in enumerate(segments_text)
    ]

    _speech_tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "message": f"已创建演讲视频任务，共 {len(segments_text)} 段",
        "segments": segments,
        "output_video": None,
        "current_segment": -1,
        "title": request.title,
    }

    # 启动后台任务
    background_tasks.add_task(
        generate_speech_video_task,
        task_id=task_id,
        segments=segments_text,
        avatar=avatar,
        voice=voice,
        model=request.model,
        output_dir=output_dir
    )

    return SpeechTaskResponse(
        task_id=task_id,
        status="pending",
        message=f"演讲视频任务已创建，共 {len(segments_text)} 段，正在后台生成中...",
        segments=[SpeechSegment(**s) for s in segments],
        output_video=None
    )


@router.get("/status/{task_id}", response_model=SpeechTaskResponse)
async def get_speech_status(task_id: str):
    """查询演讲视频生成进度"""
    if task_id not in _speech_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")

    task = _speech_tasks[task_id]
    return SpeechTaskResponse(
        task_id=task_id,
        status=task["status"],
        message=task["message"],
        segments=[SpeechSegment(**s) for s in task["segments"]],
        output_video=task.get("output_video")
    )


@router.get("/list")
async def list_speech_tasks():
    """列出所有演讲视频（内存任务 + 磁盘历史）"""
    result = {}
    
    # 1. 内存中的任务
    for tid, task in _speech_tasks.items():
        result[tid] = {
            "task_id": tid,
            "status": task["status"],
            "message": task["message"],
            "title": task.get("title", ""),
            "segment_count": len(task["segments"]),
            "current_segment": task.get("current_segment", -1),
            "output_video": task.get("output_video"),
            "created_at": task.get("created_at"),
        }
    
    # 2. 磁盘上的历史视频（扫描 D:\AI_Avatar_Data\generated\speech\speech_*.mp4）
    speech_dir = os.path.join(settings.GENERATED_DIR, "speech")
    if os.path.isdir(speech_dir):
        for fname in os.listdir(speech_dir):
            if fname.startswith("speech_") and fname.endswith(".mp4"):
                # 从文件名提取 task_id: speech_150daea43675.mp4 -> 150daea43675
                tid = fname[7:-4]  # 去掉 "speech_" 前缀和 ".mp4" 后缀
                if tid not in result:
                    fpath = os.path.join(speech_dir, fname)
                    fstat = os.stat(fpath)
                    # 检查视频是否有效（>1KB）
                    if fstat.st_size > 1024:
                        result[tid] = {
                            "task_id": tid,
                            "status": "completed",
                            "message": "演讲视频",
                            "title": "演讲视频",
                            "segment_count": 0,
                            "current_segment": -1,
                            "output_video": _path_to_url(fpath),
                            "created_at": None,
                            "file_size": fstat.st_size,
                            "file_mtime": fstat.st_mtime,
                        }
    
    # 按创建时间/修改时间倒序排列
    items = sorted(result.values(), key=lambda x: x.get("file_mtime") or 0, reverse=True)
    return {"tasks": items}


@router.delete("/{task_id}")
async def delete_speech_task(task_id: str):
    """删除演讲视频（内存任务 + 磁盘文件）"""
    deleted = False
    
    # 1. 从内存中删除
    if task_id in _speech_tasks:
        task = _speech_tasks.pop(task_id)
        if task.get("output_video"):
            fpath = _resolve_path(task["output_video"])
            if os.path.exists(fpath):
                try:
                    os.remove(fpath)
                    deleted = True
                except Exception:
                    pass
    
    # 2. 从磁盘删除（即使不在内存中）
    speech_dir = os.path.join(settings.GENERATED_DIR, "speech")
    fname = f"speech_{task_id}.mp4"
    fpath = os.path.join(speech_dir, fname)
    if os.path.exists(fpath):
        try:
            os.remove(fpath)
            deleted = True
        except Exception:
            pass
    
    if not deleted and task_id not in _speech_tasks:
        raise HTTPException(status_code=404, detail="视频不存在")
    
    return {"message": "视频已删除"}
