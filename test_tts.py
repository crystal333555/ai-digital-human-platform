import sys, os

# 切换到 GPT-SoVITS 目录
os.chdir('GPT-SoVITS')
sys.path.insert(0, 'GPT_SoVITS')

from TTS_infer_pack.TTS import TTS, TTS_Config

try:
    cfg = TTS_Config('GPT_SoVITS/configs/tts_infer.yaml')
    tts = TTS(cfg)
    print('TTS initialized successfully')
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
