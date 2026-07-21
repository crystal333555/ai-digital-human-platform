"""LivePortrait口型同步服务封装"""
import os, httpx, logging, asyncio, uuid, shutil
from typing import Optional

logger = logging.getLogger(__name__)
LIVEPORTRAIT_URL = os.environ.get("LIVEPORTRAIT_API_URL", "http://192.168.100.3:7863")

class LivePortraitService:
    def __init__(self):
        self.api_url = LIVEPORTRAIT_URL
        self._is_remote = not self.api_url.startswith(("http://localhost", "http://127.0.0.1"))
        self.file_server_url = self.api_url.replace(":7863", ":7862") if self._is_remote else None

    async def health_check(self):
        try:
            async with httpx.AsyncClient(timeout=10.0) as c:
                r = await c.get(f"{self.api_url}/health")
                return r.status_code == 200 and r.json().get("pipeline_loaded", False)
        except:
            return False

    async def generate_video(self, image_path, audio_path, output_path, timeout=600):
        try:
            task_id = uuid.uuid4().hex[:8]
            async with httpx.AsyncClient(timeout=timeout) as c:
                with open(image_path, "rb") as img_f, open(audio_path, "rb") as audio_f:
                    r = await c.post(
                        f"{self.api_url}/generate",
                        files={
                            "image": (f"lp_{task_id}.jpg", img_f, "image/jpeg"),
                            "audio": (f"lp_{task_id}.wav", audio_f, "audio/wav"),
                        },
                        data={"output_dir": r"D:\MuseTalkShare"},
                    )
                if r.status_code == 200:
                    result = r.json()
                    if result.get("success"):
                        remote_path = result.get("video_path")
                        if remote_path and self._is_remote:
                            async with httpx.AsyncClient(timeout=120.0) as dl:
                                rp = await dl.post(
                                    f"{self.file_server_url}/download",
                                    json={"path": remote_path},
                                )
                                if rp.status_code == 200:
                                    with open(output_path, "wb") as f:
                                        f.write(rp.content)
                                    return output_path
                        elif remote_path and os.path.exists(remote_path):
                            shutil.move(remote_path, output_path)
                            return output_path
            logger.error(f"LivePortrait failed: {r.status_code}")
            return None
        except Exception as e:
            logger.error(f"LivePortrait error: {e}")
            return None
