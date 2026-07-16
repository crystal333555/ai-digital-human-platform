import requests
import json

url = 'http://localhost:8000/api/v1/face-mesh/extract-from-path'
payload = {'image_path': 'uploads/avatars/a5288a64e73d4d8bbe5391f188529217.jpg'}

try:
    print('Sending request...')
    resp = requests.post(url, json=payload, timeout=60)
    print('Status:', resp.status_code)
    data = resp.json()
    print('Success:', data.get('success'))
    print('Vertices:', data.get('num_vertices'))
    print('Faces:', data.get('num_faces'))
    if data.get('success'):
        # Save geometry for inspection
        with open('test_geometry.json', 'w') as f:
            json.dump(data.get('geometry', {}), f)
        print('Geometry saved to test_geometry.json')
except Exception as e:
    print('Error:', type(e).__name__, str(e))
