import sys
sys.path.insert(0, '.')
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

files = {'file': ('test.jpg', open('../uploads/test_avatar.jpg', 'rb'), 'image/jpeg')}
data = {'name': 'test', 'style': 'realistic', 'display_mode': 'both'}

try:
    response = client.post('/api/v1/avatars/upload', data=data, files=files)
    print(f'Status: {response.status_code}')
    print(response.text[:1000])
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
