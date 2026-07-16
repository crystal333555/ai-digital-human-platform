import os
import shutil
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.avatar import Voice, User
from app.config import settings

router = APIRouter(prefix="/voices")


def _path_to_url(p: str) -> str:
    """将绝对路径转为URL路径"""
    p = p.replace("\\", "/")
    data_root = settings.GENERATED_DIR.replace("\\", "/")
    if p.startswith(data_root):
        return "/data/generated/" + p[len(data_root)+1:]
    proj_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    uploads_root = os.path.join(proj_root, "uploads").replace("\\", "/")
    if p.startswith(uploads_root):
        return "/uploads/" + p[len(uploads_root)+1:]
    return p


def _ffmpeg_convert_to_wav(audio_path: str, output_path: str, max_duration: float = 10.0) -> bool:
    """用 ffmpeg 将任意音频转为 WAV（16kHz mono），裁剪到指定时长"""
    import subprocess
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"
    try:
        cmd = [
            ffmpeg_exe, "-y", "-i", audio_path,
            "-t", str(max_duration),
            "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        return result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000
    except Exception:
        return False


def _convert_to_trimmed_wav(audio_path: str) -> str:
    """将音频文件转换为 WAV 并裁剪到 3~10 秒（GPT-SoVITS 零样本克隆要求）
    优先用 ffmpeg（支持 M4A/MP3/WAV 等所有格式），降级用 soundfile（仅 WAV）
    """
    # 已有 trimmed 文件直接返回
    trimmed_path = os.path.splitext(audio_path)[0] + '_trimmed.wav'
    if os.path.exists(trimmed_path) and os.path.getsize(trimmed_path) > 1000:
        return trimmed_path

    # 方案1：ffmpeg（支持所有格式）
    if _ffmpeg_convert_to_wav(audio_path, trimmed_path, max_duration=10.0):
        return trimmed_path

    # 方案2：soundfile（仅支持 WAV/FLAC/OGG）
    try:
        import soundfile as sf
        import numpy as np
        data, sr = sf.read(audio_path)
        duration = len(data) / sr
        if duration > 10.0:
            data = data[:int(10.0 * sr)]
        elif duration < 3.0:
            if data.ndim > 1:
                repeat = int(3.0 * sr / len(data)) + 1
                data = np.tile(data, (repeat, 1))[:int(3.0 * sr)]
            else:
                repeat = int(3.0 * sr / len(data)) + 1
                data = np.tile(data, repeat)[:int(3.0 * sr)]
        sf.write(trimmed_path, data, sr)
        if os.path.exists(trimmed_path) and os.path.getsize(trimmed_path) > 1000:
            return trimmed_path
    except Exception:
        pass

    # 全部失败，返回原路径
    return audio_path


def _ensure_wav(audio_path: str) -> str:
    """确保音频文件为WAV格式且3~10秒（GPT-SoVITS零样本克隆要求）"""
    # 如果文件不存在，尝试找原始文件
    if not os.path.exists(audio_path):
        # _trimmed.wav 不存在时，尝试找原始文件（M4A/MP3等）
        if '_trimmed' in audio_path:
            base = audio_path.replace('_trimmed.wav', '')
            for ext in ['.m4a', '.mp3', '.wav', '.ogg', '.flac']:
                candidate = base + ext
                if os.path.exists(candidate):
                    audio_path = candidate
                    break
        if not os.path.exists(audio_path):
            return audio_path  # 返回不存在的路径，让调用方报错
    
    # 如果不是WAV，自动转换
    if not audio_path.lower().endswith('.wav'):
        return _convert_to_trimmed_wav(audio_path)
    # 是WAV，检查时长
    return _check_and_trim_wav(audio_path)


def _check_and_trim_wav(wav_path: str) -> str:
    """检查WAV时长是否在3~10秒，不在则裁剪"""
    import wave
    import numpy as np
    try:
        with wave.open(wav_path, 'rb') as wf:
            frames = wf.getnframes()
            sr = wf.getframerate()
            duration = frames / sr

        if 3.0 <= duration <= 10.0:
            return wav_path

        # 需要裁剪
        import soundfile as sf
        data, sr = sf.read(wav_path)
        if duration > 10.0:
            data = data[:int(10.0 * sr)]
        elif duration < 3.0:
            if data.ndim > 1:
                repeat = int(3.0 * sr / len(data)) + 1
                data = np.tile(data, (repeat, 1))[:int(3.0 * sr)]
            else:
                repeat = int(3.0 * sr / len(data)) + 1
                data = np.tile(data, repeat)[:int(3.0 * sr)]

        trimmed_path = os.path.splitext(wav_path)[0] + '_trimmed.wav'
        sf.write(trimmed_path, data, sr)
        return trimmed_path
    except Exception:
        return wav_path


async def _release_musetalk_gpu():
    """让MuseTalk释放GPU显存，给GPT-SoVITS腾空间"""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post("http://localhost:7861/release_gpu")
            if resp.status_code == 200:
                import asyncio
                await asyncio.sleep(5)  # 等待GPU完全释放
    except Exception:
        pass


class VoiceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    source: str = "edge-tts"
    tts_config: Optional[dict] = None


class VoiceResponse(VoiceCreate):
    id: int
    reference_audio_path: Optional[str] = None
    cloned_voice_id: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.post("/upload", response_model=VoiceResponse)
async def upload_voice_reference(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传参考音频进行音色克隆"""
    allowed_types = ['audio/wav', 'audio/mpeg', 'audio/mp3', 'audio/m4a', 'audio/x-m4a', 'audio/webm']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="仅支持 WAV/MP3/M4A 音频格式")

    import uuid
    file_ext = os.path.splitext(file.filename)[1] or '.wav'
    file_name = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(settings.VOICE_DIR, file_name)

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 自动转换为WAV并裁剪到3~10秒（GPT-SoVITS要求）
    wav_path = _convert_to_trimmed_wav(file_path)

    user = db.query(User).first()
    if not user:
        user = User(username="admin", email="admin@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)

    voice = Voice(
        name=name,
        description=description,
        reference_audio_path=wav_path or file_path,
        source="cloned",
        owner_id=user.id
    )
    db.add(voice)
    db.commit()
    db.refresh(voice)
    return voice


@router.get("/", response_model=List[VoiceResponse])
async def list_voices(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """获取音色列表"""
    voices = db.query(Voice).filter(Voice.is_active == True).offset(skip).limit(limit).all()
    return voices


@router.get("/{voice_id}", response_model=VoiceResponse)
async def get_voice(voice_id: int, db: Session = Depends(get_db)):
    """获取音色详情"""
    voice = db.query(Voice).filter(Voice.id == voice_id, Voice.is_active == True).first()
    if not voice:
        raise HTTPException(status_code=404, detail="音色不存在")
    return voice


@router.post("/{voice_id}/clone")
async def clone_voice(voice_id: int, db: Session = Depends(get_db)):
    """触发音色克隆 - GPT-SoVITS零样本克隆（无需训练）"""
    voice = db.query(Voice).filter(Voice.id == voice_id).first()
    if not voice:
        raise HTTPException(status_code=404, detail="音色不存在")

    if not voice.reference_audio_path:
        raise HTTPException(status_code=400, detail="该音色没有参考音频，无法克隆")

    try:
        import httpx
        import uuid
        ref_path = _ensure_wav(voice.reference_audio_path)
        if not os.path.exists(ref_path):
            raise HTTPException(status_code=400, detail=f"参考音频文件不存在: {ref_path}")

        test_text = "音色克隆测试成功，你可以使用这个音色来生成语音了。"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.get(
                f"{settings.GPT_SOVITS_API_URL}/tts",
                params={
                    "text": test_text,
                    "text_lang": "zh",
                    "ref_audio_path": ref_path,
                    "prompt_lang": "zh",
                    "prompt_text": ""
                }
            )

        content_type = resp.headers.get("content-type", "")
        if resp.status_code == 200 and "audio" in content_type:
            test_file = os.path.join(
                settings.GENERATED_DIR, "voice_preview",
                f"clone_test_{voice_id}_{uuid.uuid4().hex[:8]}.wav"
            )
            os.makedirs(os.path.dirname(test_file), exist_ok=True)
            with open(test_file, "wb") as f:
                f.write(resp.content)

            voice.cloned_voice_id = "gpt-sovits-zero-shot"
            voice.source = "cloned"
            db.commit()

            return {
                "status": "success",
                "voice_id": voice_id,
                "message": "音色克隆成功！GPT-SoVITS零样本克隆，无需训练",
                "preview_url": _path_to_url(test_file),
                "cloned_voice_id": "gpt-sovits-zero-shot"
            }
        else:
            return {
                "status": "error",
                "voice_id": voice_id,
                "message": f"克隆测试失败: GPT-SoVITS返回 {resp.status_code}"
            }
    except httpx.TimeoutException:
        return {
            "status": "error",
            "voice_id": voice_id,
            "message": "GPT-SoVITS超时，请确认服务正在运行"
        }
    except Exception as e:
        return {
            "status": "error",
            "voice_id": voice_id,
            "message": f"克隆失败: {str(e)}"
        }


@router.get("/{voice_id}/preview")
async def preview_voice(
    voice_id: int,
    text: str = "你好，这是我的声音，很高兴认识你。",
    db: Session = Depends(get_db)
):
    """试听音色 - 用该音色合成一段测试音频"""
    voice = db.query(Voice).filter(Voice.id == voice_id, Voice.is_active == True).first()
    if not voice:
        raise HTTPException(status_code=404, detail="音色不存在")

    import uuid
    preview_dir = os.path.join(settings.GENERATED_DIR, "voice_preview")
    os.makedirs(preview_dir, exist_ok=True)

    if voice.source == "cloned" and voice.reference_audio_path:
        ref_path = _ensure_wav(voice.reference_audio_path)
        if not os.path.exists(ref_path):
            raise HTTPException(status_code=400, detail="参考音频文件不存在")

        try:
            import httpx

            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.get(
                    f"{settings.GPT_SOVITS_API_URL}/tts",
                    params={
                        "text": text,
                        "text_lang": "zh",
                        "ref_audio_path": ref_path,
                        "prompt_lang": "zh",
                        "prompt_text": ""
                    }
                )

            # GPT-SoVITS出错时status_code可能仍是200，但返回JSON错误
            content_type = resp.headers.get("content-type", "")
            if resp.status_code == 200 and "audio" in content_type:
                preview_file = os.path.join(
                    preview_dir, f"preview_{voice_id}_{uuid.uuid4().hex[:8]}.wav"
                )
                with open(preview_file, "wb") as f:
                    f.write(resp.content)
                return {"audio_url": _path_to_url(preview_file)}
            elif resp.status_code == 200 and "json" in content_type:
                # GPT-SoVITS返回了JSON错误
                err_data = resp.json()
                err_msg = err_data[0].get("error", "未知错误") if isinstance(err_data, list) else str(err_data)
                raise HTTPException(status_code=500, detail=f"GPT-SoVITS错误: {err_msg}")
            else:
                # 尝试解析为JSON错误
                try:
                    err_data = resp.json()
                    err_msg = err_data[0].get("error", "未知错误") if isinstance(err_data, list) else str(err_data)
                except Exception:
                    err_msg = f"GPT-SoVITS返回 {resp.status_code}"
                raise HTTPException(status_code=500, detail=err_msg)
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="GPT-SoVITS超时")
    elif voice.source == "edge-tts" or voice.tts_config:
        voice_name = voice.tts_config.get("voice_name", "zh-CN-XiaoxiaoNeural") if voice.tts_config else "zh-CN-XiaoxiaoNeural"
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, voice_name)
            preview_file = os.path.join(
                preview_dir, f"preview_{voice_id}_{uuid.uuid4().hex[:8]}.mp3"
            )
            await communicate.save(preview_file)
            return {"audio_url": _path_to_url(preview_file)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Edge-TTS失败: {str(e)}")
    else:
        raise HTTPException(status_code=400, detail="该音色不支持试听")


@router.delete("/{voice_id}")
async def delete_voice(voice_id: int, db: Session = Depends(get_db)):
    """删除音色"""
    voice = db.query(Voice).filter(Voice.id == voice_id).first()
    if not voice:
        raise HTTPException(status_code=404, detail="音色不存在")

    voice.is_active = False
    db.commit()
    return {"message": "音色已删除"}
