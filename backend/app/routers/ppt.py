"""PPT数字人讲解 API路由"""

import os
import uuid
import shutil
import logging
import subprocess
import asyncio
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ppt import PPTProject, PPTSlide
from app.models.avatar import Avatar, Voice
from app.services.ppt_parser import parse_ppt
from app.services.tts_service import TTSService
from app.services.lip_sync_service import LipSyncService
from app.services.ppt_video_composer import compose_slide_video, compose_full_ppt_video
from app.services.gpu_coordinator import GPUCoordinator
from app.config import settings

logger = logging.getLogger(__name__)

# PPT生成串行锁 - 同一时间只允许一个PPT生成任务
_ppt_generation_running = False  # 简单标志位替代Lock

# 项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _get_audio_duration(audio_path: str) -> float:
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
        for line in result.stderr.split("\n"):
            if "Duration:" in line:
                # Duration: 00:00:25.12
                time_str = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = time_str.split(":")
                return float(h) * 3600 + float(m) * 60 + float(s)
    except Exception as e:
        logger.warning(f"[PPT] Failed to get audio duration: {e}")
    return 30.0  # 默认30秒


def _resolve_path(rel_path: str) -> str:
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
    # D:\AI_Avatar_Data\ppt\... -> /data/ppt/...
    ppt_root = settings.PPT_DIR.replace("\\", "/")
    if p.startswith(ppt_root):
        return "/data/ppt/" + p[len(ppt_root)+1:]
    # 项目根目录下的 uploads/... -> /uploads/...
    uploads_root = settings.UPLOAD_DIR.replace("\\", "/")
    if p.startswith(uploads_root):
        return "/uploads/" + p[len(uploads_root)+1:]
    for prefix in ["/uploads/", "/data/generated/", "/data/ppt/", "/generated/"]:
        idx = p.find(prefix)
        if idx >= 0:
            return prefix + p[idx+len(prefix):]
    return p


router = APIRouter()

tts_service = TTSService()
lip_sync_service = LipSyncService()

# 内存任务状态
_ppt_tasks: dict = {}


# ===== 请求/响应模型 =====

class PPTUploadResponse(BaseModel):
    project_id: int
    name: str
    slide_count: int
    slides: List[dict]


class SlideNarrationUpdate(BaseModel):
    narration_text: str


class PPTGenerateRequest(BaseModel):
    avatar_id: int
    voice_config: Optional[dict] = None
    voice_id: Optional[int] = None
    layout_mode: str = "pip"
    digital_human_position: str = "bottom-right"
    digital_human_size: float = 0.25
    transition: str = "fade"
    model: str = "musetalk"
    segment_duration: float = 30.0
    bbox_shift: int = 0
    musetalk_timeout_per_second: int = 30
    start_slide: int = 0
    end_slide: int = 0  # 0表示到最后


class PPTGenerateResponse(BaseModel):
    task_id: str
    project_id: int
    status: str
    message: str


class PPTTaskStatus(BaseModel):
    task_id: str
    project_id: int
    status: str
    message: str
    current_slide: int
    total_slides: int
    output_video: Optional[str] = None


# ===== API端点 =====

