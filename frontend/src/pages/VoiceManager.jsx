import React, { useState, useEffect, useRef } from 'react'
import { Table, Button, Modal, Form, Input, Upload, message, Tag, Card, Row, Col, Slider, Tabs, Badge, Space, Typography } from 'antd'
import { PlusOutlined, UploadOutlined, AudioOutlined, DeleteOutlined, PlayCircleOutlined, PauseCircleOutlined, ExperimentOutlined, SoundOutlined, SaveOutlined, ReloadOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { voiceAPI, voiceLibAPI } from '../services/api.js'

const { TabPane } = Tabs
const { Title, Text } = Typography

function VoiceManager() {
  const [voices, setVoices] = useState([])
  const [presetVoices, setPresetVoices] = useState([])
  const [categories, setCategories] = useState([])
  const [activeTab, setActiveTab] = useState('my')
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [cloning, setCloning] = useState({})
  const [playing, setPlaying] = useState(null)
  const [previewLoading, setPreviewLoading] = useState(null)
  const [myVoicePlaying, setMyVoicePlaying] = useState(null)
  const [myVoicePreviewLoading, setMyVoicePreviewLoading] = useState(null)
  const [blendVoices, setBlendVoices] = useState([])
  const [blendWeights, setBlendWeights] = useState({})
  const [blendText, setBlendText] = useState('你好，我是融合多种特色的全新音色。')
  const [blendResult, setBlendResult] = useState(null)
  const [blendLoading, setBlendLoading] = useState(false)
  const [blendSaveOpen, setBlendSaveOpen] = useState(false)
  const [blendSaveName, setBlendSaveName] = useState('')
  const [blendSaveDesc, setBlendSaveDesc] = useState('')
  const [blendSaving, setBlendSaving] = useState(false)
  const audioRef = useRef(null)
  const [form] = Form.useForm()

  useEffect(() => {
    loadVoices()
    loadPresetVoices()
    loadCategories()
  }, [])

  const loadVoices = async () => {
    try {
      const res = await voiceAPI.list()
      setVoices(res.data || [])
    } catch (err) {
      message.error('加载音色失败')
    }
  }

  const loadPresetVoices = async (category, gender) => {
    try {
      const params = {}
      if (category) params.category = category
      if (gender) params.gender = gender
      const res = await voiceLibAPI.presets(params)
      setPresetVoices(res.data?.voices || [])
    } catch (err) {
      console.error('加载音色库失败', err)
    }
  }

  const loadCategories = async () => {
    try {
      const res = await voiceLibAPI.categories()
      setCategories(res.data?.categories || [])
    } catch (err) {
      console.error('加载分类失败', err)
    }
  }

  const handleUpload = async (values) => {
    setUploading(true)
    try {
      const formData = new FormData()
      if (values.file && values.file.fileList && values.file.fileList[0]) {
        formData.append('file', values.file.fileList[0].originFileObj)
      }
      formData.append('name', values.name)
      if (values.description) formData.append('description', values.description)

      await voiceAPI.upload(formData)
      message.success('音色上传成功')
      setIsModalOpen(false)
      form.resetFields()
      loadVoices()
    } catch (err) {
      message.error('上传失败: ' + err.message)
    } finally {
      setUploading(false)
    }
  }

  const handleClone = async (id) => {
    setCloning({ ...cloning, [id]: true })
    try {
      const res = await voiceAPI.clone(id)
      message.success('克隆任务已启动: ' + res.data.task_id)
    } catch (err) {
      message.error('克隆失败')
    } finally {
      setCloning({ ...cloning, [id]: false })
    }
  }

  const handleDelete = async (id) => {
    try {
      await voiceAPI.delete(id)
      message.success('删除成功')
      loadVoices()
    } catch (err) {
      message.error('删除失败')
    }
  }

  const playMyVoice = async (voice) => {
    if (myVoicePlaying === voice.id) {
      setMyVoicePlaying(null)
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
      return
    }

    // 先停止之前的播放
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current = null
    }

    setMyVoicePreviewLoading(voice.id)
    try {
      const res = await voiceAPI.preview(voice.id)
      if (res.data?.audio_url) {
        let audioUrl = res.data.audio_url
        if (audioUrl.startsWith('/data/') || audioUrl.startsWith('/uploads/')) {
          audioUrl = `http://localhost:8000${audioUrl}`
        }
        console.log('[VoiceManager] Preview audio URL:', audioUrl)
        const audio = new Audio(audioUrl)
        audio.onended = () => {
          console.log('[VoiceManager] Audio ended')
          setMyVoicePlaying(null)
        }
        audio.onerror = (e) => {
          console.error('[VoiceManager] Audio error:', e)
          setMyVoicePlaying(null)
          message.error('音频播放失败，请检查浏览器是否支持WAV格式')
        }
        audio.oncanplay = () => {
          console.log('[VoiceManager] Audio can play')
        }
        audio.onloadeddata = () => {
          console.log('[VoiceManager] Audio loaded, duration:', audio.duration)
        }
        audioRef.current = audio
        setMyVoicePlaying(voice.id)
        try {
          await audio.play()
          console.log('[VoiceManager] Audio play started')
          message.success('正在播放试听音频...')
        } catch (playErr) {
          console.error('[VoiceManager] Play failed:', playErr)
          setMyVoicePlaying(null)
          message.error('播放被浏览器阻止，请点击页面后再试')
        }
      } else {
        message.error('未获取到音频URL')
      }
    } catch (err) {
      console.error('[VoiceManager] Preview API error:', err)
      message.error('试听失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setMyVoicePreviewLoading(null)
    }
  }

  const playPreset = async (voiceId) => {
    if (playing === voiceId) {
      setPlaying(null)
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current = null
      }
      return
    }

    setPreviewLoading(voiceId)
    try {
      const res = await voiceLibAPI.testPreset(voiceId)
      if (res.data?.audio_url) {
        let audioUrl = res.data.audio_url
        if (audioUrl.startsWith('/data/')) {
          audioUrl = `http://localhost:8000${audioUrl}`
        } else if (audioUrl.startsWith('/uploads/')) {
          audioUrl = `http://localhost:8000${audioUrl}`
        }
        const audio = new Audio(audioUrl)
        audio.onended = () => setPlaying(null)
        audio.onerror = () => {
          setPlaying(null)
          message.error('音频播放失败')
        }
        audioRef.current = audio
        setPlaying(voiceId)
        try {
          await audio.play()
        } catch (playErr) {
          setPlaying(null)
          message.error('播放被浏览器阻止')
        }
      }
    } catch (err) {
      message.error('试听失败: ' + err.message)
    } finally {
      setPreviewLoading(null)
    }
  }

  const addToBlend = (voice) => {
    if (blendVoices.length >= 3) {
      message.warning('最多选择3个音色')
      return
    }
    if (blendVoices.find(v => v.id === voice.id)) {
      message.info('该音色已在混合列表中')
      return
    }
    const nextLen = blendVoices.length + 1
    const newVoices = [...blendVoices, voice]
    const newWeights = { ...blendWeights }
    // 重新均分权重
    const newWeight = 1 / nextLen
    newWeights[voice.id] = newWeight
    // 更新已有权重
    newVoices.forEach(v => {
      if (v.id !== voice.id) {
        newWeights[v.id] = newWeight
      }
    })
    setBlendVoices(newVoices)
    setBlendWeights(newWeights)
    message.success(`已添加「${voice.name}」，当前共 ${nextLen} 个音色，还可添加 ${3 - nextLen} 个`)
  }

  const removeFromBlend = (voiceId) => {
    const newVoices = blendVoices.filter(v => v.id !== voiceId)
    const newWeights = {}
    const total = newVoices.length
    newVoices.forEach(v => {
      newWeights[v.id] = total > 0 ? parseFloat((1 / total).toFixed(2)) : 0
    })
    setBlendVoices(newVoices)
    setBlendWeights(newWeights)
  }

  const updateWeight = (voiceId, value) => {
    setBlendWeights({ ...blendWeights, [voiceId]: value })
  }

  const doBlend = async () => {
    if (blendVoices.length < 2) {
      message.warning('请至少选择2个音色')
      return
    }
    if (!blendSaveName.trim()) {
      message.warning('请输入新音色名称')
      return
    }

    setBlendLoading(true)
    setBlendResult(null)

    try {
      const voice_ids = blendVoices.map(v => v.id)
      const weights = blendVoices.map(v => blendWeights[v.id] || 0.5)

      // 1. 生成混合音频预览
      const res = await voiceLibAPI.blend({
        voice_ids,
        weights,
        text: blendText,
        method: "audio"
      })
      setBlendResult(res.data)

      // 2. 直接保存到我的音色
      const saveRes = await voiceLibAPI.saveBlend({
        name: blendSaveName,
        description: blendSaveDesc,
        voice_ids,
        weights,
        method: 'audio'
      })

      if (saveRes.data?.success) {
        message.success(`混合音色「${blendSaveName}」已生成并保存到我的音色`)
        loadVoices()
      } else {
        message.success('混合音色生成成功，但保存失败')
      }
    } catch (err) {
      message.error('混合失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setBlendLoading(false)
    }
  }

  const playBlendResult = () => {
    if (!blendResult?.audio_url) return
    let audioUrl = blendResult.audio_url
    if (audioUrl.startsWith('/data/') || audioUrl.startsWith('/uploads/')) {
      audioUrl = `http://localhost:8000${audioUrl}`
    }
    const audio = new Audio(audioUrl)
    audio.play()
  }

  const handleSaveBlend = async () => {
    if (!blendSaveName.trim()) {
      message.warning('请输入音色名称')
      return
    }
    setBlendSaving(true)
    try {
      const voice_ids = blendVoices.map(v => v.id)
      const weights = blendVoices.map(v => blendWeights[v.id] || 0.5)
      const res = await voiceLibAPI.saveBlend({
        name: blendSaveName,
        description: blendSaveDesc,
        voice_ids,
        weights,
        method: 'audio'
      })
      if (res.data?.success) {
        message.success(res.data.message || '保存成功')
        setBlendSaveOpen(false)
        setBlendSaveName('')
        setBlendSaveDesc('')
        loadVoices()
        setActiveTab('my')
      }
    } catch (err) {
      message.error('保存失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setBlendSaving(false)
    }
  }

  const handleAddPresetToMine = async (voice) => {
    try {
      const res = await voiceLibAPI.cloneToMine(voice.id, voice.name)
      message.success(res.data?.message || `已将「${voice.name}」添加到我的音色`)
      loadVoices()
    } catch (err) {
      message.error('添加失败: ' + (err.response?.data?.detail || err.message))
    }
  }

  const getCategoryColor = (cat) => {
    const colors = {
      '温柔系': 'pink',
      '沉稳系': 'blue',
      '活力系': 'orange',
      '方言特色': 'purple',
      'AI/特殊': 'cyan',
    }
    return colors[cat] || 'default'
  }

  const getGenderIcon = (g) => {
    if (g === 'male') return '♂'
    if (g === 'female') return '♀'
    return '⚧'
  }

  return (
    <div>
      <Title level={3}>音色管理</Title>
      <Text type="secondary">管理你的音色，或从预置音色库中浏览、试听、自由混合创建新音色</Text>

      <Tabs activeKey={activeTab} onChange={setActiveTab} style={{ marginTop: 16 }}>
        <TabPane tab={<><SoundOutlined /> 我的音色</>} key="my">
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setIsModalOpen(true)} style={{ marginBottom: 16 }}>
            上传参考音频
          </Button>

          <Table
            columns={[
              { title: 'ID', dataIndex: 'id', width: 60 },
              { title: '名称', dataIndex: 'name' },
              { title: '来源', dataIndex: 'source', render: (t) => <Tag color={t === 'cloned' ? 'green' : 'blue'}>{t}</Tag> },
              { title: '创建时间', dataIndex: 'created_at' },
              {
                title: '操作',
                key: 'action',
                render: (_, record) => (
                  <Space>
                    <Button
                      type={myVoicePlaying === record.id ? 'primary' : 'default'}
                      icon={myVoicePlaying === record.id ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                      loading={myVoicePreviewLoading === record.id}
                      onClick={() => playMyVoice(record)}
                    >
                      {myVoicePlaying === record.id ? '停止' : '试听'}
                    </Button>
                    {record.source === 'cloned' && (
                      <Button icon={<AudioOutlined />} loading={cloning[record.id]} onClick={() => handleClone(record.id)}>
                        {record.cloned_voice_id ? '重新克隆' : '克隆训练'}
                      </Button>
                    )}
                    <Button icon={<DeleteOutlined />} danger onClick={() => handleDelete(record.id)}>删除</Button>
                  </Space>
                ),
              },
            ]}
            dataSource={voices}
            rowKey="id"
          />
        </TabPane>

        <TabPane tab={<><PlayCircleOutlined /> 预置音色库 ({presetVoices.length})</>} key="library">
          {/* 已选音色提示 */}
          {blendVoices.length > 0 && (
            <Card size="small" style={{ marginBottom: 16, background: '#f6ffed', borderColor: '#b7eb8f' }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Space>
                  <Text strong>已选音色 ({blendVoices.length}/3)：</Text>
                  {blendVoices.map(v => (
                    <Tag key={v.id} color="green" closable onClose={() => removeFromBlend(v.id)}>
                      {v.name}
                    </Tag>
                  ))}
                  {blendVoices.length < 3 && (
                    <Text type="secondary">还可选 {3 - blendVoices.length} 个</Text>
                  )}
                  {blendVoices.length >= 3 && (
                    <Text type="danger">已达到上限（最多3个）</Text>
                  )}
                </Space>
                <Space>
                  <Button type="primary" size="small" onClick={() => setActiveTab('blend')}>
                    去混合页面调整比例
                  </Button>
                  {blendVoices.length > 0 && (
                    <Button size="small" danger onClick={() => { setBlendVoices([]); setBlendWeights({}) }}>
                      清空已选
                    </Button>
                  )}
                </Space>
              </Space>
            </Card>
          )}

          <Space style={{ marginBottom: 16 }}>
            {categories.map(cat => (
              <Button key={cat.name} onClick={() => loadPresetVoices(cat.name)}>
                {cat.name}
                <Badge count={cat.count} style={{ marginLeft: 4 }} />
              </Button>
            ))}
            <Button onClick={() => loadPresetVoices()}>全部</Button>
          </Space>

          <Row gutter={[16, 16]}>
            {presetVoices.map(voice => {
              const isSelected = blendVoices.find(bv => bv.id === voice.id)
              return (
                <Col key={voice.id} xs={24} sm={12} md={8} lg={6}>
                  <Card
                    hoverable
                    size="small"
                    style={isSelected ? { border: '2px solid #52c41a', background: '#f6ffed' } : {}}
                    title={
                      <Space>
                        <Text strong>{voice.name}</Text>
                        <Tag color={getCategoryColor(voice.category)} size="small">{voice.category}</Tag>
                      </Space>
                    }
                    extra={<Text type="secondary">{getGenderIcon(voice.gender)}</Text>}
                    actions={[
                      <Button
                        type={isSelected ? 'primary' : 'default'}
                        size="small"
                        onClick={() => addToBlend(voice)}
                        disabled={blendVoices.length >= 3 && !isSelected}
                      >
                        {isSelected ? '已选' : '加入混合'}
                      </Button>,
                      <Button
                        type={playing === voice.id ? 'primary' : 'default'}
                        icon={playing === voice.id ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                        size="small"
                        loading={previewLoading === voice.id}
                        onClick={() => playPreset(voice.id)}
                      >
                        {playing === voice.id ? '暂停' : '试听'}
                      </Button>,
                      <Button
                        size="small"
                        icon={<PlusOutlined />}
                        onClick={() => handleAddPresetToMine(voice)}
                      >
                        添加到我的音色
                      </Button>
                    ]}
                  >
                    <Text type="secondary" style={{ fontSize: 12 }}>{voice.description}</Text>
                    <div style={{ marginTop: 8 }}>
                      {voice.mood_tags?.map(tag => (
                        <Tag size="small" key={tag}>{tag}</Tag>
                      ))}
                    </div>
                  </Card>
                </Col>
              )
            })}
          </Row>
        </TabPane>

        <TabPane tab={<><ExperimentOutlined /> 音色混合 {blendVoices.length > 0 && <Badge count={blendVoices.length} />}</>} key="blend">
          <Row gutter={16}>
            <Col span={14}>
              <Card title="混合配置" size="small" extra={blendVoices.length >= 2 && <Tag color="green">可混合</Tag>}>
                {blendVoices.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '40px 0' }}>
                    <ExperimentOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
                    <div style={{ marginTop: 16 }}>
                      <Text type="secondary">选择 2~3 个音色进行混合</Text>
                    </div>
                    <div style={{ marginTop: 12 }}>
                      <Button type="primary" onClick={() => setActiveTab('library')}>去音色库选择 →</Button>
                    </div>
                  </div>
                ) : (
                  <>
                    {blendVoices.map((voice, index) => (
                      <div key={voice.id} style={{
                        marginBottom: 12,
                        padding: '12px 16px',
                        background: '#fafafa',
                        borderRadius: 8,
                        border: '1px solid #f0f0f0'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                          <Space>
                            <div style={{
                              width: 28, height: 28, borderRadius: '50%',
                              background: `linear-gradient(135deg, ${['#5b5bd6', '#06b6d4', '#ec4899'][index]}, ${['#8186f0', '#22d3ee', '#f472b6'][index]})`,
                              color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                              fontSize: 13, fontWeight: 600
                            }}>{index + 1}</div>
                            <Text strong>{voice.name}</Text>
                            <Tag size="small" color={getCategoryColor(voice.category)}>{voice.category}</Tag>
                          </Space>
                          <Space>
                            <Button size="small" type="text" icon={<PlayCircleOutlined />}
                              onClick={() => handlePreviewPreset(voice.id)}>
                              试听
                            </Button>
                            <Button size="small" type="text" danger icon={<DeleteOutlined />}
                              onClick={() => removeFromBlend(voice.id)} />
                          </Space>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <Slider
                            min={0.1} max={0.9} step={0.05}
                            value={blendWeights[voice.id] || 0.5}
                            onChange={(v) => updateWeight(voice.id, v)}
                            style={{ flex: 1 }}
                            tooltip={{ formatter: v => `${Math.round(v * 100)}%` }}
                          />
                          <div style={{
                            width: 56, textAlign: 'center',
                            fontWeight: 600, color: '#5b5bd6',
                            fontSize: 14
                          }}>
                            {Math.round((blendWeights[voice.id] || 0.5) * 100)}%
                          </div>
                        </div>
                      </div>
                    ))}

                    {blendVoices.length < 2 && (
                      <div style={{ marginBottom: 12, padding: 12, background: '#fffbe6', borderRadius: 8, border: '1px solid #ffe58f' }}>
                        <Text type="warning">还需至少选择 {2 - blendVoices.length} 个音色</Text>
                        <Button size="small" type="link" onClick={() => setActiveTab('library')}>去添加</Button>
                      </div>
                    )}

                    <div style={{ marginTop: 12 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>合成文本</Text>
                      <Input.TextArea
                        value={blendText}
                        onChange={(e) => setBlendText(e.target.value)}
                        rows={2}
                        style={{ marginTop: 4 }}
                        placeholder="输入要合成的文本内容..."
                      />
                    </div>

                    {blendVoices.length >= 2 && (
                      <>
                        <div style={{ marginTop: 12, marginBottom: 12 }}>
                          <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 6 }}>新音色名称</Text>
                          <Input
                            placeholder="如：温柔知性女声"
                            value={blendSaveName}
                            onChange={e => setBlendSaveName(e.target.value)}
                            style={{ borderRadius: 8 }}
                          />
                        </div>
                        <div style={{ marginBottom: 12 }}>
                          <Text strong style={{ fontSize: 13, display: 'block', marginBottom: 6 }}>描述（可选）</Text>
                          <Input.TextArea
                            placeholder="如：温柔桃子60% + 邻家女孩40%"
                            value={blendSaveDesc}
                            onChange={e => setBlendSaveDesc(e.target.value)}
                            rows={2}
                            style={{ borderRadius: 8 }}
                          />
                        </div>
                        <Button
                          type="primary" block
                          icon={<ExperimentOutlined />}
                          loading={blendLoading}
                          onClick={doBlend}
                          style={{ height: 40, borderRadius: 8 }}
                        >
                          生成混合音色
                        </Button>
                      </>
                    )}
                  </>
                )}
              </Card>
            </Col>

            <Col span={10}>
              <Card title="混合结果" size="small">
                {blendResult ? (
                  <>
                    <div style={{ marginBottom: 12, padding: 12, background: '#f6ffed', borderRadius: 8, border: '1px solid #b7eb8f' }}>
                      <Space>
                        <CheckCircleOutlined style={{ color: '#52c41a' }} />
                        <Text strong style={{ color: '#389e0d' }}>合成成功</Text>
                      </Space>
                    </div>

                    <div style={{ marginBottom: 12 }}>
                      <Text type="secondary" style={{ fontSize: 12 }}>混合比例</Text>
                      <div style={{ marginTop: 8, display: 'flex', gap: 4, height: 24, borderRadius: 6, overflow: 'hidden' }}>
                        {blendResult.blend_info?.voice_ids?.map((vid, idx) => {
                          const name = presetVoices.find(v => v.id === vid)?.name || vid
                          const weight = blendResult.blend_info?.normalized_weights?.[idx] || 0
                          const colors = ['#5b5bd6', '#06b6d4', '#ec4899']
                          return (
                            <div key={vid} style={{
                              flex: weight,
                              background: colors[idx % 3],
                              color: '#fff',
                              fontSize: 11,
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              minWidth: 30
                            }}>
                              {Math.round(weight * 100)}%
                            </div>
                          )
                        })}
                      </div>
                      <div style={{ marginTop: 6, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        {blendResult.blend_info?.voice_ids?.map((vid, idx) => {
                          const name = presetVoices.find(v => v.id === vid)?.name || vid
                          const colors = ['#5b5bd6', '#06b6d4', '#ec4899']
                          return <Tag key={vid} color={colors[idx % 3]}>{name}</Tag>
                        })}
                      </div>
                    </div>

                    {blendResult.audio_url && (
                    <audio
                      controls
                      style={{ width: '100%', marginTop: 8 }}
                      src={(() => {
                        let url = blendResult.audio_url || ''
                        if (url && (url.startsWith('/data/') || url.startsWith('/uploads/'))) {
                          return `http://localhost:8000${url}`
                        }
                        return url
                      })()}
                    />
                    )}

                    <Button
                      type="primary"
                      icon={<SaveOutlined />}
                      block
                      style={{ marginTop: 12, borderRadius: 8 }}
                      onClick={() => setBlendSaveOpen(true)}
                    >
                      保存为我的音色
                    </Button>
                    <Text type="secondary" style={{ fontSize: 12, display: 'block', marginTop: 4, textAlign: 'center' }}>
                      保存后可在演讲视频、PPT讲解、对话等模块使用
                    </Text>
                  </>
                ) : (
                  <div style={{ textAlign: 'center', padding: '40px 0' }}>
                    <PlayCircleOutlined style={{ fontSize: 48, color: '#d9d9d9' }} />
                    <div style={{ marginTop: 16 }}>
                      <Text type="secondary">混合结果将显示在这里</Text>
                    </div>
                  </div>
                )}
              </Card>
            </Col>
          </Row>
        </TabPane>
      </Tabs>

      <Modal title="上传参考音频" open={isModalOpen} onCancel={() => setIsModalOpen(false)} footer={null}>
        <Form form={form} onFinish={handleUpload} layout="vertical">
          <Form.Item name="name" label="音色名称" rules={[{ required: true }]}>
            <Input placeholder="给这个音色命名" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="简单描述这个音色特点" />
          </Form.Item>
          <Form.Item name="file" label="参考音频" rules={[{ required: true }]}>
            <Upload beforeUpload={() => false} maxCount={1} accept="audio/*">
              <Button icon={<UploadOutlined />}>选择音频文件</Button>
            </Upload>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={uploading} block>上传</Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 保存混合音色弹窗 */}
      <Modal
        title="保存混合音色"
        open={blendSaveOpen}
        onCancel={() => setBlendSaveOpen(false)}
        onOk={handleSaveBlend}
        confirmLoading={blendSaving}
        okText="保存"
        cancelText="取消"
      >
        <Form layout="vertical">
          <Form.Item label="音色名称" required>
            <Input
              placeholder="如：温柔知性女声"
              value={blendSaveName}
              onChange={e => setBlendSaveName(e.target.value)}
            />
          </Form.Item>
          <Form.Item label="描述（可选）">
            <Input.TextArea
              placeholder="如：温柔桃子60% + 邻家女孩40%，适合温柔场景"
              value={blendSaveDesc}
              onChange={e => setBlendSaveDesc(e.target.value)}
              rows={2}
            />
          </Form.Item>
          <div style={{ padding: '8px 12px', background: '#f5f5fa', borderRadius: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>混合配置：</Text>
            <div style={{ marginTop: 4 }}>
              {blendVoices.map((v, i) => (
                <Tag key={v.id} color="purple">
                  {v.name} ({Math.round((blendWeights[v.id] || 0.5) * 100)}%)
                </Tag>
              ))}
            </div>
          </div>
        </Form>
      </Modal>
    </div>
  )
}

export default VoiceManager
