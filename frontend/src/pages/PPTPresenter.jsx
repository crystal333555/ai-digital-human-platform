import React, { useState, useEffect, useCallback, useRef } from 'react'
import {
  Card, Button, Input, Select, Form, Row, Col, message, Progress,
  List, Tag, Space, Typography, Divider, Modal, Empty, Spin,
  Upload, Slider, Collapse, Image, Steps, Tooltip, Badge, Checkbox,
  Collapse as AntCollapse
} from 'antd'
import {
  FilePptOutlined, PlayCircleOutlined, EditOutlined,
  CheckCircleOutlined, ClockCircleOutlined, CloseCircleOutlined,
  LoadingOutlined, UploadOutlined, VideoCameraOutlined, DeleteOutlined,
  SoundOutlined, UserOutlined, LayoutOutlined, ThunderboltOutlined,
  FileTextOutlined, EyeOutlined, ArrowRightOutlined, InfoCircleOutlined,
  ReloadOutlined, CheckOutlined, WarningOutlined, SettingOutlined,
  MergeCellsOutlined
} from '@ant-design/icons'
import { api, avatarAPI, voiceAPI, voiceLibAPI, pptAPI } from '../services/api'

const { TextArea } = Input
const { Title, Text, Paragraph } = Typography

const PPT_API = '/ppt'

