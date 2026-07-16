import os
import traceback
import asyncio
import threading
import logging
import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.config import settings
from app.database import init_db
from app.routers import avatar, voice, chat, tts, voice_lib, face_mesh, speech, ppt

logger = logging.getLogger(__name__)

# ============ 服务健康检查守护 ============

_service_status = {
    "musetalk": {"status": "unknown", "last_check": None, "fail_count": 0, "models_loaded": False},
    "gpt_sovits": {"status": "unknown", "last_check": None, "fail_count": 0, "models_loaded": False},
}

MUSETALK_URL = os.environ.get("MUSETALK_API_URL", "http://localhost:7861")
GPT_SOVITS_URL = os.environ.get("GPT_SOVITS_API_URL", "http://localhost:9880")
HEALTH_CHECK_INTERVAL = 30  # 秒
MAX_FAIL_BEFORE_RESTART = 3  # 连续失败次数后触发重启


def _check_services_sync():
    """同步检查服务健康状态（在守护线程中调用）"""
    import datetime
    
    # 检查MuseTalk
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{MUSETALK_URL}/health")
            if resp.status_code == 200:
                data = resp.json()
                _service_status["musetalk"]["status"] = "online"
                _service_status["musetalk"]["models_loaded"] = data.get("models_loaded", False)
                _service_status["musetalk"]["fail_count"] = 0
            else:
                _service_status["musetalk"]["status"] = "degraded"
                _service_status["musetalk"]["fail_count"] += 1
    except Exception:
        _service_status["musetalk"]["status"] = "offline"
        _service_status["musetalk"]["fail_count"] += 1
    
    _service_status["musetalk"]["last_check"] = datetime.datetime.now().isoformat()
    
    # 检查GPT-SoVITS
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{GPT_SOVITS_URL}/health")
            if resp.status_code == 200:
                _service_status["gpt_sovits"]["status"] = "online"
                _service_status["gpt_sovits"]["fail_count"] = 0
            else:
                _service_status["gpt_sovits"]["status"] = "degraded"
                _service_status["gpt_sovits"]["fail_count"] += 1
    except Exception:
        _service_status["gpt_sovits"]["status"] = "offline"
        _service_status["gpt_sovits"]["fail_count"] += 1
    
    _service_status["gpt_sovits"]["last_check"] = datetime.datetime.now().isoformat()
    
    # MuseTalk连续失败超过阈值，尝试自动重启
    if _service_status["musetalk"]["fail_count"] >= MAX_FAIL_BEFORE_RESTART:
        logger.warning(f"[HealthGuard] MuseTalk failed {_service_status['musetalk']['fail_count']} times, attempting restart...")
        _restart_musetalk_sync()