@router.post("/upload", response_model=PPTUploadResponse)
async def upload_ppt(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """上传PPT文件，自动解析提取页面"""
    if not file.filename.endswith(('.pptx', '.ppt')):
        raise HTTPException(status_code=400, detail="仅支持 .pptx 格式文件")
    
    # 保存文件
    ppt_dir = settings.PPT_DIR
    os.makedirs(ppt_dir, exist_ok=True)
    
    file_ext = os.path.splitext(file.filename)[1]
    file_name = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(ppt_dir, file_name)
    
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # 解析PPT
    project_name = name or os.path.splitext(file.filename)[0]
    slides_dir = os.path.join(ppt_dir, f"{uuid.uuid4().hex}_slides")
    
    try:
        import asyncio
        slides = await asyncio.to_thread(parse_ppt, file_path, slides_dir)
    except Exception as e:
        # 清理
        if os.path.exists(file_path):
            os.remove(file_path)
        if os.path.exists(slides_dir):
            shutil.rmtree(slides_dir)
        raise HTTPException(status_code=400, detail=f"PPT解析失败: {str(e)}")
    
    if not slides:
        raise HTTPException(status_code=400, detail="PPT无有效页面")
    
    # 创建数据库记录
    user = db.query(Avatar).first()  # 简化：取第一个用户
    owner_id = None
    
    project = PPTProject(
        name=project_name,
        ppt_file_path=file_path,
        slide_count=len(slides),
        status="draft",
        owner_id=owner_id,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # 创建页面记录
    slide_records = []
    for s in slides:
        slide = PPTSlide(
            project_id=project.id,
            slide_index=s["index"],
            slide_image_path=s["image_path"],
            extracted_text=s.get("text", ""),
            narration_text=s.get("text", ""),  # 默认用提取的文字作为讲稿
        )
        db.add(slide)
        slide_records.append(slide)
    
    db.commit()
    
    # 构建响应
    slides_data = []
    for sr in slide_records:
        slides_data.append({
            "id": sr.id,
            "slide_index": sr.slide_index,
            "slide_image_path": _path_to_url(sr.slide_image_path) if sr.slide_image_path else None,
            "extracted_text": sr.extracted_text,
            "narration_text": sr.narration_text,
        })
    
    return PPTUploadResponse(
        project_id=project.id,
        name=project_name,
        slide_count=len(slides),
        slides=slides_data,
    )


@router.get("/projects", response_model=List[dict])
async def list_projects(db: Session = Depends(get_db)):
    """列出所有PPT项目"""
    projects = db.query(PPTProject).order_by(PPTProject.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "slide_count": p.slide_count,
            "status": p.status,
            "output_video_path": _path_to_url(p.output_video_path) if p.output_video_path else None,
            "created_at": str(p.created_at),
        }
        for p in projects
    ]


@router.get("/projects/{project_id}", response_model=dict)
async def get_project(project_id: int, db: Session = Depends(get_db)):
    """获取PPT项目详情（含所有页面）"""
    project = db.query(PPTProject).filter(PPTProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    slides = db.query(PPTSlide).filter(
        PPTSlide.project_id == project_id
    ).order_by(PPTSlide.slide_index).all()
    
    return {
        "id": project.id,
        "name": project.name,
        "ppt_file_path": project.ppt_file_path,
        "slide_count": project.slide_count,
        "status": project.status,
        "layout_mode": project.layout_mode,
        "digital_human_position": project.digital_human_position,
        "digital_human_size": project.digital_human_size,
        "transition": project.transition,
        "output_video_path": _path_to_url(project.output_video_path) if project.output_video_path else None,
        "avatar_id": project.avatar_id,
        "voice_config": project.voice_config,
        "slides": [
            {
                "id": s.id,
                "slide_index": s.slide_index,
                "slide_image_path": _path_to_url(s.slide_image_path) if s.slide_image_path else None,
                "extracted_text": s.extracted_text,
                "narration_text": s.narration_text,
                "status": s.status,
                "duration": s.duration,
            }
            for s in slides
        ],
    }


@router.put("/projects/{project_id}/slides/{slide_id}")
async def update_slide_narration(
    project_id: int,
    slide_id: int,
    update: SlideNarrationUpdate,
    db: Session = Depends(get_db),
):
    """更新单页PPT的讲解文字"""
    slide = db.query(PPTSlide).filter(
        PPTSlide.project_id == project_id,
        PPTSlide.id == slide_id,
    ).first()
    if not slide:
        raise HTTPException(status_code=404, detail="页面不存在")
    
    slide.narration_text = update.narration_text
    db.commit()
    return {"message": "更新成功", "narration_text": slide.narration_text}


@router.post("/projects/{project_id}/generate", response_model=PPTGenerateResponse)
async def generate_ppt_video(
    project_id: int,
    request: PPTGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """生成PPT数字人讲解视频"""
    project = db.query(PPTProject).filter(PPTProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    
    # 验证形象
    avatar = db.query(Avatar).filter(Avatar.id == request.avatar_id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="数字人形象不存在")
    
    # 获取音色
    voice = None
    voice_config = request.voice_config
    
    if request.voice_id:
        voice = db.query(Voice).filter(Voice.id == request.voice_id).first()
        if not voice:
            raise HTTPException(status_code=404, detail="音色不存在")
    elif voice_config and voice_config.get("type") == "preset":
        from app.services.voice_library import get_preset_voice
        preset = get_preset_voice(voice_config["id"])
        if not preset:
            raise HTTPException(status_code=404, detail="预置音色不存在")
        voice = Voice(
            name=preset["name"],
            source="edge-tts",
            tts_config={
                "edge_voice_name": voice_config.get("edge_voice", preset["edge_tts_voice"]),
                "rate": voice_config.get("rate", preset.get("rate", "+0%")),
                "pitch": voice_config.get("pitch", preset.get("pitch", "+0Hz")),
            }
        )
    else:
        voice = Voice(name="默认", source="edge-tts", tts_config={"edge_voice_name": "zh-CN-XiaoxiaoNeural"})
    
    # 更新项目配置
    project.avatar_id = request.avatar_id
    project.voice_config = voice_config or {"type": "my", "voice_id": request.voice_id}
    project.layout_mode = request.layout_mode
    project.digital_human_position = request.digital_human_position
    project.digital_human_size = request.digital_human_size
    project.transition = request.transition
    project.status = "generating"
    db.commit()
    
    # 获取页面
    slides = db.query(PPTSlide).filter(
        PPTSlide.project_id == project_id
    ).order_by(PPTSlide.slide_index).all()
    
    # 检查是否有讲解文字，如果全部为空则自动填充默认讲解词
    valid_slides = [s for s in slides if s.narration_text and s.narration_text.strip() and s.narration_text.strip() != '\ufeff']
    if not valid_slides:
        # 自动为每页填充默认讲解词
        for i, s in enumerate(slides):
            default_text = f"这是第{i+1}页幻灯片的内容。"
            s.narration_text = default_text
            s.extracted_text = default_text
            db.commit()
        valid_slides = slides
        logger.info(f"[PPT] Auto-filled default narration for {len(slides)} slides")
    
    # 按页数范围过滤（用于测试前N页）
    if request.start_slide > 0 or request.end_slide > 0:
        start = request.start_slide if request.start_slide > 0 else 0
        end = request.end_slide if request.end_slide > 0 else len(valid_slides)
        valid_slides = [s for s in valid_slides if start <= s.slide_index < end]
        logger.info(f"[PPT] Slide range filter: start={start}, end={end}, filtered={len(valid_slides)} slides")
    
    # 创建任务
    task_id = uuid.uuid4().hex[:12]
    _ppt_tasks[task_id] = {
        "task_id": task_id,
        "project_id": project_id,
        "status": "pending",
        "message": f"已创建任务，共 {len(valid_slides)} 页需要生成",
        "current_slide": 0,
        "total_slides": len(valid_slides),
        "output_video": None,
    }
    
    # 启动后台任务（用线程池替代asyncio，确保任务不被取消）
    import threading
    _seg_dur = request.segment_duration
    _bbox = request.bbox_shift
    _timeout_ps = request.musetalk_timeout_per_second
    _model = request.model
    _layout = request.layout_mode
    _pos = request.digital_human_position
    _size = request.digital_human_size
    _trans = request.transition
    _avatar_id = avatar.id
    _voice_id = voice.id if voice else None
    _slide_ids = [s.id for s in valid_slides]
    
    def _run_async_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # 在线程内重新创建DB Session查询对象
            from app.database import SessionLocal
            thread_db = SessionLocal()
            thread_avatar = thread_db.query(Avatar).filter(Avatar.id == _avatar_id).first()
            thread_voice = thread_db.query(Voice).filter(Voice.id == _voice_id).first() if _voice_id else None
            thread_slides = thread_db.query(PPTSlide).filter(PPTSlide.id.in_(_slide_ids)).order_by(PPTSlide.slide_index).all()
            
            loop.run_until_complete(_generate_ppt_video_task(
                task_id=task_id,
                project_id=project_id,
                slides=thread_slides,
                avatar=thread_avatar,
                voice=thread_voice,
                model=_model,
                layout_mode=_layout,
                position=_pos,
                size_ratio=_size,
                transition=_trans,
                segment_duration=_seg_dur,
                bbox_shift=_bbox,
                musetalk_timeout_per_second=_timeout_ps,
            ))
        except Exception as e:
            logger.error(f"[PPT] Background task error: {e}")
            _ppt_tasks[task_id]["status"] = "error"
            _ppt_tasks[task_id]["message"] = str(e)
        finally:
            loop.close()
    
    thread = threading.Thread(target=_run_async_task, daemon=True)
    thread.start()
    
    return PPTGenerateResponse(
        task_id=task_id,
        project_id=project_id,
        status="pending",
        message=f"已创建任务，共 {len(valid_slides)} 页",
    )


@router.get("/tasks/{task_id}", response_model=PPTTaskStatus)
async def get_task_status(task_id: str):
    """获取PPT视频生成任务状态"""
    if task_id not in _ppt_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    task = _ppt_tasks[task_id]
    return PPTTaskStatus(**task)


@router.get("/tasks", response_model=List[PPTTaskStatus])
async def list_tasks():
    """列出所有PPT任务"""
    return [PPTTaskStatus(**t) for t in _ppt_tasks.values()]


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消/暂停PPT生成任务"""
    if task_id not in _ppt_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    task = _ppt_tasks[task_id]
    if task["status"] in ("completed", "error", "cancelled"):
        raise HTTPException(status_code=400, detail=f"任务已{task['status']}，无法取消")
    task["status"] = "cancelled"
    task["message"] = "用户已取消生成"
    return {"status": "cancelled", "message": "任务已取消"}


@router.delete("/projects/{project_id}")
async def delete_project(project_id: int):
    """删除PPT项目及其所有页面和生成的文件"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        project = db.query(PPTProject).filter(PPTProject.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 删除关联的slides
        db.query(PPTSlide).filter(PPTSlide.project_id == project_id).delete()

        # 删除生成的视频文件
        import glob
        ppt_output_dir = os.path.join(settings.GENERATED_DIR, "ppt")
        for f in glob.glob(os.path.join(ppt_output_dir, f"ppt_{project_id}_*")):
            try:
                os.remove(f)
            except:
                pass

        # 取消关联的正在运行的任务
        for tid, t in _ppt_tasks.items():
            if t.get("project_id") == project_id and t["status"] in ("pending", "processing"):
                t["status"] = "cancelled"
                t["message"] = "项目已删除"

        db.delete(project)
        db.commit()
        return {"status": "deleted", "message": f"项目 {project_id} 已删除"}
    finally:
        db.close()


@router.post("/projects/{project_id}/regenerate")
async def regenerate_project(project_id: int, request: Request):
    """重新生成PPT讲解视频（取消旧任务，创建新任务）"""
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        project = db.query(PPTProject).filter(PPTProject.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="项目不存在")

        # 取消旧的运行中任务
        for tid, t in _ppt_tasks.items():
            if t.get("project_id") == project_id and t["status"] in ("pending", "processing"):
                t["status"] = "cancelled"
                t["message"] = "被重新生成取代"

        # 重置项目状态
        project.status = "draft"
        db.query(PPTSlide).filter(PPTSlide.project_id == project_id).update({"status": "pending"})
        db.commit()

        # 重新触发generate
        body = await request.json()
        avatar_id = body.get("avatar_id", project.avatar_id or 1)
        voice_config = body.get("voice_config")
        layout_mode = body.get("layout_mode", "bottom_bar")
        position = body.get("digital_human_position", "bottom-center")
        size_ratio = body.get("digital_human_size", 0.25)
        transition = body.get("transition", "fade")
        model = body.get("model", "musetalk")

        avatar = db.query(Avatar).filter(Avatar.id == avatar_id).first()
        if not avatar:
            raise HTTPException(status_code=404, detail="数字人形象不存在")

        slides = db.query(PPTSlide).filter(
            PPTSlide.project_id == project_id,
            PPTSlide.narration_text.isnot(None),
            PPTSlide.narration_text != ""
        ).order_by(PPTSlide.slide_index).all()

        if not slides:
            raise HTTPException(status_code=400, detail="没有已编辑讲稿的页面")

        task_id = f"ppt_{project_id}_{uuid.uuid4().hex[:8]}"
        _ppt_tasks[task_id] = {
            "task_id": task_id,
            "project_id": project_id,
            "status": "pending",
            "message": f"重新生成，共 {len(slides)} 页",
            "progress": 0,
            "current_slide": 0,
            "total_slides": len(slides),
            "output_video": None,
        }

        asyncio.create_task(_generate_ppt_video_task(
            task_id, project_id, slides, avatar, None, model,
            layout_mode, position, size_ratio, transition
        ))

        return PPTGenerateResponse(
            task_id=task_id,
            project_id=project_id,
            status="pending",
            message=f"重新生成任务已创建，共 {len(slides)} 页",
        )
    finally:
        db.close()


# ===== 后台任务 =====

async def _generate_ppt_video_task(
    task_id: str,
    project_id: int,
    slides: list,
    avatar: Avatar,
    voice: Voice,
    model: str,
    layout_mode: str,
    position: str,
    size_ratio: float,
    transition: str,
    segment_duration: float = 30.0,
    bbox_shift: int = 0,
    musetalk_timeout_per_second: int = 30,
):
    """后台任务：逐页生成PPT讲解视频（串行执行，同时只允许一个）"""
    
    # 串行控制：等待其他PPT生成任务完成
    global _ppt_generation_running
    if _ppt_generation_running:
        task = _ppt_tasks[task_id]
        task["message"] = "等待其他PPT生成任务完成..."
        logger.info(f"[PPT-{project_id}] Waiting for other PPT generation to finish")
        while _ppt_generation_running:
            await asyncio.sleep(2)
    
    _ppt_generation_running = True
    try:
        await _generate_ppt_video_task_inner(
            task_id, project_id, slides, avatar, voice, model,
            layout_mode, position, size_ratio, transition,
            segment_duration, bbox_shift, musetalk_timeout_per_second
        )
    finally:
        _ppt_generation_running = False


async def _generate_ppt_video_task_inner(
    task_id: str,
    project_id: int,
    slides: list,
    avatar: Avatar,
    voice: Voice,
    model: str,
    layout_mode: str,
    position: str,
    size_ratio: float,
    transition: str,
    segment_duration: float = 30.0,
    bbox_shift: int = 0,
    musetalk_timeout_per_second: int = 30,
):
    """PPT视频生成实际逻辑 - 两阶段策略：
    
    Phase 1 (TTS): 释放MuseTalk GPU → 批量生成所有TTS音频 → 释放GPT-SoVITS GPU
    Phase 2 (LipSync): MuseTalk重新加载到GPU → 批量生成口型视频 → 合成
    
    避免GPU来回切换导致设备不匹配和超时。
    """
    task = _ppt_tasks[task_id]
    task["status"] = "processing"
    
    from app.database import SessionLocal
    db = SessionLocal()
    
    gpu_coord = GPUCoordinator.get_instance()
    
    try:
        # 解析形象图片路径
        image_path = avatar.transparent_image_path or avatar.styled_image_path or avatar.original_image_path
        if image_path:
            image_path = _resolve_path(image_path)
        if not image_path or not os.path.exists(image_path):
            image_path = _resolve_path(avatar.original_image_path) if avatar.original_image_path else ""
        if not image_path or not os.path.exists(image_path):
            task["status"] = "error"
            task["message"] = "数字人形象图片不存在"
            return
        
        output_dir = os.path.join(settings.GENERATED_DIR, "ppt")
        os.makedirs(output_dir, exist_ok=True)
        
        # 判断MuseTalk是否在远程机器上
        musetalk_url = getattr(settings, 'MUSETALK_API_URL', 'http://localhost:7861')
        is_remote_musetalk = not musetalk_url.startswith(('http://localhost', 'http://127.0.0.1'))
        if is_remote_musetalk:
            logger.info(f"[PPT-{project_id}] Remote MuseTalk at {musetalk_url}, GPU coordination disabled")
        
        # ========== Phase 1: 批量TTS ==========
        logger.info(f"[PPT-{project_id}] Phase 1: Batch TTS generation for {len(slides)} slides")
        task["message"] = f"Phase 1: 批量生成TTS音频 (0/{len(slides)})"
        
        # 远程MuseTalk不需要GPU协调；本地模式才需要释放MuseTalk GPU
        if not is_remote_musetalk:
            await gpu_coord.acquire_for_tts()
        
        audio_paths = {}  # slide_index -> audio_path
        tts_failed = []
        
        try:
            for i, slide in enumerate(slides):
                task["current_slide"] = i + 1
                task["message"] = f"Phase 1 (TTS): 生成第 {i + 1}/{len(slides)} 页音频..."
                
                try:
                    audio_filename = f"ppt_{project_id}_slide_{slide.slide_index}_{uuid.uuid4().hex[:8]}.wav"
                    audio_path = os.path.join(output_dir, audio_filename)
                    
                    if voice.source == "cloned" and voice.cloned_voice_id:
                        ref_audio = voice.reference_audio_path if voice.reference_audio_path else None
                        prompt_text = "参考音频"
                        if voice.tts_config and isinstance(voice.tts_config, dict):
                            prompt_text = voice.tts_config.get("prompt_text", "参考音频")
                        await tts_service.synthesize_with_cloned(
                            text=slide.narration_text,
                            voice_id=voice.cloned_voice_id,
                            output_path=audio_path,
                            ref_audio_path=ref_audio,
                            prompt_text=prompt_text,
                        )
                    else:
                        edge_voice = "zh-CN-XiaoxiaoNeural"
                        if voice.tts_config and isinstance(voice.tts_config, dict):
                            edge_voice = voice.tts_config.get("edge_voice_name", "zh-CN-XiaoxiaoNeural")
                        await tts_service.synthesize_with_edge(
                            text=slide.narration_text,
                            output_path=audio_path,
                            voice_name=edge_voice,
                        )
                    
                    # 更新数据库
                    db_slide = db.query(PPTSlide).filter(PPTSlide.id == slide.id).first()
                    if db_slide:
                        db_slide.audio_path = audio_path
                        db.commit()
                    
                    audio_paths[slide.slide_index] = audio_path
                    logger.info(f"[PPT-{project_id}] TTS slide {slide.slide_index} OK: {audio_path}")
                    
                except Exception as e:
                    logger.error(f"[PPT-{project_id}] TTS slide {slide.slide_index} failed: {e}")
                    tts_failed.append(slide.slide_index)
        finally:
            # 释放GPT-SoVITS GPU
            await gpu_coord.release_from_tts()
        
        if not audio_paths:
            task["status"] = "error"
            task["message"] = "所有TTS音频生成失败"
            return
        
        logger.info(f"[PPT-{project_id}] Phase 1 complete: {len(audio_paths)} audio files, {len(tts_failed)} failed")
        
        # ========== Phase 2: 批量MuseTalk口型视频 ==========
        logger.info(f"[PPT-{project_id}] Phase 2: Batch MuseTalk lip sync for {len(audio_paths)} slides")
        task["message"] = f"Phase 2: 批量生成口型视频 (0/{len(audio_paths)})"
        
        # 远程MuseTalk不需要GPU协调（机器B独占GPU）
        if not is_remote_musetalk:
            # 本地模式：需要GPU协调
            lipsync_ready = await gpu_coord.acquire_for_lipsync()
            if not lipsync_ready:
                task["status"] = "error"
                task["message"] = "MuseTalk GPU加载失败，无法生成口型视频"
                return
        else:
            logger.info(f"[PPT-{project_id}] Remote MuseTalk at {musetalk_url}, skipping GPU coordination")
            # 远程模式：检查MuseTalk健康状态即可
            try:
                import httpx
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(f"{musetalk_url}/health")
                    if resp.status_code != 200 or not resp.json().get("models_loaded"):
                        task["status"] = "error"
                        task["message"] = "远程MuseTalk服务不可用"
                        return
            except Exception as e:
                task["status"] = "error"
                task["message"] = f"远程MuseTalk连接失败: {e}"
                return
        
        video_paths = {}  # slide_index -> video_path
        lipsync_failed = []
        
        try:
            for i, slide in enumerate(slides):
                if slide.slide_index not in audio_paths:
                    continue  # TTS失败的跳过
                
                task["current_slide"] = i + 1
                task["message"] = f"Phase 2 (MuseTalk): 生成第 {i + 1}/{len(slides)} 页口型视频..."
                
                try:
                    audio_path = audio_paths[slide.slide_index]
                    video_filename = f"ppt_{project_id}_slide_{slide.slide_index}_{uuid.uuid4().hex[:8]}.mp4"
                    video_path = os.path.join(output_dir, video_filename)
                    
                    # 检查音频时长，超过25秒则分段处理
                    audio_duration = _get_audio_duration(audio_path)
                    if audio_duration > 25.0:
                        logger.info(f"[PPT] Slide {slide.slide_index}: audio {audio_duration:.1f}s > 25s, splitting")
                        video_path = await _generate_segmented_musetalk(
                            image_path=image_path,
                            audio_path=audio_path,
                            output_path=video_path,
                            segment_duration=segment_duration,
                            output_dir=output_dir,
                            project_id=project_id,
                            slide_index=slide.slide_index,
                            bbox_shift=bbox_shift,
                            musetalk_timeout_per_second=musetalk_timeout_per_second,
                        )
                    else:
                        await lip_sync_service.generate_lip_sync_video(
                            image_path=image_path,
                            audio_path=audio_path,
                            output_path=video_path,
                            model=model,
                        )
                    
                    video_paths[slide.slide_index] = video_path
                    logger.info(f"[PPT-{project_id}] MuseTalk slide {slide.slide_index} OK")
                    
                    # 智能重启：每5次推理后重启MuseTalk防止GPU内存碎片化
                    await lip_sync_service.maybe_restart_if_needed()
                    
                except Exception as e:
                    logger.error(f"[PPT-{project_id}] MuseTalk slide {slide.slide_index} failed: {e}")
                    lipsync_failed.append(slide.slide_index)
                    db_slide = db.query(PPTSlide).filter(PPTSlide.id == slide.id).first()
                    if db_slide:
                        db_slide.status = "error"
                        db.commit()
        finally:
            # 口型同步完成，释放GPU
            await gpu_coord.release_from_lipsync()
        
        if not video_paths:
            task["status"] = "error"
            task["message"] = "所有口型视频生成失败"
            return
        
        logger.info(f"[PPT-{project_id}] Phase 2 complete: {len(video_paths)} videos, {len(lipsync_failed)} failed")
        
        # ========== Phase 3: 视频合成（无需GPU） ==========
        task["message"] = f"Phase 3: 合成视频 (0/{len(video_paths)})"
        composed_videos = []
        
        for i, slide in enumerate(slides):
            if slide.slide_index not in video_paths:
                continue
            
            task["current_slide"] = i + 1
            task["message"] = f"Phase 3: 合成第 {i + 1}/{len(slides)} 页视频..."
            
            try:
                video_path = video_paths[slide.slide_index]
                slide_image_path = _resolve_path(slide.slide_image_path) if slide.slide_image_path else None
                
                if slide_image_path and os.path.exists(slide_image_path):
                    composed_filename = f"ppt_{project_id}_composed_{slide.slide_index}_{uuid.uuid4().hex[:8]}.mp4"
                    composed_path = os.path.join(output_dir, composed_filename)
                    
                    # 获取下一页的数字人位置（用于过渡动画）
                    next_pos = None
                    if i + 1 < len(slides):
                        next_slide = slides[i + 1]
                        next_pos = getattr(next_slide, 'digital_human_position', None) or None
                    
                    compose_slide_video(
                        slide_image_path=slide_image_path,
                        human_video_path=video_path,
                        output_path=composed_path,
                        layout_mode=layout_mode,
                        position=position,
                        next_position=next_pos,
                        size_ratio=size_ratio,
                        bar_ratio=1/6,
                    )
                    composed_videos.append(composed_path)
                else:
                    # 没有PPT图片，直接用口型视频
                    composed_videos.append(video_path)
                
                db_slide = db.query(PPTSlide).filter(PPTSlide.id == slide.id).first()
                if db_slide:
                    db_slide.video_path = video_path
                    db_slide.status = "done"
                    db.commit()
                    
            except Exception as e:
                logger.error(f"[PPT] Compose slide {slide.slide_index} failed: {e}")
                db_slide = db.query(PPTSlide).filter(PPTSlide.id == slide.id).first()
                if db_slide:
                    db_slide.status = "error"
                    db.commit()
        
        # 4. 拼接所有页面视频
        if composed_videos:
            final_filename = f"ppt_{project_id}_final_{uuid.uuid4().hex[:8]}.mp4"
            final_path = os.path.join(output_dir, final_filename)
            
            if len(composed_videos) == 1:
                shutil.copy2(composed_videos[0], final_path)
            else:
                compose_full_ppt_video(
                    slide_composed_videos=composed_videos,
                    output_path=final_path,
                    transition=transition,
                )
            
            task["output_video"] = _path_to_url(final_path)
            task["status"] = "completed"
            task["message"] = f"PPT讲解视频生成完成，共 {len(composed_videos)} 页"
            
            # 更新数据库
            project = db.query(PPTProject).filter(PPTProject.id == project_id).first()
            if project:
                project.output_video_path = _path_to_url(final_path)
                project.status = "completed"
                db.commit()
        else:
            task["status"] = "error"
            task["message"] = "没有成功生成任何页面视频"
    
    except Exception as e:
        task["status"] = "error"
        task["message"] = f"生成失败: {str(e)}"
        logger.error(f"[PPT] Generate task failed: {e}")
    
    finally:
        db.close()


async def _generate_segmented_musetalk(
    image_path: str,
    audio_path: str,
    output_path: str,
    segment_duration: float = 30.0,
    output_dir: str = "",
    project_id: int = 0,
    slide_index: int = 0,
    bbox_shift: int = 0,
    musetalk_timeout_per_second: int = 30,
) -> str:
    """
    将长音频分段后逐段调用MuseTalk，再拼接为完整视频。
    避免MuseTalk处理长音频时GPU OOM。
    """
    try:
        import imageio_ffmpeg
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        ffmpeg_exe = "ffmpeg"
    
    # 1. 获取音频总时长
    total_duration = _get_audio_duration(audio_path)
    num_segments = max(1, int(total_duration / segment_duration) + (1 if total_duration % segment_duration > 0.5 else 0))
    logger.info(f"[PPT] Segmented MuseTalk: {total_duration:.1f}s -> {num_segments} segments")
    
    # 2. 分段切割音频
    segment_audio_paths = []
    for i in range(num_segments):
        start = i * segment_duration
        seg_filename = f"ppt_{project_id}_slide_{slide_index}_seg{i}_{uuid.uuid4().hex[:6]}.wav"
        seg_path = os.path.join(output_dir, seg_filename)
        
        cmd = [
            ffmpeg_exe, "-y",
            "-i", audio_path,
            "-ss", str(start),
            "-t", str(segment_duration),
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            seg_path
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
            if os.path.exists(seg_path) and os.path.getsize(seg_path) > 1000:
                segment_audio_paths.append(seg_path)
            else:
                logger.warning(f"[PPT] Segment {i} too small, skipping")
        except Exception as e:
            logger.warning(f"[PPT] Segment {i} cut failed: {e}")
    
    if not segment_audio_paths:
        logger.warning("[PPT] No audio segments, falling back to full audio")
        await LipSyncService().generate_lip_sync_video(
            image_path=image_path,
            audio_path=audio_path,
            output_path=output_path,
            model="musetalk",
        )
        return output_path


# ==================== 分段管理API ====================

class SlideGenerateRequest(BaseModel):
    avatar_id: int
    voice_id: Optional[int] = None
    voice_config: Optional[dict] = None
    layout_mode: str = "pip"
    digital_human_position: str = "bottom-right"
    digital_human_size: float = 0.25
    segment_duration: float = 30.0
    bbox_shift: int = 0
    musetalk_timeout_per_second: int = 30


class MergeRequest(BaseModel):
    slide_ids: List[int] = []
    transition: str = "fade"


# 单页生成任务存储
_slide_tasks = {}


@router.post("/projects/{project_id}/slides/{slide_id}/generate")
async def generate_single_slide(
    project_id: int,
    slide_id: int,
    request: SlideGenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """生成单页PPT视频"""
    slide = db.query(PPTSlide).filter(
        PPTSlide.id == slide_id,
        PPTSlide.project_id == project_id
    ).first()
    if not slide:
        raise HTTPException(status_code=404, detail="页面不存在")

    project = db.query(PPTProject).filter(PPTProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    avatar = db.query(Avatar).filter(Avatar.id == request.avatar_id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="数字人形象不存在")

    voice = None
    if request.voice_id:
        voice = db.query(Voice).filter(Voice.id == request.voice_id).first()

    task_id = str(uuid.uuid4())[:12]
    _slide_tasks[task_id] = {
        "task_id": task_id,
        "project_id": project_id,
        "slide_id": slide_id,
        "slide_index": slide.slide_index,
        "status": "pending",
        "message": "等待开始...",
        "progress": 0,
        "current_slide": 1,
        "total_slides": 1,
    }

    # 更新slide状态
    slide.status = "generating"
    db.commit()

    # 在线程中运行
    import threading
    _avatar_id = avatar.id
    _voice_id = voice.id if voice else None
    _layout = request.layout_mode
    _pos = request.digital_human_position
    _size = request.digital_human_size
    _seg_dur = request.segment_duration
    _bbox = request.bbox_shift
    _timeout_ps = request.musetalk_timeout_per_second
    _narration = slide.narration_text or ""
    _slide_index = slide.slide_index
    _slide_id = slide_id

    def _run_slide_task():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_generate_single_slide_task(
                task_id, project_id, _slide_id, _slide_index, _narration,
                _avatar_id, _voice_id, _layout, _pos, _size,
                _seg_dur, _bbox, _timeout_ps
            ))
        except Exception as e:
            logger.error(f"[PPT] Slide task error: {e}")
            _slide_tasks[task_id]["status"] = "error"
            _slide_tasks[task_id]["message"] = str(e)
        finally:
            loop.close()

    thread = threading.Thread(target=_run_slide_task, daemon=True)
    thread.start()

    return {"task_id": task_id, "status": "pending", "message": f"正在生成第{_slide_index + 1}页"}


async def _generate_single_slide_task(
    task_id, project_id, slide_id, slide_index, narration,
    avatar_id, voice_id, layout_mode, position, size_ratio,
    segment_duration, bbox_shift, musetalk_timeout_per_second
):
    """单页视频生成任务"""
    from app.database import SessionLocal
    thread_db = SessionLocal()

    try:
        task = _slide_tasks[task_id]
        task["status"] = "processing"
        task["message"] = "正在生成语音..."

        avatar = thread_db.query(Avatar).filter(Avatar.id == avatar_id).first()
        voice = thread_db.query(Voice).filter(Voice.id == voice_id).first() if voice_id else None
        slide = thread_db.query(PPTSlide).filter(PPTSlide.id == slide_id).first()

        output_dir = os.path.join(settings.GENERATED_DIR, "ppt")
        os.makedirs(output_dir, exist_ok=True)

        # 1. TTS
        tts = TTSService()
        audio_filename = f"ppt_{project_id}_slide_{slide_index}_{uuid.uuid4().hex[:8]}.wav"
        audio_path = os.path.join(output_dir, audio_filename)

        if voice and voice.source == "cloned":
            tts_result = await tts.generate_with_gpt_sovits(narration, voice, audio_path)
        else:
            edge_voice = "zh-CN-XiaoxiaoNeural"
            if voice and voice.source == "blended":
                edge_voice = voice.edge_tts_voice or edge_voice
            tts_result = await tts.generate_with_edge_tts(narration, edge_voice, audio_path)

        if not tts_result or not os.path.exists(audio_path):
            task["status"] = "error"
            task["message"] = "TTS语音生成失败"
            slide.status = "error"
            thread_db.commit()
            return

        task["message"] = "正在生成口型视频..."

        # 2. MuseTalk
        image_path = avatar.transparent_image_path or avatar.styled_image_path or avatar.original_image_path
        if image_path:
            image_path = _resolve_path(image_path)
        if not image_path or not os.path.exists(image_path):
            image_path = _resolve_path(avatar.original_image_path) if avatar.original_image_path else ""

        video_filename = f"ppt_{project_id}_slide_{slide_index}_{uuid.uuid4().hex[:8]}.mp4"
        video_path = os.path.join(output_dir, video_filename)

        video_result = await _generate_segmented_musetalk(
            image_path=image_path,
            audio_path=audio_path,
            output_path=video_path,
            segment_duration=segment_duration,
            output_dir=output_dir,
            project_id=project_id,
            slide_index=slide_index,
            bbox_shift=bbox_shift,
            musetalk_timeout_per_second=musetalk_timeout_per_second,
        )

        if not video_result or not os.path.exists(video_result):
            task["status"] = "error"
            task["message"] = "MuseTalk口型视频生成失败"
            slide.status = "error"
            thread_db.commit()
            return

        task["message"] = "正在合成画中画..."

        # 3. 合成画中画
        slide_image = _resolve_path(slide.slide_image_path) if slide.slide_image_path else ""
        composed_filename = f"ppt_{project_id}_composed_{slide_index}_{uuid.uuid4().hex[:8]}.mp4"
        composed_path = os.path.join(output_dir, composed_filename)

        composed = compose_slide_video(
            slide_image_path=slide_image,
            avatar_video_path=video_result,
            output_path=composed_path,
            layout_mode=layout_mode,
            position=position,
            size_ratio=size_ratio,
        )

        if composed and os.path.exists(composed):
            slide.composed_video_path = composed
            slide.duration = _get_audio_duration(audio_path)
            slide.status = "completed"
            thread_db.commit()
            task["status"] = "completed"
            task["message"] = "生成完成"
            task["video_url"] = f"/data/generated/ppt/{composed_filename}"
        else:
            task["status"] = "error"
            task["message"] = "视频合成失败"
            slide.status = "error"
            thread_db.commit()

    except Exception as e:
        logger.error(f"[PPT] Single slide task error: {e}")
        task = _slide_tasks.get(task_id)
        if task:
            task["status"] = "error"
            task["message"] = str(e)
        slide = thread_db.query(PPTSlide).filter(PPTSlide.id == slide_id).first()
        if slide:
            slide.status = "error"
            thread_db.commit()
    finally:
        thread_db.close()


@router.get("/projects/{project_id}/slides/{slide_id}/status")
async def get_slide_status(project_id: int, slide_id: int):
    """查询单页生成状态"""
    for task in _slide_tasks.values():
        if task.get("slide_id") == slide_id and task.get("project_id") == project_id:
            return task
    return {"status": "idle", "message": "无生成任务"}


@router.post("/projects/{project_id}/merge")
async def merge_selected_slides(
    project_id: int,
    request: MergeRequest,
    db: Session = Depends(get_db)
):
    """合成选中页视频"""
    project = db.query(PPTProject).filter(PPTProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    if request.slide_ids:
        slides = db.query(PPTSlide).filter(
            PPTSlide.project_id == project_id,
            PPTSlide.id.in_(request.slide_ids),
            PPTSlide.status == "completed"
        ).order_by(PPTSlide.slide_index).all()
    else:
        slides = db.query(PPTSlide).filter(
            PPTSlide.project_id == project_id,
            PPTSlide.status == "completed"
        ).order_by(PPTSlide.slide_index).all()

    if not slides:
        raise HTTPException(status_code=400, detail="没有已完成的页面可合成")

    output_dir = os.path.join(settings.GENERATED_DIR, "ppt")
    os.makedirs(output_dir, exist_ok=True)

    # 收集已合成视频
    video_paths = []
    for slide in slides:
        if slide.composed_video_path and os.path.exists(slide.composed_video_path):
            video_paths.append(slide.composed_video_path)

    if not video_paths:
        raise HTTPException(status_code=400, detail="没有找到已合成的视频文件")

    # 拼接
    final_filename = f"ppt_{project_id}_final_{uuid.uuid4().hex[:8]}.mp4"
    final_path = os.path.join(output_dir, final_filename)

    try:
        from moviepy import VideoFileClip, concatenate_videoclips
        clips = [VideoFileClip(vp) for vp in video_paths]
        final_clip = concatenate_videoclips(clips, method="compose")
        final_clip.write_videofile(final_path, codec="libx264", audio_codec="aac", verbose=False, logger=None)
        for clip in clips:
            clip.close()
        final_clip.close()

        # 更新项目
        project.status = "completed"
        project.output_video_path = f"/data/generated/ppt/{final_filename}"
        db.commit()

        return {
            "success": True,
            "video_url": f"/data/generated/ppt/{final_filename}",
            "slide_count": len(video_paths),
            "message": f"已合成{len(video_paths)}页视频"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"合成失败: {str(e)}")


@router.get("/projects/{project_id}/slides/{slide_id}/video")
async def get_slide_video(project_id: int, slide_id: int, db: Session = Depends(get_db)):
    """获取单页视频文件路径"""
    slide = db.query(PPTSlide).filter(
        PPTSlide.id == slide_id,
        PPTSlide.project_id == project_id
    ).first()
    if not slide:
        raise HTTPException(status_code=404, detail="页面不存在")
    if not slide.composed_video_path:
        raise HTTPException(status_code=404, detail="该页视频尚未生成")
    return {"video_url": slide.composed_video_path.replace("\\", "/")}


def _get_audio_duration(audio_path: str) -> float:
    """获取音频时长"""
    try:
        from moviepy import AudioFileClip
        clip = AudioFileClip(audio_path)
        dur = clip.duration
        clip.close()
        return dur
    except:
        return 0.0


async def _generate_segmented_musetalk_tail(
    segment_audio_paths, image_path, output_dir, project_id, slide_index,
    output_path, bbox_shift, musetalk_timeout_per_second, ffmpeg_exe
):
    """同步部分：逐段生成MuseTalk视频并拼接（在线程中调用）"""
    # 3. 逐段生成MuseTalk视频
    segment_video_paths = []
    lip_sync = LipSyncService()
    for i, seg_audio in enumerate(segment_audio_paths):
        seg_video_filename = f"ppt_{project_id}_slide_{slide_index}_seg{i}_{uuid.uuid4().hex[:6]}.mp4"
        seg_video_path = os.path.join(output_dir, seg_video_filename)
        
        try:
            result = await lip_sync.generate_lip_sync_video(
                image_path=image_path,
                audio_path=seg_audio,
                output_path=seg_video_path,
                model="musetalk",
                bbox_shift=bbox_shift,
                musetalk_timeout_per_second=musetalk_timeout_per_second,
            )
            if result and os.path.exists(result):
                segment_video_paths.append(result)
                logger.info(f"[PPT] Segment {i} video generated: {result}")
            else:
                logger.warning(f"[PPT] Segment {i} video failed")
        except Exception as e:
            logger.warning(f"[PPT] Segment {i} MuseTalk error: {e}")
        
        # 清理分段音频
        try:
            os.remove(seg_audio)
        except:
            pass
    
    # 4. 拼接分段视频
    if len(segment_video_paths) == 0:
        raise RuntimeError("所有分段MuseTalk视频生成失败")
    elif len(segment_video_paths) == 1:
        shutil.copy2(segment_video_paths[0], output_path)
    else:
        # 用ffmpeg拼接
        concat_file = os.path.join(output_dir, f"concat_{project_id}_{slide_index}.txt")
        with open(concat_file, "w") as f:
            for vp in segment_video_paths:
                f.write(f"file '{vp}'\n")
        
        cmd = [
            ffmpeg_exe, "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, timeout=60)
        
        # 清理
        try:
            os.remove(concat_file)
            for vp in segment_video_paths:
                if os.path.exists(vp):
                    os.remove(vp)
        except:
            pass
    
    return output_path
