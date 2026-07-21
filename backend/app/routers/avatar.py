import os
import uuid
import shutil
from typing import List, Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.avatar import Avatar, User
from app.config import settings

router = APIRouter(prefix="/avatars")

from pydantic import BaseModel, field_serializer
from datetime import datetime

class AvatarCreate(BaseModel):
    name: str
    description: Optional[str] = None
    style: str = "realistic"
    display_mode: str = "both"

class AvatarResponse(AvatarCreate):
    id: int
    original_image_path: str
    transparent_image_path: Optional[str] = None
    styled_image_path: Optional[str] = None
    model_3d_config: Optional[dict] = None
    is_active: bool
    created_at: datetime
    
    @field_serializer('created_at')
    def serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()
    
    class Config:
        from_attributes = True


@router.get("/backgrounds/list")
async def list_backgrounds():
    """获取可用背景图列表"""
    bg_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "uploads", "backgrounds")
    backgrounds = []
    if os.path.exists(bg_dir):
        for f in sorted(os.listdir(bg_dir)):
            if f.lower().endswith(('.png', '.jpg', '.jpeg')):
                name = os.path.splitext(f)[0]
                backgrounds.append({
                    "name": name,
                    "url": f"/uploads/backgrounds/{f}",
                })
    return {"backgrounds": backgrounds}


@router.post("/backgrounds/upload")
async def upload_background(file: UploadFile = File(...)):
    """上传自定义背景图"""
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="请上传图片文件")
    
    ext = os.path.splitext(file.filename or "bg.png")[1] or ".png"
    filename = f"custom_{uuid.uuid4().hex[:8]}{ext}"
    bg_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "uploads", "backgrounds")
    os.makedirs(bg_dir, exist_ok=True)
    file_path = os.path.join(bg_dir, filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"success": True, "name": os.path.splitext(filename)[0], "url": f"/uploads/backgrounds/{filename}"}


