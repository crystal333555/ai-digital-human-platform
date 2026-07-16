from datetime import datetime as DateTime
import os
import uuid
from typing import Optional, List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
import json

from app.database import get_db
from app.models.avatar import Conversation, Message, Avatar, Voice
from app.services.llm_service import LLMService
from app.services.tts_service import TTSService
from app.services.lip_sync_service import LipSyncService
from app.config import settings

router = APIRouter(prefix="/chat")

class ConversationCreate(BaseModel):
    title: Optional[str] = None
    avatar_id: int
    voice_id: int
    system_prompt: Optional[str] = None

class ConversationResponse(BaseModel):
    id: int
    title: Optional[str]
    system_prompt: str
    avatar_id: int
    voice_id: int
    is_active: bool
    created_at: DateTime
    updated_at: DateTime
    
    class Config:
        from_attributes = True

class ChatRequest(BaseModel):
    message: str
    conversation_id: int

# WebSocket连接管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict = {}
    
    async def connect(self, websocket: WebSocket, conversation_id: int):
        await websocket.accept()
        self.active_connections[conversation_id] = websocket
    
    def disconnect(self, conversation_id: int):
        if conversation_id in self.active_connections:
            del self.active_connections[conversation_id]
    
    async def send_message(self, conversation_id: int, message: dict):
        if conversation_id in self.active_connections:
            await self.active_connections[conversation_id].send_json(message)

manager = ConnectionManager()

@router.post("/conversations", response_model=ConversationResponse)
async def create_conversation(
    data: ConversationCreate,
    db: Session = Depends(get_db)
):
    """创建新对话会话"""
    
    avatar = db.query(Avatar).filter(Avatar.id == data.avatar_id, Avatar.is_active == True).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="形象不存在")
    
    voice = db.query(Voice).filter(Voice.id == data.voice_id, Voice.is_active == True).first()
    if not voice:
        raise HTTPException(status_code=404, detail="音色不存在")
    
    conv = Conversation(
        title=data.title or f"对话 {avatar.name}",
        avatar_id=data.avatar_id,
        voice_id=data.voice_id,
        system_prompt=data.system_prompt or f"你是数字人{avatar.name}，请用友好、自然的语气与用户交流。",
        user_id=1  # 简化版，实际应取当前用户
    )
    
    db.add(conv)
    db.commit()
    db.refresh(conv)
    
    return conv

@router.get("/conversations")
async def list_conversations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """获取对话列表"""
    conversations = db.query(Conversation).filter(
        Conversation.is_active == True
    ).offset(skip).limit(limit).all()
    return conversations

