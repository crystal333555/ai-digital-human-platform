from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    avatars = relationship("Avatar", back_populates="owner")
    voices = relationship("Voice", back_populates="owner")
    conversations = relationship("Conversation", back_populates="user")

class Avatar(Base):
    __tablename__ = "avatars"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    description = Column(Text, nullable=True)
    
    # 原始照片路径
    original_image_path = Column(String(500))
    # 去背景透明PNG路径（人物only，背景透明）
    transparent_image_path = Column(String(500), nullable=True)
    # 风格化后照片路径
    styled_image_path = Column(String(500), nullable=True)
    
    # 3D模型配置 (JSON存储Three.js模型参数)
    model_3d_config = Column(JSON, nullable=True)
    
    # 形象风格: realistic, anime, cartoon, etc.
    style = Column(String(50), default="realistic")
    
    # 模式: 2d, 3d, both
    display_mode = Column(String(20), default="both")
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="avatars")
    
    conversations = relationship("Conversation", back_populates="avatar")

class Voice(Base):
    __tablename__ = "voices"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    description = Column(Text, nullable=True)
    
    # 参考音频路径
    reference_audio_path = Column(String(500))
    # GPT-SoVITS训练后的模型ID或配置
    cloned_voice_id = Column(String(200), nullable=True)
    
    # 音色来源: edge-tts(预设), cloned(克隆), custom(自定义API)
    source = Column(String(50), default="edge-tts")
    
    # TTS配置参数 (语速、音调等)
    tts_config = Column(JSON, nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    owner_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="voices")
    
    conversations = relationship("Conversation", back_populates="voice")

class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=True)
    
    # 角色设定Prompt
    system_prompt = Column(Text, default="你是一个友好的AI助手。")
    
    # 关联配置
    avatar_id = Column(Integer, ForeignKey("avatars.id"))
    voice_id = Column(Integer, ForeignKey("voices.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # 会话状态
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    avatar = relationship("Avatar", back_populates="conversations")
    voice = relationship("Voice", back_populates="conversations")
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 消息类型: user(用户), assistant(AI), system(系统)
    role = Column(String(20))
    content = Column(Text)
    
    # 如果是AI回复，关联的生成资源
    audio_path = Column(String(500), nullable=True)
    video_path = Column(String(500), nullable=True)
    
    # 情感标签 (用于驱动表情/动作)
    emotion_tag = Column(String(50), nullable=True)
    
    conversation_id = Column(Integer, ForeignKey("conversations.id"))
    conversation = relationship("Conversation", back_populates="messages")
    
    created_at = Column(DateTime, default=datetime.utcnow)
