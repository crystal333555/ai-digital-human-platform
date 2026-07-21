import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Card, Button, Input, Select, Form, Row, Col, message, Progress,
  Steps, List, Tag, Space, Typography, Divider, Modal, Empty, Spin,
  Image as AntImage, Tooltip, Radio, Upload
} from 'antd'
import {
  VideoCameraOutlined, PlayCircleOutlined, DeleteOutlined,
  FileTextOutlined, CheckCircleOutlined, ClockCircleOutlined,
  CloseCircleOutlined, LoadingOutlined, ReloadOutlined,
  UserOutlined, BgColorsOutlined, EyeOutlined, UploadOutlined, SoundOutlined
} from '@ant-design/icons'
import { api, avatarAPI, voiceAPI, voiceLibAPI } from '../services/api'
import axios from 'axios'

const { TextArea } = Input
const { Title, Text, Paragraph } = Typography

const SPEECH_API = '/speech'

export default function SpeechVideo() {
  const [form] = Form.useForm()
  const [avatars, setAvatars] = useState([])
  const [voices, setVoices] = useState([])
  const [presetVoices, setPresetVoices] = useState([])
  const [backgrounds, setBackgrounds] = useState([])
  const [generating, setGenerating] = useState(false)
  const [tasks, setTasks] = useState(() => {
    try {
      const saved = localStorage.getItem('speech_tasks')
      return saved ? JSON.parse(saved) : []
    } catch { return [] }
  })
  const [polling, setPolling] = useState(null)
  const [previewVideo, setPreviewVideo] = useState(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [selectedAvatar, setSelectedAvatar] = useState(null)
  const [selectedBg, setSelectedBg] = useState('transparent')
  const [previewingVoice, setPreviewingVoice] = useState(null)
  const pollTimerRef = useRef(null)
  const avatarScale = Form.useWatch('avatar_scale', form)

  // 持久化任务列表
  useEffect(() => {
    localStorage.setItem('speech_tasks', JSON.stringify(tasks))
  }, [tasks])

  // 页面加载时恢复未完成任务的轮询
  useEffect(() => {
    const pending = tasks.filter(t => t.status === 'pending' || t.status === 'processing')
    if (pending.length > 0 && !pollTimerRef.current) {
      pollTimerRef.current = setInterval(async () => {
        const updated = [...tasks]
        let changed = false
        for (let i = 0; i < updated.length; i++) {
          if (updated[i].status === 'pending' || updated[i].status === 'processing') {
            try {
              const res = await axios.get(`/api/v1/speech/status/${updated[i].task_id}`)
              if (res.data.status !== updated[i].status) {
                updated[i] = { ...updated[i], ...res.data }
                changed = true
              }
              if (res.data.status === 'completed' || res.data.status === 'error') {
                // 任务完成，停止轮询
              }
            } catch {}
          }
        }
        if (changed) setTasks(updated)
        // 如果没有未完成的任务了，停止轮询
        if (!updated.some(t => t.status === 'pending' || t.status === 'processing')) {
          clearInterval(pollTimerRef.current)
          pollTimerRef.current = null
        }
      }, 5000)
    }
    return () => {
      if (pollTimerRef.current && !tasks.some(t => t.status === 'pending' || t.status === 'processing')) {
        clearInterval(pollTimerRef.current)
        pollTimerRef.current = null
      }
    }
  }, [])

  const loadData = useCallback(async () => {
    try {
      const [avatarRes, voiceRes, presetRes, bgRes] = await Promise.all([
        avatarAPI.list(),
        voiceAPI.list(),
        voiceLibAPI.presets(),
        avatarAPI.backgrounds(),
      ])
      const avatarData = avatarRes.data
      const voiceData = voiceRes.data
      const presetData = presetRes.data
      setAvatars(Array.isArray(avatarData) ? avatarData : (avatarData?.items || []))
      setVoices(Array.isArray(voiceData) ? voiceData : (voiceData?.items || []))
      setPresetVoices(presetData?.voices || [])
      setBackgrounds(bgRes.data?.backgrounds || [])
    } catch (e) {
      console.error('加载数据失败:', e)
      message.error('加载数据失败: ' + (e.response?.data?.detail || e.message))
    }
  }, [])

  useEffect(() => {
    loadData()
    loadTasks()
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current)
    }
  }, [loadData])

  // 选中形象时更新预览
  const handleAvatarChange = (avatarId) => {
    const avatar = avatars.find(a => a.id === avatarId)
    setSelectedAvatar(avatar || null)
  }

  // 试听音色
  const handlePreviewVoice = async (type, voiceId) => {
    const key = `${type}-${voiceId}`
    setPreviewingVoice(key)
    try {
      let res
      if (type === 'my') {
        res = await voiceAPI.preview(voiceId)
      } else {
        res = await voiceLibAPI.testPreset(voiceId)
      }
      if (res.data?.audio_url) {
        let url = res.data.audio_url
        if (url.startsWith('/data/') || url.startsWith('/uploads/')) {
          url = `http://localhost:8000${url}`
        }
        const audio = new Audio(url)
        audio.play()
        audio.onended = () => setPreviewingVoice(null)
        audio.onerror = () => { message.error('播放失败'); setPreviewingVoice(null) }
      } else {
        message.warning('试听失败')
        setPreviewingVoice(null)
      }
    } catch (err) {
      message.error('试听失败: ' + (err.response?.data?.detail || err.message))
      setPreviewingVoice(null)
    }
  }

  // 上传自定义背景
  const handleUploadBg = async (file) => {
    const formData = new FormData()
    formData.append('file', file)
    try {
      message.loading('上传中...', 0)
      const res = await axios.post('/api/v1/avatars/backgrounds/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      message.destroy()
      if (res.data?.success) {
        message.success('背景上传成功')
        setBackgrounds(prev => [...prev, { name: res.data.name, url: res.data.url }])
        setSelectedBg(res.data.url)
      }
    } catch (err) {
      message.destroy()
      message.error('上传失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  // 获取预览图片URL
  const getAvatarPreviewUrl = (avatar) => {
    if (!avatar) return null
    // 透明背景时显示透明人物图，否则也显示透明图（背景由容器提供）
    const imgPath = avatar.transparent_image_path || avatar.original_image_path
    if (!imgPath) return null
    if (imgPath.startsWith('http')) return imgPath
    if (imgPath.startsWith('/uploads/')) return `http://localhost:8000${imgPath}`
    if (imgPath.startsWith('../uploads/')) return `http://localhost:8000/${imgPath.replace('../', '')}`
    return `http://localhost:8000/${imgPath}`
  }

  // 获取背景图URL
  const getBgUrl = (bgUrl) => {
    if (!bgUrl) return null
    if (bgUrl.startsWith('http')) return bgUrl
    return `http://localhost:8000${bgUrl}`
  }

  const loadTasks = async () => {
    try {
      const res = await api.get(`${SPEECH_API}/list`)
      setTasks(res.data.tasks || [])
    } catch (e) {
      console.error('加载任务列表失败', e)
    }
  }

  const startPolling = (taskId) => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current)
    setPolling(taskId)
    pollTimerRef.current = setInterval(async () => {
      try {
        const res = await api.get(`${SPEECH_API}/status/${taskId}`)
        const task = res.data
        setTasks(prev => prev.map(t => t.task_id === taskId ? {
          ...t,
          status: task.status,
          message: task.message,
          segments: task.segments,
          output_video: task.output_video,
        } : t))

        if (task.status === 'completed' || task.status === 'error') {
          clearInterval(pollTimerRef.current)
          pollTimerRef.current = null
          setPolling(null)
          if (task.status === 'completed') {
            message.success('演讲视频生成完成！')
          } else {
            message.error('生成失败: ' + task.message)
          }
        }
      } catch (e) {
        console.error('轮询失败', e)
      }
    }, 3000)
  }

  const handleGenerate = async (values) => {
    if (!values.text || values.text.trim().length < 5) {
      message.warning('请输入至少5个字符的演讲内容')
      return
    }

    const voiceConfig = values.voice_config ? JSON.parse(values.voice_config) : null
    const submitData = {
      avatar_id: values.avatar_id,
      voice_id: voiceConfig?.type === 'my' ? voiceConfig.voice_id : null,
      voice_config: voiceConfig,
      text: values.text,
      title: values.title || '演讲视频',
      segment_strategy: values.segment_strategy || 'sentence',
      model: form.getFieldValue('model') || 'musetalk',
      background: selectedBg,
      avatar_scale: form.getFieldValue('avatar_scale') || 1.0,
      target_resolution: form.getFieldValue('target_resolution') || '1024x1024',
    }

    setGenerating(true)
    try {
      const res = await api.post(`${SPEECH_API}/generate`, submitData)
      const newTask = res.data
      setTasks(prev => [{
        task_id: newTask.task_id,
        status: newTask.status,
        message: newTask.message,
        title: values.title || '演讲视频',
        segment_count: newTask.segments.length,
        current_segment: -1,
        output_video: null,
        segments: newTask.segments,
      }, ...prev])
      message.success('任务已创建，开始生成...')
      startPolling(newTask.task_id)
      form.resetFields(['text', 'title'])
    } catch (e) {
      message.error('创建任务失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setGenerating(false)
    }
  }

  const handleDelete = async (taskId) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后视频文件将无法恢复，确定要删除吗？',
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await api.delete(`${SPEECH_API}/${taskId}`)
          setTasks(prev => prev.filter(t => t.task_id !== taskId))
          message.success('已删除')
        } catch (e) {
          message.error('删除失败')
        }
      }
    })
  }

  const handlePreview = (videoPath) => {
    if (!videoPath) return
    let url = videoPath
    if (videoPath.startsWith('/data/') || videoPath.startsWith('/uploads/')) {
      url = `http://localhost:8000${videoPath}`
    }
    setPreviewVideo(url)
    setPreviewOpen(true)
  }

  const formatTime = (timestamp) => {
    if (!timestamp) return ''
    const d = new Date(typeof timestamp === 'number' ? timestamp * 1000 : timestamp)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  const formatSize = (bytes) => {
    if (!bytes) return ''
    if (bytes < 1024) return bytes + 'B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
    return (bytes / 1024 / 1024).toFixed(1) + 'MB'
  }

  const getStatusTag = (status) => {
    const map = {
      pending: { color: 'default', icon: <ClockCircleOutlined />, text: '等待中' },
      processing: { color: 'processing', icon: <LoadingOutlined />, text: '生成中' },
      completed: { color: 'success', icon: <CheckCircleOutlined />, text: '已完成' },
      error: { color: 'error', icon: <CloseCircleOutlined />, text: '失败' },
      done: { color: 'success', icon: <CheckCircleOutlined />, text: '完成' },
    }
    const cfg = map[status] || map.pending
    return <Tag color={cfg.color} icon={cfg.icon}>{cfg.text}</Tag>
  }

  const getProgress = (task) => {
    if (!task.segments) return 0
    const done = task.segments.filter(s => s.status === 'done' || s.status === 'completed').length
    return Math.round((done / task.segments.length) * 100)
  }

  const sampleTexts = [
    '大家好，欢迎来到AI数字人平台。今天我将为大家介绍我们的最新技术成果。通过人工智能技术，我们可以创建逼真的数字人形象，实现自然流畅的语音对话。这项技术将广泛应用于教育培训、企业宣传、虚拟主播等多个领域。让我们共同期待AI数字人带来的无限可能！',
    '各位领导、各位同事，大家好。今天我汇报的主题是数字化转型与企业创新。在当前数字经济时代，企业必须拥抱技术变革。我们将通过三个方面的努力来推进数字化转型：第一，建设智能化的基础设施；第二，培养数字化人才队伍；第三，构建数据驱动的决策体系。谢谢大家！',
  ]

  return (
    <div>
      <Title level={3}>
        <VideoCameraOutlined /> 数字人演讲视频生成
      </Title>
      <Paragraph type="secondary">
        输入演讲文本，选择数字人形象和背景，系统自动生成口型同步的演讲视频。
      </Paragraph>

      <Row gutter={24}>
        {/* 左侧：生成表单 */}
        <Col span={16}>
          <Card title={<><FileTextOutlined /> 演讲配置</>} bordered>
            <Form form={form} layout="vertical" onFinish={handleGenerate}>
              <Form.Item label="演讲标题" name="title">
                <Input placeholder="请输入演讲标题（可选）" />
              </Form.Item>

              {/* 数字人形象预览 + 背景选择 */}
              <Row gutter={16}>
                <Col span={10}>
                  <Form.Item label="选择数字人形象" name="avatar_id" rules={[{ required: true, message: '请选择形象' }]}>
                    <Select 
                      placeholder="请选择数字人形象"
                      onChange={handleAvatarChange}
                    >
                      {avatars.map(a => (
                        <Select.Option key={a.id} value={a.id}>
                          <Space>
                            {a.name}
                            {a.transparent_image_path && <Tag color="green" style={{fontSize:10}}>已去背景</Tag>}
                          </Space>
                        </Select.Option>
                      ))}
                    </Select>
                  </Form.Item>

                  {/* 高级参数 */}
                  <Row gutter={8} style={{ marginBottom: 12 }}>
                    <Col span={12}>
                      <Form.Item label="视频分辨率" name="target_resolution" initialValue="1024x1024" style={{ marginBottom: 0 }}>
                        <Select size="small">
                          <Select.Option value="512x512">512x512（快速）</Select.Option>
                          <Select.Option value="1024x1024">1024x1024（标准）</Select.Option>
                          <Select.Option value="1080p">1080p（高清横屏）</Select.Option>
                          <Select.Option value="1080x1920">1080x1920（竖屏）</Select.Option>
                        </Select>
                      </Form.Item>
                    </Col>
                    <Col span={12}>
                      <Form.Item label="数字人占比" name="avatar_scale" initialValue={1.0} style={{ marginBottom: 0 }}>
                        <Select size="small">
                          <Select.Option value={0.5}>50%（小）</Select.Option>
                          <Select.Option value={0.7}>70%（中）</Select.Option>
                          <Select.Option value={0.85}>85%（大）</Select.Option>
                          <Select.Option value={1.0}>100%（满屏）</Select.Option>
                        </Select>
                      </Form.Item>
                    </Col>
                  </Row>

                  {/* 形象预览 */}
                  {selectedAvatar && (
                    <Card 
                      size="small" 
                      style={{ 
                        marginTop: -8, marginBottom: 16,
                        padding: 0,
                        overflow: 'hidden',
                      }}
                      bodyStyle={{ padding: 0 }}
                    >
                      <div style={{
                        position: 'relative',
                        width: '100%',
                        height: 220,
                        backgroundImage: selectedBg === 'transparent' 
                          ? 'repeating-conic-gradient(#f0f0f0 0% 25%, #ffffff 0% 50%) 50% / 20px 20px'
                          : `url(${getBgUrl(selectedBg)})`,
                        backgroundSize: 'cover',
                        backgroundPosition: 'center',
                        display: 'flex',
                        alignItems: 'flex-end',
                        justifyContent: 'center',
                      }}>
                        <img
                          src={getAvatarPreviewUrl(selectedAvatar)}
                          style={{ 
                            height: `${(avatarScale || 1.0) * 100}%`, 
                            width: 'auto',
                            objectFit: 'contain',
                            transition: 'all 0.3s ease',
                          }}
                          alt="数字人预览"
                        />
                      </div>
                      <div style={{ padding: '4px 8px', textAlign: 'center', background: '#fafafa' }}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {selectedBg === 'transparent' ? '✅ 透明背景（用于PPT叠加）' : '🎨 背景效果预览'}
                        </Text>
                      </div>
                    </Card>
                  )}
                </Col>

                <Col span={14}>
                  <Form.Item label={<><BgColorsOutlined /> 选择背景</>}>
                    <div style={{ marginBottom: 8 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>点击选择背景，或上传自定义图片</Text>
                    </div>
                    <Row gutter={[8, 8]}>
                      <Col span={6}>
                        <div
                          onClick={() => setSelectedBg('transparent')}
                          style={{
                            cursor: 'pointer', borderRadius: 8, overflow: 'hidden',
                            border: selectedBg === 'transparent' ? '2px solid #5b5bd6' : '2px solid #e8e8f0',
                            background: 'repeating-conic-gradient(#f0f0f5 0% 25%, #ffffff 0% 50%) 50% / 16px 16px',
                            height: 60, display: 'flex', alignItems: 'center', justifyContent: 'center',
                          }}
                        >
                          <Text style={{ fontSize: 11 }}>透明</Text>
                        </div>
                      </Col>
                      {backgrounds.map(bg => (
                        <Col span={6} key={bg.name}>
                          <div
                            onClick={() => setSelectedBg(bg.url)}
                            style={{
                              cursor: 'pointer', borderRadius: 8, overflow: 'hidden',
                              border: selectedBg === bg.url ? '2px solid #5b5bd6' : '2px solid #e8e8f0',
                              height: 60, position: 'relative',
                            }}
                          >
                            <img src={getBgUrl(bg.url)} style={{ width: '100%', height: '100%', objectFit: 'cover' }} alt={bg.name} />
                            <Text style={{ position: 'absolute', bottom: 2, left: 4, fontSize: 10, color: '#fff', textShadow: '0 1px 2px rgba(0,0,0,0.6)' }}>
                              {bg.name}
                            </Text>
                          </div>
                        </Col>
                      ))}
                      <Col span={6}>
                        <Upload
                          beforeUpload={(file) => {
                            handleUploadBg(file)
                            return false
                          }}
                          accept="image/*"
                          showUploadList={false}
                        >
                          <div style={{
                            cursor: 'pointer', borderRadius: 8, border: '2px dashed #d1d5e0',
                            height: 60, display: 'flex', alignItems: 'center', justifyContent: 'center',
                            flexDirection: 'column',
                          }}>
                            <UploadOutlined style={{ fontSize: 20, color: '#9ca3af' }} />
                            <Text style={{ fontSize: 10, color: '#9ca3af' }}>上传</Text>
                          </div>
                        </Upload>
                      </Col>
                    </Row>
                  </Form.Item>

                  <Form.Item label="生成模式" name="model" initialValue="musetalk">
                  <Select>
                    <Select.Option value="musetalk">⚡ 快速模式（MuseTalk）</Select.Option>
                    <Select.Option value="liveportrait">✨ 高质量模式（LivePortrait）</Select.Option>
                  </Select>
                </Form.Item>

                <Form.Item label="选择音色" name="voice_config" rules={[{ required: true, message: '请选择音色' }]}>
                    <Select placeholder="请选择音色" optionLabelProp="label">
                      <Select.OptGroup label="我的音色">
                        {voices.map(v => (
                          <Select.Option key={`my-${v.id}`} value={JSON.stringify({ type: 'my', id: v.id, voice_id: v.id })} label={v.name}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span>{v.name} {v.source === 'cloned' ? <Tag color="blue" style={{ fontSize: 10 }}>克隆</Tag> : <Tag color="green" style={{ fontSize: 10 }}>混合</Tag>}</span>
                              <Button
                                type="text"
                                size="small"
                                icon={<SoundOutlined />}
                                onClick={(e) => { e.stopPropagation(); handlePreviewVoice('my', v.id) }}
                                loading={previewingVoice === `my-${v.id}`}
                              />
                            </div>
                          </Select.Option>
                        ))}
                      </Select.OptGroup>
                      <Select.OptGroup label="音色库">
                        {presetVoices.map(v => (
                          <Select.Option key={`preset-${v.id}`} value={JSON.stringify({ type: 'preset', id: v.id, edge_voice: v.edge_tts_voice, rate: v.rate, pitch: v.pitch })} label={v.name}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <Space>
                                <span>{v.name}</span>
                                <Tag color="purple" style={{ fontSize: 10 }}>{v.category}</Tag>
                              </Space>
                              <Button
                                type="text"
                                size="small"
                                icon={<SoundOutlined />}
                                onClick={(e) => { e.stopPropagation(); handlePreviewVoice('preset', v.id) }}
                                loading={previewingVoice === `preset-${v.id}`}
                              />
                            </div>
                          </Select.Option>
                        ))}
                      </Select.OptGroup>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item label="演讲内容" name="text" rules={[{ required: true, message: '请输入演讲内容' }]}>
                <TextArea
                  rows={8}
                  placeholder="请输入或粘贴演讲文本...&#10;系统将自动分段，逐段生成语音和视频，最后拼接为完整演讲视频。"
                  showCount
                  maxLength={5000}
                />
              </Form.Item>

              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item label="分段策略" name="segment_strategy" initialValue="sentence">
                    <Select>
                      <Select.Option value="sentence">按句子分段（推荐）</Select.Option>
                      <Select.Option value="paragraph">按段落分段</Select.Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={16}>
                  <Form.Item label=" " colon={false}>
                    <Button type="primary" htmlType="submit" loading={generating} icon={<VideoCameraOutlined />} size="large" block>
                      生成演讲视频
                    </Button>
                  </Form.Item>
                </Col>
              </Row>

              <Divider />
              <Text type="secondary">快速示例：</Text>
              <Space wrap style={{ marginTop: 8 }}>
                {sampleTexts.map((t, i) => (
                  <Button key={i} size="small" onClick={() => form.setFieldValue('text', t)}>
                    示例 {i + 1}
                  </Button>
                ))}
              </Space>
            </Form>
          </Card>
        </Col>

        {/* 右侧：任务列表 */}
        <Col span={8}>
          <Card
            title={<><ClockCircleOutlined /> 生成任务</>}
            extra={<Button size="small" icon={<ReloadOutlined />} onClick={loadTasks}>刷新</Button>}
            bordered
            style={{ maxHeight: '80vh', overflow: 'auto' }}
          >
            {tasks.length === 0 ? (
              <Empty description="暂无任务" />
            ) : (
              <List
                dataSource={tasks}
                renderItem={(task) => (
                  <List.Item
                    actions={[
                      task.output_video && (
                        <Button key="play" type="link" icon={<PlayCircleOutlined />} onClick={() => handlePreview(task.output_video)}>
                          播放
                        </Button>
                      ),
                      <Button key="delete" type="link" danger icon={<DeleteOutlined />} onClick={() => handleDelete(task.task_id)}>
                        删除
                      </Button>,
                    ].filter(Boolean)}
                  >
                    <List.Item.Meta
                      title={<Space><Text strong>{task.title || '演讲视频'}</Text>{getStatusTag(task.status)}</Space>}
                      description={
                        <div>
                          <Text type="secondary">{task.message}</Text>
                          {(task.file_size || task.file_mtime) && (
                            <div style={{ marginTop: 2, fontSize: 12, color: '#999' }}>
                              {task.file_size && <span>{formatSize(task.file_size)}</span>}
                              {task.file_mtime && <span style={{ marginLeft: 8 }}>{formatTime(task.file_mtime)}</span>}
                            </div>
                          )}
                          {(task.status === 'processing' || task.status === 'pending') && (
                            <Progress percent={getProgress(task)} size="small" status="active" format={() => `${task.current_segment + 1 >= 0 ? task.current_segment + 1 : 0}/${task.segment_count}`} />
                          )}
                        </div>
                      }
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>

      {/* 视频预览弹窗 */}
      <Modal open={previewOpen} title="演讲视频预览" footer={null} onCancel={() => { setPreviewOpen(false); setPreviewVideo(null) }} width={800} destroyOnClose>
        {previewVideo && <video src={previewVideo} controls autoPlay style={{ width: '100%', borderRadius: 8 }} />}
      </Modal>
    </div>
  )
}