@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: int,
    db: Session = Depends(get_db)
):
    """获取对话历史消息"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.is_active == True
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    return conversation.messages

@router.post("/send")
async def send_message(
    data: ChatRequest,
    db: Session = Depends(get_db)
):
    """发送消息并获取AI回复 (HTTP轮询模式)"""
    
    conversation = db.query(Conversation).filter(
        Conversation.id == data.conversation_id,
        Conversation.is_active == True
    ).first()
    
    if not conversation:
        raise HTTPException(status_code=404, detail="对话不存在")
    
    # 保存用户消息
    user_msg = Message(
        role="user",
        content=data.message,
        conversation_id=conversation.id
    )
    db.add(user_msg)
    db.commit()
    
    # 构建对话历史
    messages = []
    messages.append({"role": "system", "content": conversation.system_prompt})
    
    for msg in conversation.messages[-20:]:  # 取最近20条作为上下文
        if msg.role in ["user", "assistant"]:
            messages.append({"role": msg.role, "content": msg.content})
    
    # 调用LLM生成回复
    llm_service = LLMService()
    response_text, emotion = await llm_service.chat(messages)
    
    # 生成语音 (TTS)
    voice = db.query(Voice).filter(Voice.id == conversation.voice_id).first()
    tts_service = TTSService()
    
    audio_file_name = f"{uuid.uuid4().hex}.mp3"
    audio_path = os.path.join(settings.GENERATED_DIR, audio_file_name)
    
    # 根据音色配置选择TTS引擎
    if voice and voice.source == "cloned" and voice.cloned_voice_id:
        # 使用GPT-SoVITS克隆音色
        ref_audio = voice.reference_audio_path if voice.reference_audio_path else None
        prompt = "参考音频"
        if voice.tts_config and isinstance(voice.tts_config, dict):
            prompt = voice.tts_config.get("prompt_text", "参考音频")
        await tts_service.synthesize_with_cloned(
            text=response_text,
            voice_id=voice.cloned_voice_id,
            output_path=audio_path,
            ref_audio_path=ref_audio,
            prompt_text=prompt
        )
    else:
        # 使用Edge-TTS
        edge_voice = "zh-CN-XiaoxiaoNeural"
        if voice and voice.tts_config and isinstance(voice.tts_config, dict):
            edge_voice = voice.tts_config.get("edge_voice_name", "zh-CN-XiaoxiaoNeural")
        await tts_service.synthesize_with_edge(
            text=response_text,
            output_path=audio_path,
            voice_name=edge_voice
        )
    
    # 生成口型同步视频
    video_file_name = f"{uuid.uuid4().hex}.mp4"
    video_path = os.path.join(settings.GENERATED_DIR, video_file_name)
    
    avatar = db.query(Avatar).filter(Avatar.id == conversation.avatar_id).first()
    avatar_image = avatar.original_image_path if avatar else None
    
    if avatar_image and os.path.exists(audio_path):
        lip_sync = LipSyncService()
        try:
            await lip_sync.generate_lip_sync_video(
                image_path=avatar_image,
                audio_path=audio_path,
                output_path=video_path
            )
        except Exception as e:
            print(f"[LipSync] 视频生成失败: {e}")
            video_path = None
    else:
        video_path = None
    
    # 保存AI回复
    ai_msg = Message(
        role="assistant",
        content=response_text,
        audio_path=audio_path,
        video_path=video_path,
        emotion_tag=emotion,
        conversation_id=conversation.id
    )
    db.add(ai_msg)
    db.commit()
    db.refresh(ai_msg)
    
    return {
        "message": ai_msg,
        "audio_url": f"/uploads/generated/{audio_file_name}" if os.path.exists(audio_path) else None,
        "video_url": f"/uploads/generated/{video_file_name}" if video_path and os.path.exists(video_path) else None
    }

@router.websocket("/ws/{conversation_id}")
async def websocket_chat(
    websocket: WebSocket,
    conversation_id: int,
    db: Session = Depends(get_db)
):
    """WebSocket实时对话"""
    await manager.connect(websocket, conversation_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            message_text = data.get("message", "")
            
            conversation = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                await websocket.send_json({"error": "对话不存在"})
                continue
            
            # 保存用户消息
            user_msg = Message(
                role="user",
                content=message_text,
                conversation_id=conversation.id
            )
            db.add(user_msg)
            db.commit()
            
            # 构建历史
            messages = [{"role": "system", "content": conversation.system_prompt}]
            for msg in conversation.messages[-20:]:
                if msg.role in ["user", "assistant"]:
                    messages.append({"role": msg.role, "content": msg.content})
            
            # 流式生成回复
            llm_service = LLMService()
            response_text = ""
            
            async for chunk in llm_service.chat_stream(messages):
                response_text += chunk
                await websocket.send_json({
                    "type": "stream",
                    "content": chunk,
                    "done": False
                })
            
            # 生成语音
            voice = db.query(Voice).filter(Voice.id == conversation.voice_id).first()
            tts_service = TTSService()
            audio_file_name = f"{uuid.uuid4().hex}.mp3"
            audio_path = os.path.join(settings.GENERATED_DIR, audio_file_name)
            
            if voice and voice.source == "cloned" and voice.cloned_voice_id:
                ref_audio = voice.reference_audio_path if voice.reference_audio_path else None
                prompt = "参考音频"
                if voice.tts_config and isinstance(voice.tts_config, dict):
                    prompt = voice.tts_config.get("prompt_text", "参考音频")
                await tts_service.synthesize_with_cloned(
                    text=response_text,
                    voice_id=voice.cloned_voice_id,
                    output_path=audio_path,
                    ref_audio_path=ref_audio,
                    prompt_text=prompt
                )
            else:
                edge_voice = "zh-CN-XiaoxiaoNeural"
                if voice and voice.tts_config and isinstance(voice.tts_config, dict):
                    edge_voice = voice.tts_config.get("edge_voice_name", "zh-CN-XiaoxiaoNeural")
                await tts_service.synthesize_with_edge(
                    text=response_text,
                    output_path=audio_path,
                    voice_name=edge_voice
                )
            
            # 生成口型同步视频
            video_file_name = f"{uuid.uuid4().hex}.mp4"
            video_path = os.path.join(settings.GENERATED_DIR, video_file_name)
            
            avatar = db.query(Avatar).filter(Avatar.id == conversation.avatar_id).first()
            avatar_image = avatar.original_image_path if avatar else None
            
            if avatar_image and os.path.exists(audio_path):
                lip_sync = LipSyncService()
                try:
                    await lip_sync.generate_lip_sync_video(
                        image_path=avatar_image,
                        audio_path=audio_path,
                        output_path=video_path
                    )
                except Exception as e:
                    print(f"[LipSync] 视频生成失败: {e}")
                    video_path = None
            else:
                video_path = None
            
            # 保存AI回复
            ai_msg = Message(
                role="assistant",
                content=response_text,
                audio_path=audio_path,
                video_path=video_path,
                emotion_tag=emotion,
                conversation_id=conversation.id
            )
            db.add(ai_msg)
            db.commit()
            
            # 发送完成消息
            await websocket.send_json({
                "type": "complete",
                "content": response_text,
                "audio_url": f"/uploads/generated/{audio_file_name}",
                "video_url": f"/uploads/generated/{video_file_name}" if video_path and os.path.exists(video_path) else None,
                "emotion": emotion,
                "done": True
            })
    
    except WebSocketDisconnect:
        manager.disconnect(conversation_id)