@router.post("/upload", response_model=AvatarResponse)
async def upload_avatar(
    name: str = Form(...),
    description: Optional[str] = Form(None),
    style: str = Form("realistic"),
    display_mode: str = Form("both"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """上传照片创建数字人形象"""
    import uuid
    
    # 验证文件类型（同时检查content_type和扩展名）
    allowed_types = ['image/jpeg', 'image/png', 'image/jpg', 'image/webp']
    allowed_exts = ['.jpg', '.jpeg', '.png', '.webp']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    is_valid_type = (
        file.content_type in allowed_types or 
        file_ext in allowed_exts or
        (file.content_type or '').startswith('image/')
    )
    
    if not is_valid_type:
        raise HTTPException(
            status_code=400, 
            detail=f"仅支持 JPG/PNG/WEBP 图片格式，收到: content_type={file.content_type}, ext={file_ext}"
        )
    
    # 生成唯一文件名
    import uuid
    file_ext = os.path.splitext(file.filename)[1]
    file_name = f"{uuid.uuid4().hex}{file_ext}"
    file_path = os.path.join(settings.AVATAR_DIR, file_name)
    
    # 保存文件
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 存储为相对路径（基于backend目录的 ../uploads/ 格式，与前端静态文件服务兼容）
    public_path = f"../uploads/avatars/{file_name}"
    
    # 自动去背景，生成透明PNG
    transparent_path = None
    try:
        from rembg import remove
        from PIL import Image as PILImage
        transparent_name = f"{uuid.uuid4().hex}_transparent.png"
        transparent_full_path = os.path.join(settings.AVATAR_DIR, transparent_name)
        input_img = PILImage.open(file_path)
        output_img = remove(input_img)
        output_img.save(transparent_full_path, "PNG")
        transparent_path = f"../uploads/avatars/{transparent_name}"
    except ImportError:
        pass  # rembg未安装，跳过
    except Exception:
        pass  # 去背景失败，不影响上传
    
    # 创建数据库记录 (简化版，实际应有用户认证)
    user = db.query(User).first()
    if not user:
        user = User(username="admin", email="admin@example.com")
        db.add(user)
        db.commit()
        db.refresh(user)
    
    avatar = Avatar(
        name=name,
        description=description,
        original_image_path=public_path,
        transparent_image_path=transparent_path,
        style=style,
        display_mode=display_mode,
        owner_id=user.id,
        # 初始化3D配置
        model_3d_config={
            "type": display_mode,
            "model_url": None,
            "blendshapes": {
                "eyes": 1.0,
                "mouth": 1.0,
                "brow": 1.0
            },
            "animation_rig": "standard"
        }
    )
    
    db.add(avatar)
    db.commit()
    db.refresh(avatar)
    
    return avatar

@router.get("/", response_model=List[AvatarResponse])
async def list_avatars(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取形象列表"""
    avatars = db.query(Avatar).filter(Avatar.is_active == True).offset(skip).limit(limit).all()
    return avatars

@router.get("/{avatar_id}", response_model=AvatarResponse)
async def get_avatar(
    avatar_id: int,
    db: Session = Depends(get_db)
):
    """获取单个形象详情"""
    avatar = db.query(Avatar).filter(Avatar.id == avatar_id, Avatar.is_active == True).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="形象不存在")
    return avatar

@router.put("/{avatar_id}")
async def update_avatar(
    avatar_id: int,
    display_mode: Optional[str] = None,
    style: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """更新形象配置"""
    avatar = db.query(Avatar).filter(Avatar.id == avatar_id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="形象不存在")
    
    if display_mode:
        avatar.display_mode = display_mode
    if style:
        avatar.style = style
    
    db.commit()
    db.refresh(avatar)
    return avatar


@router.post("/{avatar_id}/remove-bg")
async def remove_avatar_background(
    avatar_id: int,
    db: Session = Depends(get_db)
):
    """为已有形象去背景，生成透明PNG"""
    avatar = db.query(Avatar).filter(Avatar.id == avatar_id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="形象不存在")
    
    # 获取原始图片路径
    orig_path = avatar.original_image_path
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    if orig_path.startswith("../"):
        orig_path = os.path.join(project_root, orig_path.lstrip("../"))
    elif orig_path.startswith("/uploads/"):
        orig_path = os.path.join(project_root, orig_path.lstrip("/"))
    elif not os.path.isabs(orig_path):
        orig_path = os.path.join(project_root, orig_path)
    if not os.path.exists(orig_path):
        raise HTTPException(status_code=404, detail=f"原始图片文件不存在: {orig_path}")
    
    try:
        from rembg import remove
        from PIL import Image as PILImage
        transparent_name = f"{uuid.uuid4().hex}_transparent.png"
        transparent_full_path = os.path.join(settings.AVATAR_DIR, transparent_name)
        input_img = PILImage.open(orig_path)
        output_img = remove(input_img)
        output_img.save(transparent_full_path, "PNG")
        
        avatar.transparent_image_path = f"../uploads/avatars/{transparent_name}"
        db.commit()
        db.refresh(avatar)
        return {"success": True, "transparent_image_path": avatar.transparent_image_path}
    except ImportError:
        # rembg未安装，用OpenCV GrabCut替代
        try:
            import cv2
            import numpy as np
            from PIL import Image as PILImage
            
            transparent_name = f"{uuid.uuid4().hex}_transparent.png"
            transparent_full_path = os.path.join(settings.AVATAR_DIR, transparent_name)
            
            img = cv2.imread(orig_path)
            h, w = img.shape[:2]
            mask = np.zeros((h, w), np.uint8)
            bgd = np.zeros((1, 65), np.float64)
            fgd = np.zeros((1, 65), np.float64)
            # 矩形区域：中心80%区域为前景
            rect = (int(w*0.1), int(h*0.05), int(w*0.8), int(h*0.9))
            cv2.grabCut(img, mask, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
            mask2 = np.where((mask == 1) | (mask == 3), 255, 0).astype('uint8')
            
            # 羽化边缘
            mask2 = cv2.GaussianBlur(mask2, (5, 5), 0)
            
            # 转为RGBA
            rgba = cv2.cvtColor(img, cv2.COLOR_BGR2RGBA)
            rgba[:, :, 3] = mask2
            
            pil_img = PILImage.fromarray(rgba)
            pil_img.save(transparent_full_path, "PNG")
            
            avatar.transparent_image_path = f"../uploads/avatars/{transparent_name}"
            db.commit()
            db.refresh(avatar)
            return {"success": True, "transparent_image_path": avatar.transparent_image_path, "method": "grabcut"}
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"去背景失败(rembg+grabcut): {str(e)} / {str(e2)}")


@router.delete("/{avatar_id}")
async def delete_avatar(
    avatar_id: int,
    db: Session = Depends(get_db)
):
    """删除形象"""
    avatar = db.query(Avatar).filter(Avatar.id == avatar_id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="形象不存在")
    
    avatar.is_active = False
    db.commit()
    return {"message": "形象已删除"}
