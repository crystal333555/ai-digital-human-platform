import sys, os
sys.path.insert(0, './backend')
os.environ['PYTHONIOENCODING'] = 'utf-8'

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
resp = client.post('/api/v1/chat/conversations', json={'avatar_id': 11, 'voice_id': 1, 'system_prompt': 'hello'})
print(f'Status: {resp.status_code}')
print(f'Body: {resp.text[:2000]}')
