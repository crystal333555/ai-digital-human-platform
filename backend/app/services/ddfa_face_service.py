import cv2
import numpy as np
from typing import Dict, List, Optional
import os

class Ddfa3DFaceService:
    """使用 face-alignment 进行3D人脸关键点检测，生成高质量3D网格"""
    
    def __init__(self):
        import face_alignment
        # 使用 3D 关键点检测模型 (SFD 检测器 + 3D 关键点)
        self.fa = face_alignment.FaceAlignment(
            face_alignment.LandmarksType.THREE_D, 
            face_detector='sfd',
            device='cpu'
        )
    
    def extract_3d_mesh(self, image_path: str) -> Optional[Dict]:
        """从照片提取3D人脸关键点
        
        Returns:
            {
                'vertices': [[x, y, z], ...],  # 68个3D关键点 (像素坐标)
                'uvs': [[u, v], ...],  # 归一化到 [0,1]
                'indices': [i0, i1, i2, ...],  # 三角剖分
                'image_width': int,
                'image_height': int,
                'has_face': bool
            }
        """
        image = cv2.imread(image_path)
        if image is None:
            return None
        
        h, w = image.shape[:2]
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # 检测3D关键点
        preds = self.fa.get_landmarks(image_rgb)
        
        if preds is None or len(preds) == 0:
            return {'has_face': False}
        
        landmarks = preds[0]  # 取第一个人脸，68个3D点
        
        # 归一化到 [-1, 1] 范围
        vertices = []
        uvs = []
        for (x, y, z) in landmarks:
            # 归一化坐标
            nx = (x - w/2) / (w/2)
            ny = -(y - h/2) / (h/2)  # Y轴翻转
            nz = z / (w/2)  # Z深度归一化
            vertices.append([nx, ny, nz])
            uvs.append([x / w, 1.0 - y / h])  # UV坐标
        
        # 使用Delaunay三角剖分
        indices = self._triangulate(landmarks, w, h)
        
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
    
    def _triangulate(self, landmarks: np.ndarray, w: int, h: int) -> List[int]:
        """对68个3D关键点进行Delaunay三角剖分"""
        from scipy.spatial import Delaunay
        
        # 使用2D坐标进行三角剖分
        points_2d = np.array([[p[0], p[1]] for p in landmarks])
        
        # 限制在图像范围内
        points_2d = np.clip(points_2d, 0, max(w, h))
        
        try:
            tri = Delaunay(points_2d)
            indices = tri.simplices.flatten().tolist()
        except Exception:
            # 回退：使用中心扇形展开
            indices = []
            center = 30  # 鼻尖附近
            for i in range(68):
                if i != center:
                    indices.extend([center, (i-1) % 68, i])
        
        return indices
    
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
                'generator': 'Ddfa3DFaceService'
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

# 单例实例
_ddfa_service = None

def get_ddfa_service() -> Ddfa3DFaceService:
    global _ddfa_service
    if _ddfa_service is None:
        _ddfa_service = Ddfa3DFaceService()
    return _ddfa_service
