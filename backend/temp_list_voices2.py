import asyncio
import edge_tts
import json

async def list_all_voices():
    voices = await edge_tts.list_voices()
    # Chinese voices
    zh = [v for v in voices if 'zh' in v['Locale']]
    en = [v for v in voices if 'en-US' in v['Locale']]
    print("=== zh voices ===")
    for v in zh:
        print(f"  {v['ShortName']} ({v['Gender']}) - {v.get('FriendlyName', '')}")
    print("\n=== en-US voices ===")
    for v in en:
        print(f"  {v['ShortName']} ({v['Gender']}) - {v.get('FriendlyName', '')}")

asyncio.run(list_all_voices())
