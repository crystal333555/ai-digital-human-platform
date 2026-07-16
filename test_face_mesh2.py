import sys
sys.path.insert(0, './backend')

from app.services.face_mesh_service import get_face_mesh_service

print('Creating service...')
try:
    service = get_face_mesh_service()
    print('Service created')
    result = service.extract_3d_mesh('./uploads/test_avatar.jpg')
    print(f'Result: {result is not None}')
    if result:
        print(f'Has face: {result.get("has_face")}')
        if result.get('has_face'):
            print(f'Vertices: {result["num_vertices"]}')
            print(f'Faces: {result["num_faces"]}')
        else:
            print('No face detected in image')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
