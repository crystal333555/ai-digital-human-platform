import requests
import json

API = 'http://localhost:8000'

# 1. Create a conversation
payload = {
    "avatar_id": 11,
    "voice_id": 1,
    "system_prompt": "你是一个友好的AI助手，用中文回答问题。"
}
resp = requests.post(f'{API}/api/v1/chat/conversations', json=payload)
print('Create conv:', resp.status_code)
data = resp.json()
print(json.dumps(data, indent=2, ensure_ascii=False)[:500])

conv_id = data.get('id')
if conv_id:
    # 2. Send a message
    msg_payload = {
        "message": "你好，请自我介绍一下",
        "conversation_id": conv_id
    }
    resp2 = requests.post(f'{API}/api/v1/chat/send', json=msg_payload)
    print('\nSend msg:', resp2.status_code)
    data2 = resp2.json()
    print(json.dumps(data2, indent=2, ensure_ascii=False)[:1000])
    print('Audio URL:', data2.get('audio_url'))
    print('Video URL:', data2.get('video_url'))
