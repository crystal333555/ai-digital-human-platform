import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Card, Button, Input, Select, Form, Row, Col, message, Progress,
  Steps, List, Tag, Space, Typography, Divider, Modal, Empty, Spin
} from 'antd'
import {
  VideoCameraOutlined, PlayCircleOutlined, DeleteOutlined,
  FileTextOutlined, CheckCircleOutlined, ClockCircleOutlined,
  CloseCircleOutlined, LoadingOutlined, ReloadOutlined
} from '@ant-design/icons'
import { api, avatarAPI, voiceAPI, voiceLibAPI } from '../services/api'

const { TextArea } = Input
const { Title, Text, Paragraph } = Typography

const SPEECH_API = '/speech'

export default function SpeechVideo() {
  const [form] = Form.useForm()
  const [avatars, setAvatars] = useState([])
  const [voices, setVoices] = useState([])
  const [presetVoices, setPresetVoices] = useState([])
  const [generating, setGenerating] = useState(false)
  const [tasks, setTasks] = useState([])
  const [polling, setPolling] = useState(null)
  const [previewVideo, setPreviewVideo] = useState(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const pollTimerRef = useRef(null)

  // 加载形象和音色列表
  const loadData = useCallback(async () => {
    try {
      const [avatarRes, voiceRes, presetRes] = await Promise.all([
        avatarAPI.list(),
        voiceAPI.list(),
        voiceLibAPI.presets(),
      ])
      const avatarData = avatarRes.data
      const voiceData = voiceRes.data
      const presetData = presetRes.data
      console.log('Avatar API response:', avatarData)
      console.log('Voice API response:', voiceData)
      console.log('Preset voices response:', presetData)
      setAvatars(Array.isArray(avatarData) ? avatarData : (avatarData?.items || []))
      setVoices(Array.isArray(voiceData) ? voiceData : (voiceData?.items || []))
      setPresetVoices(presetData?.voices || [])
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

  // 加载任务列表
  const loadTasks = async () => {
    try {
      const res = await api.get(`${SPEECH_API}/list`)
      setTasks(res.data.tasks || [])
    } catch (e) {
      console.error('加载任务列表失败', e)
    }
  }

  // 轮询单个任务状态
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

  // 提交生成
  const handleGenerate = async (values) => {
    if (!values.text || values.text.trim().length < 5) {
      message.warning('请输入至少5个字符的演讲内容')
      return
    }

    // 解析音色配置
    const voiceConfig = values.voice_config ? JSON.parse(values.voice_config) : null
    const submitData = {
      avatar_id: values.avatar_id,
      voice_id: voiceConfig?.type === 'my' ? voiceConfig.voice_id : null,
      voice_config: voiceConfig,
      text: values.text,
      title: values.title || '演讲视频',
      segment_strategy: values.segment_strategy || 'sentence',
      model: values.model || 'wav2lip',
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

  // 删除任务（带确认）
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

  // 预览视频（使用相对路径，通过Vite代理）
  const handlePreview = (videoPath) => {
    if (!videoPath) return
    // 确保 URL 以 / 开头，通过 Vite 代理转发
    const url = videoPath.startsWith('/') ? videoPath : '/' + videoPath
    setPreviewVideo(url)
    setPreviewOpen(true)
  }

  // 格式化时间
  const formatTime = (timestamp) => {
    if (!timestamp) return ''
    const d = new Date(typeof timestamp === 'number' ? timestamp * 1000 : timestamp)
    return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
  }

  // 格式化文件大小
  const formatSize = (bytes) => {
    if (!bytes) return ''
    if (bytes < 1024) return bytes + 'B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB'
    return (bytes / 1024 / 1024).toFixed(1) + 'MB'
  }

  // 获取状态标签
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

  // 计算进度
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
        输入演讲文本或材料内容，系统将自动分段、逐段合成语音、生成口型同步视频，并拼接为完整演讲视频。
      </Paragraph>

      <Row gutter={24}>
        {/* 左侧：生成表单 */}
        <Col span={14}>
          <Card title={<><FileTextOutlined /> 演讲内容</>} bordered>
            <Form form={form} layout="vertical" onFinish={handleGenerate}>
              <Form.Item label="演讲标题" name="title">
                <Input placeholder="请输入演讲标题（可选）" />
              </Form.Item>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="选择数字人形象" name="avatar_id" rules={[{ required: true, message: '请选择形象' }]}>
                    <Select placeholder="请选择数字人形象">
                      {avatars.map(a => (
                        <Select.Option key={a.id} value={a.id}>{a.name}</Select.Option>
                      ))}
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="选择音色" name="voice_config" rules={[{ required: true, message: '请选择音色' }]}>
                    <Select placeholder="请选择音色" optionLabelProp="label">
                      <Select.OptGroup label="我的音色">
                        {voices.map(v => (
                          <Select.Option key={`my-${v.id}`} value={JSON.stringify({ type: 'my', id: v.id, voice_id: v.id })} label={v.name}>
                            {v.name} {v.source === 'cloned' ? <Tag color="blue">克隆</Tag> : <Tag color="green">预设</Tag>}
                          </Select.Option>
                        ))}
                        {voices.length === 0 && <Select.Option disabled value="">暂无音色，请先到音色管理添加</Select.Option>}
                      </Select.OptGroup>
                      <Select.OptGroup label="音色库">
                        {presetVoices.map(v => (
                          <Select.Option key={`preset-${v.id}`} value={JSON.stringify({ type: 'preset', id: v.id, edge_voice: v.edge_tts_voice, rate: v.rate, pitch: v.pitch })} label={v.name}>
                            <Space>
                              <span>{v.name}</span>
                              <Tag color="purple" style={{ fontSize: 10 }}>{v.category}</Tag>
                              <span style={{ color: '#999', fontSize: 11 }}>{v.description?.substring(0, 15)}...</span>
                            </Space>
                          </Select.Option>
                        ))}
                      </Select.OptGroup>
                    </Select>
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item label="演讲内容" name="text" rules={[{ required: true, message: '请输入演讲内容' }]}>
                <TextArea
                  rows={10}
                  placeholder="请输入或粘贴演讲文本/材料内容...&#10;系统将自动按句子分段，逐段生成语音和视频，最后拼接为完整演讲视频。"
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
                <Col span={8}>
                  <Form.Item label="口型模型" name="model" initialValue="wav2lip">
                    <Select>
                      <Select.Option value="wav2lip">Wav2Lip</Select.Option>
                      <Select.Option value="sadtalker">SadTalker</Select.Option>
                    </Select>
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label=" " colon={false}>
                    <Space>
                      <Button type="primary" htmlType="submit" loading={generating} icon={<VideoCameraOutlined />} size="large">
                        生成演讲视频
                      </Button>
                    </Space>
                  </Form.Item>
                </Col>
              </Row>

              <Divider />
              <Text type="secondary">快速示例：</Text>
              <Space wrap style={{ marginTop: 8 }}>
                {sampleTexts.map((t, i) => (
                  <Button
                    key={i}
                    size="small"
                    onClick={() => form.setFieldValue('text', t)}
                  >
                    示例 {i + 1}
                  </Button>
                ))}
              </Space>
            </Form>
          </Card>
        </Col>

        {/* 右侧：任务列表 */}
        <Col span={10}>
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
                        <Button
                          key="play"
                          type="link"
                          icon={<PlayCircleOutlined />}
                          onClick={() => handlePreview(task.output_video)}
                        >
                          播放
                        </Button>
                      ),
                      <Button
                        key="delete"
                        type="link"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => handleDelete(task.task_id)}
                      >
                        删除
                      </Button>,
                    ].filter(Boolean)}
                  >
                    <List.Item.Meta
                      title={
                        <Space>
                          <Text strong>{task.title || '演讲视频'}</Text>
                          {getStatusTag(task.status)}
                        </Space>
                      }
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
                            <Progress
                              percent={getProgress(task)}
                              size="small"
                              status="active"
                              format={() => `${task.current_segment + 1 >= 0 ? task.current_segment + 1 : 0}/${task.segment_count}`}
                            />
                          )}
                          {task.segments && task.status === 'processing' && (
                            <div style={{ marginTop: 4 }}>
                              {task.segments.map((seg, i) => (
                                <Tag
                                  key={i}
                                  color={seg.status === 'done' ? 'success' : seg.status === 'error' ? 'error' : seg.status === 'processing' ? 'processing' : 'default'}
                                  style={{ marginBottom: 2, fontSize: 11 }}
                                >
                                  {i + 1}: {seg.status === 'done' ? '✓' : seg.status === 'error' ? '✗' : seg.status === 'processing' ? '...' : '⏳'}
                                </Tag>
                              ))}
                            </div>
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
      <Modal
        open={previewOpen}
        title="演讲视频预览"
        footer={null}
        onCancel={() => { setPreviewOpen(false); setPreviewVideo(null) }}
        width={800}
        destroyOnClose
      >
        {previewVideo && (
          <video
            src={previewVideo}
            controls
            autoPlay
            style={{ width: '100%', borderRadius: 8 }}
          />
        )}
      </Modal>
    </div>
  )
}
