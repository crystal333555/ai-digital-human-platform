import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
import os
import json

class FaceMeshService:
    """使用MediaPipe Face Landmarker从照片提取3D人脸mesh"""
    
    def __init__(self):
        from mediapipe.tasks.python import vision
        from mediapipe.tasks.python.core.base_options import BaseOptions
        
        # 获取模型路径 - 搜索可能的位置
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', '..', 'models', 'mediapipe', 'face_landmarker.task'),
            os.path.join(os.path.dirname(__file__), '..', '..', 'app', 'models', 'mediapipe', 'face_landmarker.task'),
            'app/models/mediapipe/face_landmarker.task',
            os.path.join(os.getcwd(), 'app', 'models', 'mediapipe', 'face_landmarker.task'),
        ]
        
        model_path = None
        for p in possible_paths:
            abs_path = os.path.abspath(p)
            if os.path.exists(abs_path):
                model_path = abs_path
                break
        
        if not model_path:
            raise FileNotFoundError("Face Landmarker model not found. Searched: " + str([os.path.abspath(p) for p in possible_paths]))
        
        # 创建Face Landmarker
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=model_path),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=False
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)
    
    def extract_3d_mesh(self, image_path: str) -> Optional[Dict]:
        """从照片提取3D人脸mesh数据
        
        Returns:
            {
                'vertices': [[x, y, z], ...]  # 478个点
                'uvs': [[u, v], ...]  # 纹理坐标
                'indices': [i0, i1, i2, ...]  # 三角面片索引
                'image_width': int,
                'image_height': int,
                'has_face': bool
            }
        """
        import mediapipe as mp
        
        image = cv2.imread(image_path)
        if image is None:
            return None
        
        h, w = image.shape[:2]
        
        # 转换为MediaPipe Image格式
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        
        # 检测人脸
        results = self.landmarker.detect(mp_image)
        
        if not results.face_landmarks or len(results.face_landmarks) == 0:
            return {'has_face': False, 'image_width': w, 'image_height': h}
        
        face = results.face_landmarks[0]
        
        # 提取478个关键点（新版MediaPipe有478个而不是468个）
        vertices = []
        uvs = []
        for landmark in face:
            x = (landmark.x - 0.5) * 2  # [-1, 1]
            y = (0.5 - landmark.y) * 2  # [-1, 1]，翻转Y轴
            z = landmark.z * 2
            vertices.append([x, y, z])
            uvs.append([landmark.x, 1.0 - landmark.y])
        
        # 使用Delaunay三角剖分生成标准人脸三角网格
        import scipy
        from scipy.spatial import Delaunay
        
        # 获取关键点的2D坐标
        points_2d = np.array([[lm.x, lm.y] for lm in face])
        
        # 进行Delaunay三角剖分
        try:
            tri = Delaunay(points_2d)
            indices = tri.simplices.flatten().tolist()
        except Exception:
            # 回退：简单的扇形展开
            indices = []
            center = 1
            for i in range(2, len(face)):
                indices.extend([center, i - 1, i])
            indices.extend([center, len(face) - 1, 1])
        
        return {
            'vertices': vertices,
            'uvs': uvs,
            'indices': indices,
            'image_width': w,
            'image_height': h,
            'has_face': True,
            'num_vertices': len(vertices),
            'num_faces': len(indices) // 3
        }
    
    def generate_threejs_buffergeometry(self, mesh_data: Dict) -> Dict:
        """生成Three.js BufferGeometry JSON格式"""
        if not mesh_data.get('has_face'):
            return None
        
        vertices_flat = [v for vertex in mesh_data['vertices'] for v in vertex]
        uvs_flat = [v for uv in mesh_data['uvs'] for v in uv]
        
        return {
            'metadata': {
                'version': 4.5,
                'type': 'BufferGeometry',
                'generator': 'FaceMeshService'
            },
            'data': {
                'attributes': {
                    'position': {
                        'itemSize': 3,
                        'type': 'Float32Array',
                        'array': vertices_flat,
                        'normalized': False
                    },
                    'uv': {
                        'itemSize': 2,
                        'type': 'Float32Array',
                        'array': uvs_flat,
                        'normalized': False
                    }
                },
                'index': {
                    'type': 'Uint16Array',
                    'array': mesh_data['indices']
                }
            }
        }

# 单例
face_mesh_service = None

def get_face_mesh_service():
    global face_mesh_service
    if face_mesh_service is None:
        face_mesh_service = FaceMeshService()
    return face_mesh_service
