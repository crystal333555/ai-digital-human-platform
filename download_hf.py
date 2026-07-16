import os
import urllib.request
import ssl

# 禁用SSL证书验证（用于国内镜像）
ssl._create_default_https_context = ssl._create_unverified_context

# 使用hf-mirror国内镜像
HF_MIRROR = "https://hf-mirror.com"
MODELS = [
    "lj1995/GPT-SoVITS",
]

# 需要下载的特定文件
FILES = [
    "GPT_SoVITS/pretrained_models/s1bert25hz-5kh-longer-epoch=68e-step=50232.ckpt",
    "GPT_SoVITS/pretrained_models/s2G488k.pth",
]

BASE_DIR = "./GPT-SoVITS"

def download_file(url, local_path):
    """下载文件，显示进度"""
    print(f"Downloading: {url}")
    print(f"To: {local_path}")
    
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    
    try:
        urllib.request.urlretrieve(url, local_path)
        print(f"Success: {local_path}")
        return True
    except Exception as e:
        print(f"Failed: {e}")
        return False

# 下载核心文件
for file_path in FILES:
    url = f"{HF_MIRROR}/lj1995/GPT-SoVITS/resolve/main/{file_path}"
    local_path = os.path.join(BASE_DIR, file_path)
    download_file(url, local_path)

print("Done!")
