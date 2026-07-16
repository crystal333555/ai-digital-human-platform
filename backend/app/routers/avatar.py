import os
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
    styled_image_path: Optional[str] = None
    model_3d_config: Optional[dict] = None
    is_active: bool
    created_at: datetime
    
    @field_serializer('created_at')
    def serialize_created_at(self, value: datetime) -> str:
        return value.isoformat()
    
    class Config:
        from_attributes = True

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
