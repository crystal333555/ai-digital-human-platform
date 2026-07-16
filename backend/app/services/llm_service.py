import os
import httpx
from typing import List, Dict, AsyncGenerator, Optional
from openai import AsyncOpenAI

from app.config import settings

class LLMService:
    """LLM对话服务，支持多厂商切换"""
    
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.client = None
        self._init_client()
    
    def _init_client(self):
        if self.provider == "openai":
            self.client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY or "sk-demo-key",
                base_url=settings.OPENAI_BASE_URL
            )
            self.model = settings.OPENAI_MODEL
        elif self.provider == "qwen":
            self.client = AsyncOpenAI(
                api_key=settings.QWEN_API_KEY or "",
                base_url=settings.QWEN_BASE_URL
            )
            self.model = settings.QWEN_MODEL
        else:
            # 默认OpenAI兼容格式
            self.client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY or "sk-demo-key",
                base_url=settings.OPENAI_BASE_URL
            )
            self.model = settings.OPENAI_MODEL
    
    async def chat(self, messages: List[Dict]) -> tuple:
        """非流式对话，返回完整回复和情感标签"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.8,
                max_tokens=800
            )
            
            content = response.choices[0].message.content
            
            # 简单情感分析 (基于关键词)
            emotion = await self._analyze_emotion(content)
            
            return content, emotion
        except Exception as e:
            # 降级方案：返回预设回复
            return f"抱歉，我暂时无法连接到大脑，请稍后重试。错误: {str(e)}", "neutral"
    
    async def chat_stream(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        """流式对话，逐字返回"""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.8,
                max_tokens=800,
                stream=True
            )
            
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            yield f"连接出错: {str(e)}"
    
    async def analyze_emotion(self, text: str) -> str:
        """分析文本情感"""
        return self._analyze_emotion(text)
    
    def _analyze_emotion(self, text: str) -> str:
        """基于关键词的简易情感分析"""
        text_lower = text.lower()
        
        happy_keywords = ['开心', '高兴', '棒', '好', '喜欢', '谢谢', '哈哈', '笑', '开心', '愉快', '快乐']
        sad_keywords = ['难过', '伤心', '抱歉', '遗憾', '对不起', '悲伤', '痛苦']
        angry_keywords = ['生气', '愤怒', '讨厌', '烦', '气', '怒', '不满']
        surprised_keywords = ['惊讶', '哇', '天哪', '没想到', '竟然', '震惊']
        
        for kw in happy_keywords:
            if kw in text_lower:
                return "happy"
        for kw in sad_keywords:
            if kw in text_lower:
                return "sad"
        for kw in angry_keywords:
            if kw in text_lower:
                return "angry"
        for kw in surprised_keywords:
            if kw in text_lower:
                return "surprised"
        
        return "neutral"
    
    async def generate_character_prompt(
        self,
        name: str,
        personality: str,
        background: str,
        speaking_style: str
    ) -> str:
        """生成角色系统Prompt"""
        prompt = f"""你是数字人{name}。

【背景设定】
{background}

【性格特点】
{personality}

【说话风格】
{speaking_style}

【交流规则】
1. 保持角色设定的一致性，不要跳出角色
2. 使用自然、口语化的中文交流
3. 适当使用表情和语气词增加生动感
4. 回答控制在100字以内，保持简洁
5. 如果用户问题涉及危险或不当内容，礼貌拒绝并引导到正面话题

请始终保持以上角色设定与用户对话。"""
        return prompt
