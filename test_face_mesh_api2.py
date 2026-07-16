import requests
import traceback

try:
    url = 'http://localhost:8000/api/v1/face-mesh/extract-from-path'
    payload = {'image_path': 'uploads/avatars/a5288a64e73d4d8bbe5391f188529217.jpg'}
    print(f'Sending POST to {url}')
    resp = requests.post(url, json=payload, timeout=30)
    print(f'Status: {resp.status_code}')
    print(f'Headers: {dict(resp.headers)}')
    print(f'Body: {resp.text[:2000]}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
    traceback.print_exc()