export default function PPTPresenter() {
  const [form] = Form.useForm()
  const [avatars, setAvatars] = useState([])
  const [myVoices, setMyVoices] = useState([])
  const [presetVoices, setPresetVoices] = useState([])
  const [projects, setProjects] = useState([])
  const [currentProject, setCurrentProject] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [activeSlide, setActiveSlide] = useState(0)
  const [previewVideo, setPreviewVideo] = useState(null)
  const [selectedSlideIds, setSelectedSlideIds] = useState([])
  const [slideStatuses, setSlideStatuses] = useState({})
  const [slideVideos, setSlideVideos] = useState({})
  const [serviceReady, setServiceReady] = useState({ musetalk: false, tts: false })
  const [merging, setMerging] = useState(false)
  const [finalVideo, setFinalVideo] = useState(null)
  const pollRef = useRef({})

  useEffect(() => {
    loadData()
    const interval = setInterval(checkServices, 30000)
    checkServices()
    return () => clearInterval(interval)
  }, [])

  const loadData = async () => {
    try {
      const [avatarRes, voiceRes, presetRes, projectRes] = await Promise.all([
        avatarAPI.list(),
        voiceAPI.list(),
        voiceLibAPI.presets(),
        api.get(`${PPT_API}/projects`),
      ])
      setAvatars(Array.isArray(avatarRes.data) ? avatarRes.data : (avatarRes.data?.items || []))
      setMyVoices(Array.isArray(voiceRes.data) ? voiceRes.data : (voiceRes.data?.items || []))
      setPresetVoices(presetRes.data?.voices || [])
      setProjects(projectRes.data || [])
    } catch (e) {
      console.error('Load data error:', e)
    }
  }

  const checkServices = async () => {
    try {
      const res = await api.get('/system/services')
      setServiceReady({
        musetalk: res.data?.musetalk?.status === 'online' && res.data?.musetalk?.models_loaded,
        tts: res.data?.gpt_sovits?.status === 'online' || true,
      })
    } catch {}
  }

  // 选择项目
  const handleSelectProject = async (projectId) => {
    try {
      const res = await api.get(`${PPT_API}/projects/${projectId}`)
      setCurrentProject(res.data)
      setActiveSlide(0)
      setFinalVideo(res.data.output_video_path ? 
        (res.data.output_video_path.startsWith('/data/') ? `http://localhost:8000${res.data.output_video_path}` : res.data.output_video_path)
        : null)
      // 初始化已选页面
      const completed = (res.data.slides || []).filter(s => s.status === 'completed').map(s => s.id)
      setSelectedSlideIds(completed)
      // 加载已有视频
      const videos = {}
      for (const s of (res.data.slides || [])) {
        if (s.composed_video_path) {
          videos[s.id] = s.composed_video_path.startsWith('/data/') ? `http://localhost:8000${s.composed_video_path}` : s.composed_video_path
        }
      }
      setSlideVideos(videos)
    } catch (e) {
      message.error('加载项目失败')
    }
  }

  // 生成单页
  const handleGenerateSlide = async (slide) => {
    if (!serviceReady.musetalk) {
      message.warning('MuseTalk离线，无法生成')
      return
    }
    const values = form.getFieldsValue()
    if (!values.avatar_id) {
      message.warning('请先选择数字人形象')
      return
    }

    // 构造音色配置
    let voiceConfig = null
    let voiceId = null
    if (values.voice_select) {
      const vc = JSON.parse(values.voice_select)
      if (vc.type === 'my') {
        voiceId = vc.voice_id
      } else {
        voiceConfig = { type: 'preset', id: vc.id, edge_voice: vc.edge_voice }
      }
    }

    try {
      const res = await pptAPI.generateSlide(currentProject.id, slide.id, {
        avatar_id: values.avatar_id,
        voice_id: voiceId,
        voice_config: voiceConfig,
        layout_mode: values.layout_mode || 'pip',
        digital_human_position: values.position || 'bottom-right',
        digital_human_size: values.size_ratio || 0.25,
        segment_duration: values.segment_duration || 30,
        bbox_shift: values.bbox_shift ?? 0,
        musetalk_timeout_per_second: values.musetalk_timeout_per_second || 30,
      })

      message.info(`正在生成第${slide.slide_index + 1}页...`)
      // 轮询状态
      startSlidePolling(slide.id, res.data.task_id)
    } catch (e) {
      message.error('生成失败: ' + (e.response?.data?.detail || e.message))
    }
  }

  // 轮询单页状态
  const startSlidePolling = (slideId, taskId) => {
    if (pollRef.current[slideId]) clearInterval(pollRef.current[slideId])

    setSlideStatuses(prev => ({ ...prev, [slideId]: { status: 'processing', message: '生成中...' } }))

    pollRef.current[slideId] = setInterval(async () => {
      try {
        const res = await pptAPI.getTask(taskId)
        const task = res.data
        setSlideStatuses(prev => ({ ...prev, [slideId]: { status: task.status, message: task.message } }))

        if (task.status === 'completed') {
          clearInterval(pollRef.current[slideId])
          delete pollRef.current[slideId]
          message.success(`第${slideId}页生成完成`)
          // 刷新项目获取视频URL
          handleSelectProject(currentProject.id)
        } else if (task.status === 'error' || task.status === 'cancelled') {
          clearInterval(pollRef.current[slideId])
          delete pollRef.current[slideId]
          message.error(`生成失败: ${task.message}`)
        }
      } catch {
        clearInterval(pollRef.current[slideId])
        delete pollRef.current[slideId]
      }
    }, 5000)
  }

  // 保存讲稿
  const handleSaveNarration = async (slideId, text) => {
    try {
      await api.put(`${PPT_API}/projects/${currentProject.id}/slides/${slideId}`, {
        narration_text: text
      })
      message.success('讲稿已保存')
    } catch (e) {
      message.error('保存失败')
    }
  }

  // 合成选中页
  const handleMerge = async (all = false) => {
    const ids = all ? [] : selectedSlideIds
    if (!all && ids.length < 1) {
      message.warning('请至少选择1页')
      return
    }
    setMerging(true)
    try {
      const res = await pptAPI.mergeSlides(currentProject.id, ids)
      if (res.data?.success) {
        message.success(res.data.message)
        const videoUrl = res.data.video_url.startsWith('/data/') ? `http://localhost:8000${res.data.video_url}` : res.data.video_url
        setFinalVideo(videoUrl)
      }
    } catch (e) {
      message.error('合成失败: ' + (e.response?.data?.detail || e.message))
    } finally {
      setMerging(false)
    }
  }

  // 上传PPT
  const handleUpload = async (info) => {
    if (info.file.status === 'uploading') {
      setUploading(true)
      return
    }
    if (info.file.status === 'done') {
      setUploading(false)
      message.success(`${info.file.name} 上传成功`)
      loadData()
      const newProject = info.file.response
      if (newProject?.project_id) {
        handleSelectProject(newProject.project_id)
      }
    } else if (info.file.status === 'error') {
      setUploading(false)
      message.error(`${info.file.name} 上传失败`)
    }
  }

  // 删除项目
  const handleDelete = async (projectId) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后无法恢复，包括所有已生成的视频',
      okText: '删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: async () => {
        try {
          await pptAPI.deleteProject(projectId)
          message.success('已删除')
          if (currentProject?.id === projectId) setCurrentProject(null)
          loadData()
        } catch (e) {
          message.error('删除失败')
        }
      }
    })
  }

  const voiceOptions = [
    { label: '--- 我的音色 ---', options: myVoices.map(v => ({
      label: `${v.name}${v.source === 'cloned' ? ' (已克隆)' : v.source === 'blended' ? ' (混合)' : ''}`,
      value: JSON.stringify({ type: 'my', voice_id: v.id }),
    }))},
    { label: '--- 预置音色 ---', options: presetVoices.map(v => ({
      label: `${v.name}（${v.category || v.gender || ''}）`,
      value: JSON.stringify({ type: 'preset', id: v.id, edge_voice: v.edge_tts_voice }),
    }))},
  ]

  const slides = currentProject?.slides || []
  const currentSlide = slides[activeSlide]
  const completedCount = slides.filter(s => s.status === 'completed').length

  const statusIcon = (status) => {
    switch (status) {
      case 'completed': return <CheckCircleOutlined style={{ color: '#52c41a' }} />
      case 'generating': return <LoadingOutlined style={{ color: '#1890ff' }} />
      case 'error': return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
      default: return <ClockCircleOutlined style={{ color: '#d9d9d9' }} />
    }
  }

  return (
    <div style={{ display: 'flex', gap: 16, height: 'calc(100vh - 120px)' }}>
      {/* 左侧：项目列表 + 页面列表 */}
      <div style={{ width: 280, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <Card size="small" title={<><FilePptOutlined /> PPT项目</>} extra={
          <Upload
            name="file"
            action="/api/v1/ppt/upload"
            accept=".pptx"
            showUploadList={false}
            onChange={handleUpload}
          >
            <Button size="small" icon={<UploadOutlined />} loading={uploading}>上传</Button>
          </Upload>
        } style={{ flexShrink: 0 }}>
          <List
            size="small"
            dataSource={projects}
            locale={{ emptyText: <Empty description="暂无项目" /> }}
            renderItem={p => (
              <List.Item
                style={{
                  cursor: 'pointer', borderRadius: 8, padding: '8px 12px', margin: '4px 0',
                  background: currentProject?.id === p.id ? 'rgba(91,91,214,0.06)' : undefined,
                  border: currentProject?.id === p.id ? '1px solid rgba(91,91,214,0.2)' : '1px solid transparent',
                }}
                onClick={() => handleSelectProject(p.id)}
              >
                <List.Item.Meta
                  title={<Text strong style={{ fontSize: 13 }}>{p.name}</Text>}
                  description={
                    <Space size={4}>
                      <Tag color={p.status === 'completed' ? 'green' : p.status === 'error' ? 'red' : 'blue'} style={{ fontSize: 11 }}>
                        {p.status === 'completed' ? '已完成' : p.status === 'error' ? '失败' : p.status === 'generating' ? '生成中' : '草稿'}
                      </Tag>
                      <Text type="secondary" style={{ fontSize: 11 }}>{p.slide_count || 0}页</Text>
                      <Tooltip title="删除">
                        <DeleteOutlined style={{ color: '#ff4d4f', fontSize: 12 }} onClick={(e) => { e.stopPropagation(); handleDelete(p.id) }} />
                      </Tooltip>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        </Card>

        {currentProject && (
          <Card size="small" title={<><FileTextOutlined /> 页面列表</>} extra={
            <Text type="secondary" style={{ fontSize: 12 }}>{completedCount}/{slides.length}页完成</Text>
          } style={{ flex: 1, overflow: 'auto' }}>
            <Checkbox.Group
              value={selectedSlideIds}
              onChange={setSelectedSlideIds}
              style={{ width: '100%' }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                {slides.map((s, i) => {
                  const st = slideStatuses[s.id]?.status || s.status
                  const msg = slideStatuses[s.id]?.message
                  return (
                    <div key={s.id} style={{
                      display: 'flex', alignItems: 'center', gap: 8, padding: '6px 8px',
                      borderRadius: 6, cursor: 'pointer',
                      background: activeSlide === i ? 'rgba(91,91,214,0.06)' : undefined,
                    }} onClick={() => setActiveSlide(i)}>
                      <Checkbox value={s.id} onClick={e => e.stopPropagation()} />
                      {statusIcon(st)}
                      <Text style={{ fontSize: 12, flex: 1 }}>第{i + 1}页</Text>
                      {slideVideos[s.id] && <PlayCircleOutlined style={{ color: '#52c41a', fontSize: 14 }} />}
                    </div>
                  )
                })}
              </Space>
            </Checkbox.Group>
          </Card>
        )}
      </div>

      {/* 中间：预览 + 编辑 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12, overflow: 'auto' }}>
        {!currentProject ? (
          <Card style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Empty description="请选择或上传PPT项目" />
          </Card>
        ) : (
          <>
            {/* PPT页面预览 */}
            {currentSlide && (
              <Card size="small" title={`第${activeSlide + 1}页 / 共${slides.length}页`} extra={
                <Space>
                  <Button size="small" disabled={activeSlide === 0} onClick={() => setActiveSlide(activeSlide - 1)}>上一页</Button>
                  <Button size="small" disabled={activeSlide >= slides.length - 1} onClick={() => setActiveSlide(activeSlide + 1)}>下一页</Button>
                </Space>
              }>
                {currentSlide.slide_image_path ? (
                  <Image
                    src={currentSlide.slide_image_path.startsWith('/data/') || currentSlide.slide_image_path.startsWith('/uploads/') ?
                      `http://localhost:8000${currentSlide.slide_image_path}` : currentSlide.slide_image_path}
                    style={{ maxHeight: 300, objectFit: 'contain' }}
                  />
                ) : (
                  <div style={{ height: 200, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#f5f5fa', borderRadius: 8 }}>
                    <Text type="secondary">无预览图</Text>
                  </div>
                )}
              </Card>
            )}

            {/* 讲稿编辑 */}
            {currentSlide && (
              <Card size="small" title={<><EditOutlined /> 讲稿编辑</>}>
                <TextArea
                  value={currentSlide.narration_text || ''}
                  onChange={e => {
                    const newSlides = [...slides]
                    newSlides[activeSlide] = { ...currentSlide, narration_text: e.target.value }
                    setCurrentProject({ ...currentProject, slides: newSlides })
                  }}
                  rows={4}
                  placeholder="输入讲解文字..."
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {(currentSlide.narration_text || '').length}字 · 预计{Math.ceil((currentSlide.narration_text || '').length / 4)}秒
                  </Text>
                  <Space>
                    <Button size="small" onClick={() => handleSaveNarration(currentSlide.id, currentSlide.narration_text)}>保存讲稿</Button>
                    <Button type="primary" size="small" icon={<VideoCameraOutlined />}
                      loading={slideStatuses[currentSlide.id]?.status === 'processing'}
                      onClick={() => handleGenerateSlide(currentSlide)}>
                      {currentSlide.status === 'completed' ? '重新生成' : '生成本页'}
                    </Button>
                  </Space>
                </div>
                {slideStatuses[currentSlide.id]?.message && (
                  <div style={{ marginTop: 8 }}>
                    <Progress
                      percent={slideStatuses[currentSlide.id]?.status === 'completed' ? 100 : slideStatuses[currentSlide.id]?.status === 'error' ? 0 : 50}
                      status={slideStatuses[currentSlide.id]?.status === 'error' ? 'exception' : slideStatuses[currentSlide.id]?.status === 'completed' ? 'success' : 'active'}
                      size="small"
                      format={() => slideStatuses[currentSlide.id]?.message}
                    />
                  </div>
                )}
              </Card>
            )}

            {/* 单页视频预览 */}
            {currentSlide && slideVideos[currentSlide.id] && (
              <Card size="small" title={<><PlayCircleOutlined /> 本页视频预览</>}>
                <video
                  controls
                  style={{ width: '100%', maxHeight: 300, borderRadius: 8 }}
                  src={slideVideos[currentSlide.id]}
                />
              </Card>
            )}

            {/* 合成区域 */}
            <Card size="small" title={<><MergeCellsOutlined /> 视频合成</>}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                <Text>已选 <Text strong>{selectedSlideIds.length}</Text> 页 · 已完成 <Text strong>{completedCount}</Text> 页</Text>
                <Space>
                  <Button icon={<MergeCellsOutlined />} loading={merging}
                    disabled={selectedSlideIds.length < 1}
                    onClick={() => handleMerge(false)}>
                    合成选中({selectedSlideIds.length}页)
                  </Button>
                  <Button type="primary" icon={<VideoCameraOutlined />} loading={merging}
                    disabled={completedCount < 1}
                    onClick={() => handleMerge(true)}>
                    合成全部({completedCount}页)
                  </Button>
                </Space>
              </div>

              {finalVideo && (
                <div>
                  <Divider style={{ margin: '8px 0' }} />
                  <Text strong>最终视频：</Text>
                  <video
                    controls
                    style={{ width: '100%', maxHeight: 400, borderRadius: 8, marginTop: 8 }}
                    src={finalVideo}
                  />
                </div>
              )}
            </Card>
          </>
        )}
      </div>

      {/* 右侧：配置面板 */}
      <div style={{ width: 280 }}>
        <Card size="small" title={<><SettingOutlined /> 生成配置</>} style={{ position: 'sticky', top: 0 }}>
          <Form form={form} layout="vertical" size="small">
            <Form.Item label="数字人形象" name="avatar_id">
              <Select placeholder="选择形象">
                {avatars.map(a => (
                  <Select.Option key={a.id} value={a.id}>{a.name}</Select.Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item label="音色选择" name="voice_select">
              <Select placeholder="选择音色" options={voiceOptions} />
            </Form.Item>

            <Form.Item label="布局模式" name="layout_mode" initialValue="pip">
              <Select>
                <Select.Option value="pip">画中画</Select.Option>
                <Select.Option value="bottom_bar">底部横条</Select.Option>
              </Select>
            </Form.Item>

            <Form.Item label="数字人位置" name="position" initialValue="bottom-right">
              <Select>
                <Select.Option value="bottom-right">右下角</Select.Option>
                <Select.Option value="bottom-left">左下角</Select.Option>
                <Select.Option value="bottom-center">底部居中</Select.Option>
              </Select>
            </Form.Item>

            <Form.Item label="数字人大小" name="size_ratio" initialValue={0.25}>
              <Slider min={0.15} max={0.4} step={0.05} marks={{ 0.15: '15%', 0.25: '25%', 0.4: '40%' }} />
            </Form.Item>

            <AntCollapse ghost size="small">
              <AntCollapse.Panel header={<Text type="secondary" style={{ fontSize: 12 }}><SettingOutlined /> 高级参数</Text>} key="adv">
                <Form.Item label={<Tooltip title="音频和视频的分段时长"><Text style={{ fontSize: 12 }}>分段时长（秒）<InfoCircleOutlined /></Text></Tooltip>} name="segment_duration" initialValue={30}>
                  <Slider min={10} max={120} step={5} marks={{ 10: '10s', 30: '30s', 60: '60s', 120: '120s' }} />
                </Form.Item>
                <Form.Item label={<Tooltip title="面部区域偏移"><Text style={{ fontSize: 12 }}>面部偏移<InfoCircleOutlined /></Text></Tooltip>} name="bbox_shift" initialValue={0}>
                  <Slider min={-20} max={20} step={1} />
                </Form.Item>
                <Form.Item label={<Tooltip title="每秒音频的推理超时秒数"><Text style={{ fontSize: 12 }}>超时倍数<InfoCircleOutlined /></Text></Tooltip>} name="musetalk_timeout_per_second" initialValue={30}>
                  <Slider min={10} max={60} step={5} />
                </Form.Item>
              </AntCollapse.Panel>
            </AntCollapse>

            <Divider style={{ margin: '8px 0' }} />
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Space size={4}>
                <Badge status={serviceReady.musetalk ? 'success' : 'error'} />
                <Text style={{ fontSize: 11 }}>MuseTalk</Text>
              </Space>
              <Space size={4}>
                <Badge status={serviceReady.tts ? 'success' : 'error'} />
                <Text style={{ fontSize: 11 }}>TTS</Text>
              </Space>
            </div>
          </Form>
        </Card>
      </div>
    </div>
  )
}