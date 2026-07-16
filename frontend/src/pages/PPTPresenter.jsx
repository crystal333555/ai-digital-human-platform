import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Card, Button, Input, Select, Form, Row, Col, message, Progress,
  List, Tag, Space, Typography, Divider, Modal, Empty, Spin,
  Upload, Slider, Collapse, Image
} from 'antd'
import {
  FilePptOutlined, PlayCircleOutlined, EditOutlined,
  CheckCircleOutlined, ClockCircleOutlined, CloseCircleOutlined,
  LoadingOutlined, UploadOutlined, VideoCameraOutlined, DeleteOutlined
} from '@ant-design/icons'
import { api, avatarAPI, voiceLibAPI } from '../services/api'

const { TextArea } = Input
const { Title, Text } = Typography
const { Panel } = Collapse

const PPT_API = '/ppt'

export default function PPTPresenter() {
  const [form] = Form.useForm()
  const [avatars, setAvatars] = useState([])
  const [presetVoices, setPresetVoices] = useState([])
  const [projects, setProjects] = useState([])
  const [currentProject, setCurrentProject] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [tasks, setTasks] = useState([])
  const [polling, setPolling] = useState(null)
  const [previewVideo, setPreviewVideo] = useState(null)
  const [previewOpen, setPreviewOpen] = useState(false)
  const [editingSlide, setEditingSlide] = useState(null)
  const [editText, setEditText] = useState('')
  const pollTimerRef = useRef(null)

  const loadData = useCallback(async () => {
    try {
      const [avatarRes, presetRes, projectRes] = await Promise.all([
        avatarAPI.list(),
        voiceLibAPI.presets(),
        api.get(`${PPT_API}/projects`),
      ])
      setAvatars(Array.isArray(avatarRes.data) ? avatarRes.data : (avatarRes.data?.items || []))
      setPresetVoices(presetRes.data?.voices || [])
      setProjects(projectRes.data || [])
    } catch (e) {
      console.error('加载数据失败:', e)
    }
  }, [])

  useEffect(() => {
    loadData()
    loadTasks()
    return () => {
      if (pollTimerRef.current) clearInterval(pollTimerRef.current)
    }
  }, [loadData])

  const loadTasks = async () => {
    try {
      const res = await api.get(`${PPT_API}/tasks`)
      setTasks(res.data || [])
    } catch (e) {
      console.error('加载任务失败', e)
    }
  }

  const handleUpload = async (info) => {
    const file = info.file
    if (file.status !== 'uploading' && file.originFileObj) {
      setUploading(true)
      const formData = new FormData()
      formData.append('file', file.originFileObj)
      formData.append('name', file.name.replace(/\.(pptx|ppt)$/i, ''))

      try {
        const res = await api.post(`${PPT_API}/upload`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' }
        })
        message.success(`PPT解析成功，共 ${res.data.slide_count} 页`)
        setCurrentProject(res.data)
        loadData()
      } catch (e) {
        message.error('PPT上传失败: ' + (e.response?.data?.detail || e.message))
      } finally {
        setUploading(false)
      }
    }
  }

  const handleSelectProject = async (projectId) => {
    try {
      const res = await api.get(`${PPT_API}/projects/${projectId}`)
      setCurrentProject(res.data)
    } catch (e) {
      message.error('加载项目失败')
    }
  }

  const handleSaveNarration = async (slideId) => {
    try {
      await api.put(`${PPT_API}/projects/${currentProject.id}/slides/${slideId}`, {
        narration_text: editText
      })
      message.success('讲稿已保存')
      const res = await api.get(`${PPT_API}/projects/${currentProject.id}`)
      setCurrentProject(res.data)
      setEditingSlide(null)
    } catch (e) {
      message.error('保存失败')
    }
  }

  const handleGenerate = async () => {
    if (!currentProject) {
      message.warning('请先上传PPT')
      return
    }

    const values = form.getFieldsValue()
    const voiceConfig = values.voice_config ? JSON.parse(values.voice_config) : null

    setGenerating(true)
    try {
      const res = await api.post(`${PPT_API}/projects/${currentProject.id}/generate`, {
        avatar_id: values.avatar_id,
        voice_config: voiceConfig,
        layout_mode: values.layout_mode || 'bottom_bar',
        digital_human_position: values.position || 'bottom-center',
        digital_human_size: values.size_ratio || 0.25,
        transition: values.transition || 'fade',
        model: 'musetalk',
      })

      const newTask = res.data
      setTasks(prev => [newTask, ...prev])
      message.success('任务已创建')
      startPolling(newTask.task_id)
    } catch (e) {
      message.error('生成失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setGenerating(false)
    }
  }

  const startPolling = (taskId) => {
    if (pollTimerRef.current) clearInterval(pollTimerRef.current)
    setPolling(taskId)
    pollTimerRef.current = setInterval(async () => {
      try {
        const res = await api.get(`${PPT_API}/tasks/${taskId}`)
        const task = res.data
        setTasks(prev => prev.map(t => t.task_id === taskId ? task : t))

        if (task.status === 'completed' || task.status === 'error') {
          clearInterval(pollTimerRef.current)
          pollTimerRef.current = null
          setPolling(null)
          if (task.status === 'completed') {
            message.success('PPT讲解视频生成完成！')
            loadData()
          } else {
            message.error('生成失败: ' + task.message)
          }
        }
      } catch (e) {
        console.error('轮询失败', e)
      }
    }, 3000)
  }

  const handlePreview = (videoPath) => {
    if (!videoPath) return
    const url = videoPath.startsWith('/') ? videoPath : videoPath.replace(/\\/g, '/').replace(/^.*(uploads|data)/, '/$1')
    setPreviewVideo(`http://localhost:8000${url}`)
    setPreviewOpen(true)
  }

  const getSlideImageUrl = (slideImagePath) => {
    if (!slideImagePath) return null
    const url = slideImagePath.startsWith('/') ? slideImagePath : slideImagePath.replace(/\\/g, '/').replace(/^.*(uploads|data)/, '/$1')
    return `http://localhost:8000${url}`
  }

  const voiceOptions = [
    { label: '--- 音色库 ---', options: presetVoices.map(v => ({
      label: `${v.name}（${v.category}）`,
      value: JSON.stringify({ type: 'preset', id: v.id, edge_voice: v.edge_tts_voice }),
    }))},
  ]

  const getStatusTag = (status) => {
    const map = {
      draft: { color: 'default', text: '草稿' },
      generating: { color: 'processing', icon: <LoadingOutlined />, text: '生成中' },
      completed: { color: 'success', icon: <CheckCircleOutlined />, text: '已完成' },
      error: { color: 'error', icon: <CloseCircleOutlined />, text: '失败' },
      pending: { color: 'default', icon: <ClockCircleOutlined />, text: '等待中' },
      processing: { color: 'processing', icon: <LoadingOutlined />, text: '处理中' },
    }
    const cfg = map[status] || map.draft
    return <Tag color={cfg.color} icon={cfg.icon}>{cfg.text}</Tag>
  }

  return (
    <div style={{ padding: '0 8px' }}>
      <Title level={3}>
        <FilePptOutlined /> PPT数字人讲解
      </Title>

      <Row gutter={16}>
        {/* 左侧：上传+项目列表+配置 */}
        <Col span={10}>
          <Card title="上传PPT" size="small" style={{ marginBottom: 16 }}>
            <Upload
              accept=".pptx,.ppt"
              showUploadList={false}
              customRequest={({ file, onSuccess }) => {
                handleUpload({ file: { status: 'done', originFileObj: file } })
                onSuccess()
              }}
            >
              <Button icon={<UploadOutlined />} loading={uploading} type="primary" block>
                选择PPT文件 (.pptx)
              </Button>
            </Upload>
          </Card>

          {projects.length > 0 && (
            <Card title="已有项目" size="small" style={{ marginBottom: 16 }}>
              <List
                size="small"
                dataSource={projects}
                renderItem={p => (
                  <List.Item
                    style={{ cursor: 'pointer', background: currentProject?.id === p.id ? '#e6f7ff' : undefined }}
                    onClick={() => handleSelectProject(p.id)}
                    actions={[
                      getStatusTag(p.status),
                      p.output_video_path && (
                        <Button size="small" type="link" icon={<PlayCircleOutlined />}
                          onClick={(e) => { e.stopPropagation(); handlePreview(p.output_video_path) }}>
                          播放
                        </Button>
                      )
                    ]}
                  >
                    <List.Item.Meta
                      title={p.name}
                      description={`${p.slide_count || '?'} 页`}
                    />
                  </List.Item>
                )}
              />
            </Card>
          )}

          {currentProject && (
            <Card title="生成配置" size="small">
              <Form form={form} layout="vertical" size="small">
                <Form.Item label="数字人形象" name="avatar_id" rules={[{ required: true, message: '请选择' }]}>
                  <Select placeholder="选择数字人形象">
                    {avatars.map(a => (
                      <Select.Option key={a.id} value={a.id}>{a.name}</Select.Option>
                    ))}
                  </Select>
                </Form.Item>

                <Form.Item label="音色" name="voice_config">
                  <Select placeholder="选择音色" options={voiceOptions} />
                </Form.Item>

                <Form.Item label="布局模式" name="layout_mode" initialValue="bottom_bar">
                  <Select>
                    <Select.Option value="bottom_bar">底部横条（推荐）</Select.Option>
                    <Select.Option value="pip">画中画</Select.Option>
                  </Select>
                </Form.Item>

                <Form.Item label="数字人位置" name="position" initialValue="bottom-center">
                  <Select>
                    <Select.Option value="bottom-center">居中（推荐）</Select.Option>
                    <Select.Option value="bottom-left">左侧</Select.Option>
                    <Select.Option value="bottom-right">右侧</Select.Option>
                    <Select.Option value="bottom-follow">跟随内容</Select.Option>
                  </Select>
                </Form.Item>

                <Form.Item label="数字人大小" name="size_ratio" initialValue={0.25}>
                  <Slider min={0.15} max={0.4} step={0.05} marks={{ 0.15: '小', 0.25: '中', 0.4: '大' }} />
                </Form.Item>

                <Form.Item label="翻页过渡" name="transition" initialValue="fade">
                  <Select>
                    <Select.Option value="fade">淡入淡出</Select.Option>
                    <Select.Option value="slide">滑动</Select.Option>
                    <Select.Option value="none">无过渡</Select.Option>
                  </Select>
                </Form.Item>

                <Button type="primary" icon={<VideoCameraOutlined />} block
                  loading={generating} onClick={handleGenerate}>
                  生成PPT讲解视频
                </Button>
              </Form>
            </Card>
          )}
        </Col>

        {/* 右侧：页面编辑+任务 */}
        <Col span={14}>
          {currentProject ? (
            <Card title={`页面编辑 - ${currentProject.name}（${currentProject.slide_count}页）`} size="small">
              <Collapse accordion>
                {currentProject.slides?.map(slide => (
                  <Panel
                    key={slide.id}
                    header={
                      <Space>
                        <Text strong>第 {slide.slide_index + 1} 页</Text>
                        {slide.narration_text && (
                          <Text type="secondary" ellipsis style={{ maxWidth: 300 }}>
                            {slide.narration_text.substring(0, 50)}...
                          </Text>
                        )}
                        {getStatusTag(slide.status)}
                      </Space>
                    }
                  >
                    <Row gutter={12}>
                      <Col span={8}>
                        {slide.slide_image_path && (
                          <Image
                            src={getSlideImageUrl(slide.slide_image_path)}
                            alt={`Slide ${slide.slide_index + 1}`}
                            style={{ width: '100%', border: '1px solid #d9d9d9', borderRadius: 4 }}
                            fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
                          />
                        )}
                      </Col>
                      <Col span={16}>
                        <div style={{ marginBottom: 8 }}>
                          <Text type="secondary" style={{ fontSize: 12 }}>提取的文字：</Text>
                          <div style={{ background: '#f5f5f5', padding: 8, borderRadius: 4, maxHeight: 80, overflow: 'auto', fontSize: 12 }}>
                            {slide.extracted_text || '（无文字）'}
                          </div>
                        </div>
                        <div>
                          <Text style={{ fontSize: 12 }}>讲解文字：</Text>
                          <TextArea
                            rows={4}
                            value={editingSlide === slide.id ? editText : (slide.narration_text || '')}
                            onChange={e => { setEditingSlide(slide.id); setEditText(e.target.value) }}
                            placeholder="输入这页PPT的讲解文字..."
                          />
                          {editingSlide === slide.id && (
                            <Button size="small" type="primary" style={{ marginTop: 4 }}
                              onClick={() => handleSaveNarration(slide.id)}>
                              保存讲稿
                            </Button>
                          )}
                        </div>
                      </Col>
                    </Row>
                  </Panel>
                ))}
              </Collapse>
            </Card>
          ) : (
            <Card>
              <Empty description="请先上传PPT文件" />
            </Card>
          )}

          {tasks.length > 0 && (
            <Card title="生成任务" size="small" style={{ marginTop: 16 }}>
              <List
                size="small"
                dataSource={tasks}
                renderItem={t => (
                  <List.Item
                    actions={[
                      t.output_video && (
                        <Button size="small" type="link" icon={<PlayCircleOutlined />}
                          onClick={() => handlePreview(t.output_video)}>播放</Button>
                      )
                    ]}
                  >
                    <List.Item.Meta
                      title={`项目 #${t.project_id}`}
                      description={
                        <Space>
                          {getStatusTag(t.status)}
                          <Text type="secondary">{t.message}</Text>
                          {t.status === 'processing' && t.total_slides > 0 && (
                            <Progress percent={Math.round(t.current_slide / t.total_slides * 100)} size="small" style={{ width: 120 }} />
                          )}
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            </Card>
          )}
        </Col>
      </Row>

      <Modal
        title="视频预览"
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        footer={null}
        width={800}
      >
        {previewVideo && (
          <video src={previewVideo} controls autoPlay style={{ width: '100%' }} />
        )}
      </Modal>
    </div>
  )
}
