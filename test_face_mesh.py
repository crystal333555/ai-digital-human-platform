import sys
sys.path.insert(0, './backend')

from app.services.face_mesh_service import face_mesh_service
import json

print('Testing face mesh extraction...')
result = face_mesh_service.extract_3d_mesh('./uploads/test_avatar.jpg')
if result is None:
    print('Failed to load image')
elif not result.get('has_face'):
    print('No face detected in image')
else:
    print(f'Vertices: {result.get("num_vertices")}')
    print(f'Faces: {result.get("num_faces")}')
    print(f'Image: {result.get("image_width")} x {result.get("image_height")}')
    
    geometry = face_mesh_service.generate_threejs_buffergeometry(result)
    with open('./uploads/test_mesh.json', 'w') as f:
        json.dump(geometry, f)
    print('Mesh saved to test_mesh.json')
    print('First vertex:', result['vertices'][0])
