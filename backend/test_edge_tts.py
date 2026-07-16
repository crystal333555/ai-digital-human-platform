import asyncio
import edge_tts
import os

async def test():
    try:
        await edge_tts.Communicate('你好，这是测试', 'zh-CN-XiaoxiaoNeural').save('test_tts.mp3')
        size = os.path.getsize('test_tts.mp3')
        print(f'OK, size={size}')
        os.remove('test_tts.mp3')
    except Exception as e:
        print(f'Error: {type(e).__name__}: {e}')

asyncio.run(test())
