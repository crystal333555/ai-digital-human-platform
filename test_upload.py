import requests

# 测试头像上传
files = {'file': ('test_avatar.jpg', open('../uploads/test_avatar.jpg', 'rb'), 'image/jpeg')}
data = {'name': 'test', 'style': 'realistic', 'display_mode': 'both'}

r = requests.post('http://localhost:8000/api/v1/avatars/upload', data=data, files=files)
print('Status:', r.status_code)
print('Content-Type:', r.headers.get('content-type'))
print('Body:', r.text[:1000])
