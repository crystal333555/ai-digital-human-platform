import React, { useState, useEffect, useRef } from 'react'
import { Card, Button, Input, Select, message, Avatar as AntAvatar, List, Tag, Space, Switch } from 'antd'
import { SendOutlined, AudioOutlined, StopOutlined, UserOutlined } from '@ant-design/icons'
import { chatAPI, avatarAPI, voiceAPI, createWebSocket } from '../services/api.js'

const { Option } = Select
const { TextArea } = Input
const API_BASE = 'http://localhost:8000'

function ChatPage() {
  const [conversations, setConversations] = useState([])
  const [avatars, setAvatars] = useState([])
  const [voices, setVoices] = useState([])
  const [currentConversation, setCurrentConversation] = useState(null)
  const [messages, setMessages] = useState([])
  const [inputText, setInputText] = useState('')
  const [loading, setLoading] = useState(false)
  const [isRecording, setIsRecording] = useState(false)
  const [show3D, setShow3D] = useState(false)
  const [selectedAvatar, setSelectedAvatar] = useState(null)
  const [selectedVoice, setSelectedVoice] = useState(null)
  const [systemPrompt, setSystemPrompt] = useState('')
  const [currentVideo, setCurrentVideo] = useState(null)
  const [currentAvatar, setCurrentAvatar] = useState(null)
  const wsRef = useRef(null)
  const chatEndRef = useRef(null)
  const videoRef = useRef(null)

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 自动播放视频
  useEffect(() => {
    if (currentVideo && videoRef.current) {
      videoRef.current.load()
      videoRef.current.play().catch(e => console.log('Auto-play blocked:', e))
    }
  }, [currentVideo])

  const loadData = async () => {
    try {
      const [avatarRes, voiceRes, convRes] = await Promise.all([
        avatarAPI.list(),
        voiceAPI.list(),
        chatAPI.listConversations()
      ])
      setAvatars(avatarRes.data || [])
      setVoices(voiceRes.data || [])
      setConversations(convRes.data || [])
    } catch (err) {
      console.error('加载数据失败', err)
    }
  }

  const getSelectedAvatarInfo = () => {
    return avatars.find(a => a.id === selectedAvatar)
  }

  const createConversation = async () => {
    if (!selectedAvatar || !selectedVoice) {
      message.warning('请先选择形象和音色')
      return
    }

    try {
      const res = await chatAPI.createConversation({
        avatar_id: selectedAvatar,
        voice_id: selectedVoice,
        system_prompt: systemPrompt || undefined,
      })
      
      const newConv = res.data
      setConversations([...conversations, newConv])
      setCurrentConversation(newConv.id)
      setMessages([])
      setCurrentAvatar(getSelectedAvatarInfo())
      message.success('对话创建成功')
    } catch (err) {
      message.error('创建对话失败')
    }
  }

  const sendMessage = async () => {
    if (!inputText.trim() || !currentConversation) return

    const userMsg = { role: 'user', content: inputText }
    setMessages(prev => [...prev, userMsg])
    setInputText('')
    setLoading(true)

    try {
      const res = await chatAPI.sendMessage({
        message: userMsg.content,
        conversation_id: currentConversation
      })

      const aiMsg = res.data.message
      const audioUrl = res.data.audio_url ? `${API_BASE}${res.data.audio_url}` : null
      const videoUrl = res.data.video_url ? `${API_BASE}${res.data.video_url}` : null
      
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: aiMsg.content,
        audio_url: audioUrl,
        video_url: videoUrl
      }])
      
      if (videoUrl) {
        setCurrentVideo(videoUrl)
      }
    } catch (err) {
      message.error('发送失败')
    } finally {
      setLoading(false)
    }
  }

  const startWebSocketChat = async () => {
    if (!currentConversation) return
    
    const ws = createWebSocket(currentConversation)
    wsRef.current = ws

    ws.onopen = () => {
      message.success('实时连接已建立')
    }

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data)
      if (data.type === 'stream') {
        // 流式更新
      } else if (data.type === 'complete') {
        const audioUrl = data.audio_url ? `${API_BASE}${data.audio_url}` : null
        const videoUrl = data.video_url ? `${API_BASE}${data.video_url}` : null
        
        setMessages(prev => [...prev, {
          role: 'assistant',
          content: data.content,
          audio_url: audioUrl,
          video_url: videoUrl
        }])
        
        if (videoUrl) {
          setCurrentVideo(videoUrl)
        }
        setLoading(false)
      }
    }

    ws.onerror = () => {
      message.error('连接出错')
    }
  }

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 200px)', gap: 16 }}>
      {/* 左侧配置面板 */}
      <Card title="对话配置" style={{ width: 280, minWidth: 280 }}>
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <label>选择形象：</label>
            <Select
              placeholder="选择数字人"
              style={{ width: '100%' }}
              onChange={(v) => { setSelectedAvatar(v); setCurrentAvatar(avatars.find(a => a.id === v)) }}
              value={selectedAvatar}
            >
              {avatars.map(a => (
                <Option key={a.id} value={a.id}>{a.name} ({a.style})</Option>
              ))}
            </Select>
          </div>
          <div>
            <label>选择音色：</label>
            <Select
              placeholder="选择音色"
              style={{ width: '100%' }}
              onChange={setSelectedVoice}
              value={selectedVoice}
            >
              {voices.map(v => (
                <Option key={v.id} value={v.id}>{v.name} ({v.source})</Option>
              ))}
            </Select>
          </div>
          <div>
            <label>角色设定：</label>
            <TextArea
              rows={3}
              placeholder="输入角色Prompt..."
              value={systemPrompt}
              onChange={e => setSystemPrompt(e.target.value)}
            />
          </div>
          <div>
            <label>3D模式：</label>
            <Switch checked={show3D} onChange={setShow3D} />
          </div>
          <Button type="primary" onClick={createConversation} block>
            创建对话
          </Button>
        </Space>
      </Card>

      {/* 中间聊天区域 */}
      <Card style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          <List
            dataSource={messages}
            renderItem={item => (
              <List.Item
                style={{
                  justifyContent: item.role === 'user' ? 'flex-end' : 'flex-start',
                  marginBottom: 8,
                }}
              >
                <div
                  style={{
                    maxWidth: '80%',
                    padding: '8px 12px',
                    borderRadius: 8,
                    background: item.role === 'user' ? '#1677ff' : '#f0f0f0',
                    color: item.role === 'user' ? '#fff' : '#333',
                  }}
                >
                  {item.content}
                  {item.video_url && (
                    <div style={{ marginTop: 8 }}>
                      <video
                        controls
                        src={item.video_url}
                        style={{ width: '100%', maxWidth: 240, borderRadius: 4 }}
                      />
                    </div>
                  )}
                  {!item.video_url && item.audio_url && (
                    <div style={{ marginTop: 8 }}>
                      <audio controls src={item.audio_url} style={{ width: '100%' }} />
                    </div>
                  )}
                </div>
              </List.Item>
            )}
          />
          <div ref={chatEndRef} />
        </div>

        <div style={{ display: 'flex', gap: 8, padding: '0 16px 16px' }}>
          <Input.TextArea
            rows={2}
            placeholder="输入消息..."
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            onPressEnter={e => { if (!e.shiftKey) { e.preventDefault(); sendMessage() } }}
          />
          <Button type="primary" icon={<SendOutlined />} onClick={sendMessage} loading={loading}>
            发送
          </Button>
        </div>
      </Card>

      {/* 右侧数字人视频展示区域 */}
      <Card title="数字人" style={{ width: 320, minWidth: 320 }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
          {/* 当前对话头像 */}
          {currentAvatar ? (
            <div style={{ textAlign: 'center' }}>
              <AntAvatar
                size={80}
                src={currentAvatar.original_image_path ? `${API_BASE}${currentAvatar.original_image_path}` : null}
                icon={!currentAvatar.original_image_path ? <UserOutlined /> : null}
              />
              <div style={{ marginTop: 8, fontWeight: 'bold' }}>{currentAvatar.name}</div>
            </div>
          ) : (
            <div style={{ textAlign: 'center', color: '#999', padding: 20 }}>
              请先选择形象并创建对话
            </div>
          )}

          {/* 数字人说话视频 */}
          {currentVideo ? (
            <div style={{ width: '100%', textAlign: 'center' }}>
              <video
                ref={videoRef}
                src={currentVideo}
                controls
                autoPlay
                loop={false}
                style={{ width: '100%', borderRadius: 8, maxHeight: 320 }}
              />
              <div style={{ marginTop: 4, fontSize: 12, color: '#888' }}>
                数字人正在说话...
              </div>
            </div>
          ) : currentAvatar ? (
            <div style={{ width: '100%', textAlign: 'center', padding: 20, color: '#ccc' }}>
              <img
                src={currentAvatar.original_image_path ? `${API_BASE}${currentAvatar.original_image_path}` : null}
                alt="数字人"
                style={{ width: '100%', borderRadius: 8, maxHeight: 320, objectFit: 'contain' }}
                onError={(e) => { e.target.style.display = 'none' }}
              />
              <div style={{ marginTop: 8, color: '#999' }}>
                发送消息，数字人开始说话
              </div>
            </div>
          ) : null}
        </div>
      </Card>
    </div>
  )
}

export default ChatPage
