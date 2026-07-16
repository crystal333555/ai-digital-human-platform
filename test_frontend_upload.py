import requests

# 模拟前端 Ant Design Upload 的文件结构
# AntD Upload 在 Form 中的值包含 fileList
from pathlib import Path

# 方式1：像前端一样构造 multipart，字段名"file"
files = {'file': ('zx.jpg', open('../uploads/test_avatar.jpg', 'rb'), 'image/jpeg')}
data = {'name': '小玄子', 'style': 'realistic', 'display_mode': 'both'}

r = requests.post('http://localhost:8000/api/v1/avatars/upload', data=data, files=files)
print('=== 方式1（正确文件名）===')
print('Status:', r.status_code)
print(r.text[:500])
print()

# 方式2：像前端如果没选到文件一样，不传 file
r2 = requests.post('http://localhost:8000/api/v1/avatars/upload', data=data)
print('=== 方式2（缺 file 字段）===')
print('Status:', r2.status_code)
print(r2.text[:500])