def _restart_musetalk_sync():
    """同步重启MuseTalk进程"""
    import subprocess
    try:
        # 杀掉端口7861上的进程
        net_result = subprocess.run(['netstat', '-ano'], capture_output=True, text=True, timeout=5)
        for line in net_result.stdout.split('\n'):
            if ':7861' in line and 'LISTEN' in line:
                parts = line.split()
                pid = parts[-1].strip()
                if pid.isdigit():
                    subprocess.run(['taskkill', '/f', '/pid', pid], capture_output=True, timeout=5)
                    logger.info(f"[HealthGuard] Killed MuseTalk process: {pid}")
        
        import time
        time.sleep(5)
        
        # 重新启动
        musetalk_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "MuseTalk"
        )
        conda_exe = r"C:\Users\yj821\miniconda3\Scripts\conda.exe"
        
        subprocess.Popen(
            f'pushd "{musetalk_dir}" && {conda_exe} run -n musetalk python musetalk_api_server.py',
            shell=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        
        logger.info("[HealthGuard] MuseTalk restart initiated")
        _service_status["musetalk"]["fail_count"] = 0
        
    except Exception as e:
        logger.error(f"[HealthGuard] MuseTalk restart failed: {e}")


def _health_guard_thread():
    """守护线程：定期检查服务健康状态"""
    import time
    logger.info("[HealthGuard] Starting service health monitor...")
    time.sleep(15)  # 启动后等15秒再开始检查
    
    while True:
        try:
            _check_services_sync()
        except Exception as e:
            logger.error(f"[HealthGuard] Check error: {e}")
        time.sleep(HEALTH_CHECK_INTERVAL)


# 计算项目根目录下的 uploads 绝对路径（小文件：头像、音色样本）
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
UPLOADS_DIR = os.path.join(_PROJECT_ROOT, "uploads")

# D盘大文件目录（生成视频、PPT文件等）
DATA_DIR = settings.GENERATED_DIR  # D:\AI_Avatar_Data\generated

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化目录
    os.makedirs(os.path.join(UPLOADS_DIR, "avatars"), exist_ok=True)
    os.makedirs(os.path.join(UPLOADS_DIR, "voices"), exist_ok=True)
    # D盘大文件目录
    os.makedirs(os.path.join(DATA_DIR, "speech"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "ppt"), exist_ok=True)
    os.makedirs(settings.PPT_DIR, exist_ok=True)
    os.makedirs(settings.MODELS_DIR, exist_ok=True)
    init_db()
    
    # 启动服务健康检查守护线程
    guard = threading.Thread(target=_health_guard_thread, daemon=True, name="HealthGuard")
    guard.start()
    logger.info("[HealthGuard] Service health monitor thread started")
    
    yield
    # 关闭时清理
    pass

app = FastAPI(
    title=settings.APP_NAME,
    description="AI数字人平台 - 支持2D/3D数字人生成与语音对话",
    version="1.0.0",
    lifespan=lifespan
)

# 全局异常处理器，打印详细错误
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_detail = traceback.format_exc()
    print(f"[GLOBAL ERROR] {request.url}: {error_detail}")
    return JSONResponse(status_code=500, content={"detail": str(exc), "traceback": error_detail})

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载C盘小文件（头像、音色）
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# 挂载D盘大文件（生成视频、PPT文件）
# /data/generated/speech/xxx.mp4 -> D:\AI_Avatar_Data\generated\speech\xxx.mp4
os.makedirs(DATA_DIR, exist_ok=True)
app.mount("/data/generated", StaticFiles(directory=DATA_DIR), name="generated")

# /data/ppt/xxx.pptx -> D:\AI_Avatar_Data\ppt\xxx.pptx
os.makedirs(settings.PPT_DIR, exist_ok=True)
app.mount("/data/ppt", StaticFiles(directory=settings.PPT_DIR), name="ppt_data")

app.include_router(avatar.router, prefix=settings.API_PREFIX, tags=["形象管理"])
app.include_router(voice.router, prefix=settings.API_PREFIX, tags=["音色管理"])
app.include_router(voice_lib.router, prefix=settings.API_PREFIX, tags=["音色库"])
app.include_router(chat.router, prefix=settings.API_PREFIX, tags=["对话"])
app.include_router(tts.router, prefix=settings.API_PREFIX, tags=["语音合成"])
app.include_router(face_mesh.router, prefix=settings.API_PREFIX, tags=["3D人脸重建"])
app.include_router(speech.router, prefix=settings.API_PREFIX + "/speech", tags=["演讲视频"])
app.include_router(ppt.router, prefix=settings.API_PREFIX + "/ppt", tags=["PPT讲解"])

@app.get("/")
async def root():
    return {
        "message": "AI Avatar Platform API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/api/v1/system/services")
async def get_service_status():
    """获取MuseTalk和GPT-SoVITS服务状态"""
    return {
        "musetalk": _service_status["musetalk"],
        "gpt_sovits": _service_status["gpt_sovits"],
    }


@app.post("/api/v1/system/warmup")
async def warmup_services():
    """预热MuseTalk（发送一次推理请求让模型加载到GPU）"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # 检查MuseTalk是否已加载
            health = await client.get(f"{MUSETALK_URL}/health")
            if health.status_code == 200:
                data = health.json()
                if data.get("models_loaded"):
                    return {"status": "already_warm", "message": "MuseTalk模型已加载"}
            
            # 触发模型加载
            reload = await client.post(f"{MUSETALK_URL}/reload_gpu", timeout=30.0)
            if reload.status_code == 200:
                return {"status": "warming_up", "message": "MuseTalk模型正在加载到GPU"}
            else:
                return {"status": "error", "message": f"MuseTalk reload_gpu failed: {reload.status_code}"}
    except Exception as e:
        return {"status": "error", "message": f"MuseTalk预热失败: {str(e)}"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ai-avatar-platform"}
