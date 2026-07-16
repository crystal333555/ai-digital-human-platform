import asyncio
import edge_tts
import json

async def list_voices():
    voices = await edge_tts.list_voices()
    zh_voices = [v for v in voices if 'zh-CN' in v['ShortName']]
    print(json.dumps(zh_voices, ensure_ascii=False, indent=2))

asyncio.run(list_voices())
