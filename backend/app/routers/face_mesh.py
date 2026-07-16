from fastapi import APIRouter, HTTPException, UploadFile, File, Body
from pydantic import BaseModel
import os
import shutil

from app.services.face_mesh_service import get_face_mesh_service

router = APIRouter(prefix="/face-mesh", tags=["face-mesh"])

class ImagePathRequest(BaseModel):
    image_path: str

def resolve_image_path(rel_path: str) -> str:
    """解析图片路径为绝对路径"""
    # 如果已经是绝对路径
    if os.path.isabs(rel_path):
        return rel_path
    # 从项目根目录找
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    # 尝试几种路径组合
    for base in [project_root, os.path.join(project_root, 'uploads')]:
        full = os.path.join(base, rel_path)
        if os.path.exists(full):
            return full
    # 回退：直接拼接项目根目录
    return os.path.join(project_root, rel_path)

@router.post("/extract")
async def extract_face_mesh(file: UploadFile = File(...)):
    """从上传的照片提取3D人脸mesh"""
    temp_path = f"temp_upload_{file.filename}"
    try:
        with open(temp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        service = get_face_mesh_service()
        result = service.extract_3d_mesh(temp_path)
        
        if result is None:
            raise HTTPException(status_code=400, detail="无法读取图片")
        
        if not result.get("has_face"):
            return {
                "success": False,
                "message": "未检测到人脸，请上传包含正脸的照片"
            }
        
        geometry = service.generate_threejs_buffergeometry(result)
        
        return {
            "success": True,
            "geometry": geometry,
            "num_vertices": result["num_vertices"],
            "num_faces": result["num_faces"],
            "image_width": result["image_width"],
            "image_height": result["image_height"]
        }
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@router.post("/extract-from-path")
async def extract_face_mesh_from_path(request: ImagePathRequest):
    """从已存在的图片路径提取3D人脸mesh"""
    image_path = resolve_image_path(request.image_path)
    
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail=f"图片不存在: {image_path}")
    
    service = get_face_mesh_service()
    result = service.extract_3d_mesh(image_path)
    
    if result is None:
        raise HTTPException(status_code=400, detail="无法读取图片")
    
    if not result.get("has_face"):
        return {
            "success": False,
            "message": "未检测到人脸，请上传包含正脸的照片"
        }
    
    geometry = service.generate_threejs_buffergeometry(result)
    
    return {
        "success": True,
        "geometry": geometry,
        "num_vertices": result["num_vertices"],
        "num_faces": result["num_faces"],
        "image_width": result["image_width"],
        "image_height": result["image_height"]
    }
