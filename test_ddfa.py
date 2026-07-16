import sys
sys.path.insert(0, './backend')

import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

print('Importing face_alignment...')
try:
    from app.services.ddfa_face_service import get_ddfa_service
    print('Creating DDFA service...')
    service = get_ddfa_service()
    print('Service created!')
    
    print('Extracting 3D mesh...')
    result = service.extract_3d_mesh('uploads/avatars/a5288a64e73d4d8bbe5391f188529217.jpg')
    print(f'Has face: {result.get("has_face")}')
    if result.get('has_face'):
        print(f'Vertices: {result["num_vertices"]}')
        print(f'Faces: {result["num_faces"]}')
        print(f'First vertex: {result["vertices"][0]}')
except Exception as e:
    import traceback
    print(f'Error: {type(e).__name__}: {e}')
    traceback.print_exc()
