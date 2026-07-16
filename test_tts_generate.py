import sys, os

os.chdir('GPT-SoVITS')
sys.path.insert(0, 'GPT_SoVITS')

from TTS_infer_pack.TTS import TTS, TTS_Config

cfg = TTS_Config('GPT_SoVITS/configs/tts_infer.yaml')
tts = TTS(cfg)
print('TTS initialized')

inputs = {
    "ref_audio_path": "../reference_audio.wav",
    "text": "你好，这是GPT-SoVITS音色克隆测试。",
    "text_lang": "zh",
    "prompt_text": "参考音频测试",
    "prompt_lang": "zh",
    "top_k": 20,
    "top_p": 0.6,
    "temperature": 0.6,
    "speed_factor": 1.0,
    "text_split_method": "cut5",
}

try:
    result = tts.run(inputs)
    print(f'Result type: {type(result)}')

    segments = []
    for item in result:
        print(f'Got item: {type(item)}')
        if item is not None:
            segments.append(item)

    if segments and len(segments) > 0:
        audio_data, sr = segments[0]
        print(f'Audio data type: {type(audio_data)}')
        print(f'Audio data: {audio_data}')
        print(f'Sample rate: {sr}')

        # 保存音频
        import soundfile as sf
        import numpy as np

        if isinstance(audio_data, np.ndarray):
            sf.write('../test_output.wav', audio_data, sr)
        elif isinstance(audio_data, (list, tuple)):
            sf.write('../test_output.wav', np.array(audio_data), sr)
        else:
            print(f'Unexpected audio data type: {type(audio_data)}')

        print('Audio saved to test_output.wav')
    else:
        print('No audio generated')

except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
