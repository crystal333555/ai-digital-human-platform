import sys
sys.path.insert(0, './backend')

import os
os.environ['PYTHONIOENCODING'] = 'utf-8'

print('Testing FaceMeshService locally...')
try:
    from app.services.face_mesh_service import get_face_mesh_service
    print('Creating service...')
    service = get_face_mesh_service()
    print('Service created!')
    
    print('Extracting mesh...')
    result = service.extract_3d_mesh('uploads/avatars/a5288a64e73d4d8bbe5391f188529217.jpg')
    print(f'Result: {result is not None}')
    if result:
        print(f'Has face: {result.get("has_face")}')
        if result.get('has_face'):
            print(f'Vertices: {result["num_vertices"]}')
            print(f'Faces: {result["num_faces"]}')
except Exception as e:
    import traceback
    print(f'Error: {type(e).__name__}: {e}')
    traceback.print_exc()
