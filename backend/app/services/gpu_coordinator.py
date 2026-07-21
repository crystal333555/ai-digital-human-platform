"""
GPU协调调度器 - 管理GPT-SoVITS和MuseTalk的GPU显存使用

核心策略：两阶段串行调度
  Phase 1 (TTS): 释放MuseTalk GPU → GPT-SoVITS生成所有音频 → 等待GPU释放
  Phase 2 (LipSync): MuseTalk重新加载到GPU → 逐段生成口型视频 → 保持热加载

避免两个模型同时占用GPU导致OOM，也避免静默降级到静态图片。
"""

import asyncio
import logging
import httpx
import os

logger = logging.getLogger(__name__)

# 协调器单例
_instance = None


class GPUCoordinator:
    """GPU显存协调调度器"""
    
    def __init__(self):
        self.musetalk_url = os.environ.get("MUSETALK_API_URL", "http://localhost:7861")
        self.gpt_sovits_url = os.environ.get("GPT_SOVITS_API_URL", "http://localhost:9880")
        self._lock = None  # 延迟初始化
        self._phase = "idle"  # idle | tts | lipsync
    
    @classmethod
    def get_instance(cls):
        global _instance
        if _instance is None:
            _instance = cls()
        return _instance
    
    async def acquire_for_tts(self) -> bool:
        """申请GPU给GPT-SoVITS（TTS阶段）
        
        1. 释放MuseTalk模型到CPU
        2. 将GPT-SoVITS模型加载回GPU（如果GPT-SoVITS在运行）
        3. 标记TTS阶段开始
        """
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            logger.info("[GPU-Coord] Acquiring GPU for TTS (GPT-SoVITS)...")
            self._phase = "tts"
            
            # 释放MuseTalk GPU
            released = await self._release_musetalk()
            if released:
                await asyncio.sleep(3)
            
            # 将GPT-SoVITS模型加载回GPU（仅在GPT-SoVITS运行时）
            gpt_sovits_available = await self._check_gpt_sovits_health()
            if gpt_sovits_available:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        resp = await client.post(f"{self.gpt_sovits_url}/reload_gpu")
                        if resp.status_code == 200:
                            logger.info(f"[GPU-Coord] GPT-SoVITS reloaded to GPU: {resp.json()}")
                        else:
                            logger.warning(f"[GPU-Coord] GPT-SoVITS reload_gpu failed: {resp.status_code}")
                except Exception as e:
                    logger.warning(f"[GPU-Coord] GPT-SoVITS reload_gpu error: {e}")
            else:
                logger.info("[GPU-Coord] GPT-SoVITS not running, skipping reload")
            
            await asyncio.sleep(2)
            logger.info(f"[GPU-Coord] GPU acquired for TTS (musetalk_released={released}, gptsovits_available={gpt_sovits_available})")
            return True
    
    async def release_from_tts(self) -> bool:
        """TTS阶段完成，释放GPU给MuseTalk
        
        1. 调用GPT-SoVITS的/release_gpu将模型移到CPU
        2. 等待GPU显存释放
        3. 标记TTS阶段结束
        """
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            logger.info("[GPU-Coord] Releasing GPU from TTS...")
            self._phase = "idle"
            
            # 主动调用GPT-SoVITS释放GPU（仅在运行时）
            gpt_sovits_available = await self._check_gpt_sovits_health()
            if gpt_sovits_available:
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        resp = await client.post(f"{self.gpt_sovits_url}/release_gpu")
                        if resp.status_code == 200:
                            logger.info(f"[GPU-Coord] GPT-SoVITS GPU released: {resp.json()}")
                        else:
                            logger.warning(f"[GPU-Coord] GPT-SoVITS release_gpu failed: {resp.status_code}")
                except Exception as e:
                    logger.warning(f"[GPU-Coord] GPT-SoVITS release_gpu error: {e}")
            else:
                logger.info("[GPU-Coord] GPT-SoVITS not running, skipping release")
            
            # 等待CUDA缓存清理
            await asyncio.sleep(3)
            
            logger.info("[GPU-Coord] GPU released from TTS")
            return True
    
    async def acquire_for_lipsync(self) -> bool:
        """申请GPU给MuseTalk（口型同步阶段）
        
        1. 确保GPT-SoVITS不再占用GPU
        2. 将MuseTalk模型重新加载到GPU
        3. 验证MuseTalk模型加载成功
        4. 标记口型同步阶段开始
        """
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            logger.info("[GPU-Coord] Acquiring GPU for LipSync (MuseTalk)...")
            self._phase = "lipsync"
            
            # 重新加载MuseTalk到GPU
            reloaded = await self._reload_musetalk()
            if not reloaded:
                logger.error("[GPU-Coord] Failed to reload MuseTalk to GPU!")
                return False
            
            # 验证模型加载
            for attempt in range(3):
                health = await self._check_musetalk_health()
                if health.get("models_loaded"):
                    logger.info("[GPU-Coord] MuseTalk models loaded, GPU ready for LipSync")
                    return True
                logger.warning(f"[GPU-Coord] MuseTalk models not loaded yet, waiting... (attempt {attempt+1}/3)")
                await asyncio.sleep(10)
            
            logger.error("[GPU-Coord] MuseTalk models failed to load after 3 attempts")
            return False
    
    async def release_from_lipsync(self):
        """口型同步阶段完成（保持MuseTalk热加载，不释放GPU）"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            self._phase = "idle"
            logger.info("[GPU-Coord] LipSync phase complete, MuseTalk stays on GPU (hot)")
    
    async def _release_musetalk(self) -> bool:
        """释放MuseTalk模型到CPU"""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(f"{self.musetalk_url}/release_gpu")
                if resp.status_code == 200:
                    logger.info("[GPU-Coord] MuseTalk released to CPU")
                    return True
                else:
                    logger.warning(f"[GPU-Coord] MuseTalk release failed: {resp.status_code}")
                    return False
        except Exception as e:
            logger.warning(f"[GPU-Coord] MuseTalk release error (may not be running): {e}")
            return False
    
    async def _reload_musetalk(self) -> bool:
        """将MuseTalk模型重新加载到GPU"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{self.musetalk_url}/reload_gpu")
                if resp.status_code == 200:
                    logger.info("[GPU-Coord] MuseTalk reloaded to GPU")
                    # 等待模型完全加载
                    await asyncio.sleep(5)
                    return True
                else:
                    logger.warning(f"[GPU-Coord] MuseTalk reload failed: {resp.status_code}")
                    return False
        except Exception as e:
            logger.warning(f"[GPU-Coord] MuseTalk reload error: {e}")
            return False
    
    async def _check_musetalk_health(self) -> dict:
        """检查MuseTalk健康状态"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.musetalk_url}/health")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        return {"status": "error", "models_loaded": False}
    
    async def _check_gpt_sovits_health(self) -> bool:
        """检查GPT-SoVITS是否在运行"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.gpt_sovits_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
    
    @property
    def current_phase(self) -> str:
        return self._phase
