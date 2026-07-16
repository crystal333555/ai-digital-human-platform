from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class PPTProject(Base):
    """PPT讲解项目"""
    __tablename__ = "ppt_projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200))
    
    # 原始PPT文件路径
    ppt_file_path = Column(String(500))
    
    # 关联数字人形象
    avatar_id = Column(Integer, ForeignKey("avatars.id"), nullable=True)
    
    # 音色配置 JSON: {"type": "preset", "id": "xxx", "edge_voice": "...", "rate": "+0%", "pitch": "+0Hz"}
    voice_config = Column(JSON, nullable=True)
    
    # 布局模式: "bottom_bar"(底部横条，推荐) | "pip"(画中画)
    layout_mode = Column(String(20), default="bottom_bar")
    
    # 数字人位置: "bottom-center" | "bottom-left" | "bottom-right" | "bottom-follow"
    digital_human_position = Column(String(20), default="bottom-center")
    
    # 数字人占画面比例 (0.15-0.35)
    digital_human_size = Column(Float, default=0.25)
    
    # 翻页过渡效果: "fade" | "slide" | "none"
    transition = Column(String(20), default="fade")
    
    # 状态: draft | generating | completed | error
    status = Column(String(20), default="draft")
    
    # 最终视频路径
    output_video_path = Column(String(500), nullable=True)
    
    # PPT总页数
    slide_count = Column(Integer, default=0)
    
    # 所属用户
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    slides = relationship("PPTSlide", back_populates="project", cascade="all, delete-orphan",
                          order_by="PPTSlide.slide_index")


class PPTSlide(Base):
    """PPT单页"""
    __tablename__ = "ppt_slides"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("ppt_projects.id"))
    
    # 页码（0-based）
    slide_index = Column(Integer)
    
    # 页面图片路径（从PPT导出的图片）
    slide_image_path = Column(String(500))
    
    # 页面提取的文字（从PPT文本框提取）
    extracted_text = Column(Text, nullable=True)
    
    # 用户编写的讲解文字
    narration_text = Column(Text, nullable=True)
    
    # 生成的音频路径
    audio_path = Column(String(500), nullable=True)
    
    # 生成的口型视频路径
    video_path = Column(String(500), nullable=True)
    
    # 状态: pending | generating | done | error
    status = Column(String(20), default="pending")
    
    # 音频时长（秒）
    duration = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    project = relationship("PPTProject", back_populates="slides")
