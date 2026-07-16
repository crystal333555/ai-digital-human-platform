import os
import sys
import shutil
from modelscope import snapshot_download

os.environ["MODELSCOPE_CACHE"] = "./GPT-SoVITS/GPT_SoVITS/pretrained_models"

# 下载GPT-SoVITS v2模型
print("开始下载GPT-SoVITS模型...")

try:
    # 下载GPT-SoVITS基础模型
    path = snapshot_download(
        "lj1995/GPT-SoVITS",
        cache_dir="./GPT-SoVITS/GPT_SoVITS/pretrained_models",
        revision="main"
    )
    print(f"模型下载完成: {path}")
except Exception as e:
    print(f"下载失败: {e}")
    print("尝试备用方案...")
