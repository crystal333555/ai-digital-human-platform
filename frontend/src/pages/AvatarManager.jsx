import React, { useState, useEffect, useRef } from 'react'
import { Button, Modal, Form, Input, Upload, Card, Select, message, Tag, Row, Col, Image, Spin, Tooltip, Empty, Typography, Divider } from 'antd'
import { 
  PlusOutlined, UploadOutlined, EyeOutlined, DeleteOutlined, 
  ReloadOutlined, CheckCircleOutlined, WarningOutlined, 
  UserOutlined, ScissorOutlined
} from '@ant-design/icons'
import axios from 'axios'
import { avatarAPI } from '../services/api.js'
import ThreeAvatarViewer from '../components/ThreeAvatarViewer.jsx'

const { Option } = Select
const { Title, Text } = Typography

function AvatarManager() {
  const [avatars, setAvatars] = useState([])
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isViewerOpen, setIsViewerOpen] = useState(false)
  const [selectedAvatar, setSelectedAvatar] = useState(null)
  const [meshData, setMeshData] = useState(null)
  const [meshLoading, setMeshLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [extracting, setExtracting] = useState(null)
  const [form] = Form.useForm()

  // 上传预览状态
  const [uploadPreview, setUploadPreview] = useState(null)
  const [uploadExtracted, setUploadExtracted] = useState(null)
  const [extractingUpload, setExtractingUpload] = useState(false)

  useEffect(() => {
    loadAvatars()
  }, [])

  const loadAvatars = async () => {
    try {
      const res = await avatarAPI.list()
      setAvatars(res.data || [])
    } catch (err) {
      message.error('加载形象失败')
    }
  }

  const normalizeImagePath = (path) => {
    if (!path) return null
    return '/' + path.replace(/^\.\.\//, '').replace(/\\/g, '/').replace(/^\//, '')
  }

  const getImageUrl = (path) => {
    const normalized = normalizeImagePath(path)
    return normalized ? `http://localhost:8000${normalized}` : null
  }

  // 上传时预览图片
  const handleFileChange = (info) => {
    if (info.fileList && info.fileList.length > 0) {
      const file = info.fileList[0].originFileObj
      if (file) {
        const reader = new FileReader()
        reader.onload = (e) => setUploadPreview(e.target.result)
        reader.readAsDataURL(file)
        setUploadExtracted(null)
      }
    } else {
      setUploadPreview(null)
      setUploadExtracted(null)
    }
  }

  // 上传并提取人物
  const handleUpload = async (values) => {
    setUploading(true)
    try {
      const formData = new FormData()
      if (values.file && values.file.fileList && values.file.fileList[0]) {
        formData.append('file', values.file.fileList[0].originFileObj)
      }
      formData.append('name', values.name)
      if (values.description) formData.append('description', values.description)
      if (values.style) formData.append('style', values.style)
      if (values.display_mode) formData.append('display_mode', values.display_mode)

      const res = await avatarAPI.upload(formData)
      message.success('形象创建成功，已自动提取人物')
      setIsModalOpen(false)
      form.resetFields()
      setUploadPreview(null)
      setUploadExtracted(null)
      loadAvatars()
    } catch (err) {
      message.error('上传失败: ' + err.message)
    } finally {
      setUploading(false)
    }
  }

  // 提取人物（去背景）
  const handleExtract = async (id) => {
    setExtracting(id)
    try {
      const res = await avatarAPI.removeBg(id)
      if (res.data?.success) {
        message.success('人物提取成功')
        loadAvatars()
      }
    } catch (err) {
      message.error('提取失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setExtracting(null)
    }
  }

  const handleDelete = async (id) => {
    Modal.confirm({
      title: '确认删除',
      content: '删除后无法恢复，确定删除这个数字人形象吗？',
      okText: '删除',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await avatarAPI.delete(id)
          message.success('删除成功')
          loadAvatars()
        } catch (err) {
          message.error('删除失败')
        }
      }
    })
  }

  const openViewer = async (avatar) => {
    setSelectedAvatar(avatar)
    setMeshLoading(true)
    setMeshData(null)
    setIsViewerOpen(true)
    const normalizedPath = normalizeImagePath(avatar.original_image_path)
    try {
      if (normalizedPath) {
        const response = await axios.post(
          'http://localhost:8000/api/v1/face-mesh/extract-from-path',
          { image_path: normalizedPath.startsWith('/') ? normalizedPath.substring(1) : normalizedPath }
        )
        if (response.data.success) {
          setMeshData(response.data.geometry)
        }
      }
    } catch (err) {
      console.error('Mesh extraction failed:', err)
    } finally {
      setMeshLoading(false)
    }
  }

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 20 }}>
        <Col>
          <Title level={4} style={{ margin: 0 }}>数字人形象管理</Title>
          <Text type="secondary" style={{ fontSize: 13 }}>上传照片自动提取人物，生成透明背景数字人</Text>
        </Col>
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setIsModalOpen(true)} size="large">
            创建新形象
          </Button>
        </Col>
      </Row>

      {avatars.length === 0 ? (
        <Empty description="还没有数字人形象" style={{ padding: 60 }}>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setIsModalOpen(true)}>
            创建第一个形象
          </Button>
        </Empty>
      ) : (
        <Row gutter={[16, 16]}>
          {avatars.map(avatar => (
            <Col xs={24} sm={12} lg={8} xl={6} key={avatar.id}>
              <Card
                hoverable
                style={{ borderRadius: 12, overflow: 'hidden', border: '1px solid #e8e8f0' }}
                bodyStyle={{ padding: 12 }}
              >
                {/* 左右对比预览 */}
                <Row gutter={8} style={{ marginBottom: 8 }}>
                  <Col span={12}>
                    <div style={{ position: 'relative' }}>
                      <Text style={{ fontSize: 11, color: '#9ca3af', position: 'absolute', top: 4, left: 4, zIndex: 1, background: 'rgba(255,255,255,0.8)', padding: '0 4px', borderRadius: 4 }}>原图</Text>
                      <Image
                        src={getImageUrl(avatar.original_image_path)}
                        style={{ width: '100%', height: 140, objectFit: 'cover', borderRadius: 8 }}
                        fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8/+F/PQAJpAN42kzLqAAAAABJRU5ErkJggg=="
                      />
                    </div>
                  </Col>
                  <Col span={12}>
                    <div style={{ position: 'relative' }}>
                      <Text style={{ fontSize: 11, color: '#9ca3af', position: 'absolute', top: 4, left: 4, zIndex: 1, background: 'rgba(255,255,255,0.8)', padding: '0 4px', borderRadius: 4 }}>提取</Text>
                      {avatar.transparent_image_path ? (
                        <Image
                          src={getImageUrl(avatar.transparent_image_path)}
                          style={{ width: '100%', height: 140, objectFit: 'contain', borderRadius: 8, background: 'repeating-conic-gradient(#f0f0f5 0% 25%, #ffffff 0% 50%) 50% / 16px 16px' }}
                          fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8/+F/PQAJpAN42kzLqAAAAABJRU5ErkJggg=="
                        />
                      ) : (
                        <div style={{
                          width: '100%', height: 140, borderRadius: 8,
                          background: '#f5f5fa', display: 'flex', alignItems: 'center', justifyContent: 'center',
                          border: '1px dashed #d1d5e0'
                        }}>
                          <Tooltip title="未提取人物">
                            <WarningOutlined style={{ fontSize: 24, color: '#d1d5e0' }} />
                          </Tooltip>
                        </div>
                      )}
                    </div>
                  </Col>
                </Row>

                {/* 名称和状态 */}
                <div style={{ marginBottom: 8 }}>
                  <Text strong style={{ fontSize: 14 }}>{avatar.name}</Text>
                  <div style={{ marginTop: 4 }}>
                    {avatar.transparent_image_path ? (
                      <Tag color="green" style={{ fontSize: 11 }}><CheckCircleOutlined /> 已提取</Tag>
                    ) : (
                      <Tag color="orange" style={{ fontSize: 11 }}><WarningOutlined /> 未提取</Tag>
                    )}
                    {avatar.style && <Tag style={{ fontSize: 11 }}>{avatar.style}</Tag>}
                    {avatar.display_mode && <Tag color="blue" style={{ fontSize: 11 }}>{avatar.display_mode}</Tag>}
                  </div>
                </div>

                {/* 操作按钮 */}
                <Row gutter={4}>
                  <Col span={8}>
                    <Button size="small" block icon={<EyeOutlined />} onClick={() => openViewer(avatar)} title="3D预览">
                      3D
                    </Button>
                  </Col>
                  <Col span={8}>
                    {avatar.transparent_image_path ? (
                      <Button 
                        size="small" block 
                        icon={<ReloadOutlined />}
                        loading={extracting === avatar.id}
                        onClick={() => handleExtract(avatar.id)}
                        title="重新提取人物"
                      >
                        重提
                      </Button>
                    ) : (
                      <Button 
                        size="small" block type="primary"
                        icon={<ScissorOutlined />}
                        loading={extracting === avatar.id}
                        onClick={() => handleExtract(avatar.id)}
                        title="提取人物"
                      >
                        提取
                      </Button>
                    )}
                  </Col>
                  <Col span={8}>
                    <Button size="small" block danger icon={<DeleteOutlined />} onClick={() => handleDelete(avatar.id)} title="删除" />
                  </Col>
                </Row>
              </Card>
            </Col>
          ))}
        </Row>
      )}

      {/* 创建形象弹窗 */}
      <Modal 
        title="创建数字人形象" 
        open={isModalOpen} 
        onCancel={() => { setIsModalOpen(false); setUploadPreview(null); setUploadExtracted(null); form.resetFields() }} 
        footer={null}
        width={560}
      >
        <Form form={form} onFinish={handleUpload} layout="vertical">
          <Form.Item name="name" label="形象名称" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="给数字人起个名字" />
          </Form.Item>
          <Form.Item name="description" label="描述（可选）">
            <Input.TextArea rows={2} placeholder="简单描述这个数字人" />
          </Form.Item>
          <Row gutter={12}>
            <Col span={12}>
              <Form.Item name="style" label="风格" initialValue="realistic">
                <Select>
                  <Option value="realistic">写实</Option>
                  <Option value="anime">动漫</Option>
                  <Option value="cartoon">卡通</Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="display_mode" label="显示模式" initialValue="both">
                <Select>
                  <Option value="2d">仅2D</Option>
                  <Option value="3d">仅3D</Option>
                  <Option value="both">2D+3D</Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
          <Form.Item name="file" label="上传照片" rules={[{ required: true, message: '请选择照片' }]} extra="建议正面清晰人像，上传后自动提取人物去背景">
            <Upload 
              beforeUpload={() => false} 
              maxCount={1} 
              accept="image/*"
              onChange={handleFileChange}
              listType="picture-card"
              style={{ width: '100%' }}
            >
              {uploadPreview ? null : (
                <div>
                  <UploadOutlined style={{ fontSize: 24, color: '#9ca3af' }} />
                  <div style={{ marginTop: 8, fontSize: 12, color: '#9ca3af' }}>点击上传</div>
                </div>
              )}
            </Upload>
          </Form.Item>

          {/* 上传预览 */}
          {uploadPreview && (
            <div style={{ marginBottom: 16, padding: 12, background: '#f5f5fa', borderRadius: 8 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>照片预览（上传后将自动提取人物）：</Text>
              <img src={uploadPreview} style={{ width: '100%', maxHeight: 200, objectFit: 'contain', borderRadius: 8, marginTop: 8 }} alt="预览" />
            </div>
          )}

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={uploading} block size="large">
              上传并创建
            </Button>
          </Form.Item>
        </Form>
      </Modal>

      {/* 3D预览弹窗 */}
      <Modal
        title={selectedAvatar ? `${selectedAvatar.name} - 3D预览` : '3D预览'}
        open={isViewerOpen}
        onCancel={() => setIsViewerOpen(false)}
        footer={null}
        width={600}
      >
        {meshLoading ? (
          <div style={{ textAlign: 'center', padding: 40 }}>
            <Spin size="large" />
            <p style={{ marginTop: 16 }}>加载3D模型中...</p>
          </div>
        ) : meshData ? (
          <ThreeAvatarViewer geometry={meshData} />
        ) : (
          <p>3D模型加载失败</p>
        )}
      </Modal>
    </div>
  )
}

export default AvatarManager
