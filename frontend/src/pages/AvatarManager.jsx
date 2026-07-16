import React, { useState, useEffect } from 'react'
import { Table, Button, Modal, Form, Input, Upload, Card, Select, message, Tag } from 'antd'
import { PlusOutlined, UploadOutlined, EyeOutlined, DeleteOutlined } from '@ant-design/icons'
import axios from 'axios'
import { avatarAPI } from '../services/api.js'
import ThreeAvatarViewer from '../components/ThreeAvatarViewer.jsx'

const { Option } = Select

function AvatarManager() {
  const [avatars, setAvatars] = useState([])
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [isViewerOpen, setIsViewerOpen] = useState(false)
  const [selectedAvatar, setSelectedAvatar] = useState(null)
  const [meshData, setMeshData] = useState(null)
  const [meshLoading, setMeshLoading] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [form] = Form.useForm()

  useEffect(() => {
    loadAvatars()
  }, [])

  const loadAvatars = async () => {
    try {
      const res = await avatarAPI.list()
      setAvatars(res.data || [])
    } catch (err) {
      console.error('加载形象失败', err)
      message.error('加载形象失败')
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
      if (values.style) formData.append('style', values.style)
      if (values.display_mode) formData.append('display_mode', values.display_mode)

      await avatarAPI.upload(formData)
      message.success('形象创建成功')
      setIsModalOpen(false)
      form.resetFields()
      loadAvatars()
    } catch (err) {
      message.error('上传失败: ' + err.message)
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (id) => {
    try {
      await avatarAPI.delete(id)
      message.success('删除成功')
      loadAvatars()
    } catch (err) {
      message.error('删除失败')
    }
  }

  const normalizeImagePath = (path) => {
    if (!path) return null
    // 处理旧路径格式：../uploads/avatars\xxx.jpg -> /uploads/avatars/xxx.jpg
    return '/' + path.replace(/^\.\.\//, '').replace(/\\/g, '/').replace(/^\//, '')
  }

  const openViewer = async (avatar) => {
    setSelectedAvatar(avatar)
    setMeshLoading(true)
    setMeshData(null)
    setIsViewerOpen(true)
    
    const normalizedPath = normalizeImagePath(avatar.original_image_path)
    
    // 调用后端生成3D mesh
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

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '名称', dataIndex: 'name' },
    { title: '风格', dataIndex: 'style', render: (t) => <Tag>{t}</Tag> },
    { title: '显示模式', dataIndex: 'display_mode', render: (t) => <Tag color="blue">{t}</Tag> },
    { title: '创建时间', dataIndex: 'created_at' },
    {
      title: '操作',
      key: 'action',
      render: (_, record) => (
        <>
          <Button icon={<EyeOutlined />} onClick={() => openViewer(record)}>预览</Button>
          <Button icon={<DeleteOutlined />} danger onClick={() => handleDelete(record.id)} style={{ marginLeft: 8 }}>删除</Button>
        </>
      ),
    },
  ]

  return (
    <div>
      <h2>数字人形象管理</h2>
      <Button type="primary" icon={<PlusOutlined />} onClick={() => setIsModalOpen(true)} style={{ marginBottom: 16 }}>
        创建新形象
      </Button>

      <Table columns={columns} dataSource={avatars} rowKey="id" />

      <Modal title="创建数字人形象" open={isModalOpen} onCancel={() => setIsModalOpen(false)} footer={null}>
        <Form form={form} onFinish={handleUpload} layout="vertical">
          <Form.Item name="name" label="形象名称" rules={[{ required: true }]}>
            <Input placeholder="给数字人起个名字" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} placeholder="简单描述这个数字人" />
          </Form.Item>
          <Form.Item name="style" label="风格" initialValue="realistic">
            <Select placeholder="选择风格">
              <Option value="realistic">写实</Option>
              <Option value="anime">动漫</Option>
              <Option value="cartoon">卡通</Option>
            </Select>
          </Form.Item>
          <Form.Item name="display_mode" label="显示模式" initialValue="both">
            <Select placeholder="选择显示模式">
              <Option value="2d">仅2D</Option>
              <Option value="3d">仅3D</Option>
              <Option value="both">2D+3D</Option>
            </Select>
          </Form.Item>
          <Form.Item name="file" label="上传照片" rules={[{ required: true }]}>
            <Upload beforeUpload={() => false} maxCount={1} accept="image/*">
              <Button icon={<UploadOutlined />}>选择照片</Button>
            </Upload>
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={uploading} block>创建</Button>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="形象预览"
        open={isViewerOpen}
        onCancel={() => setIsViewerOpen(false)}
        width={900}
        footer={null}
      >
        <div style={{ display: 'flex', gap: 20, height: 500 }}>
          {/* 2D 照片展示 */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <h4 style={{ marginBottom: 8 }}>2D 照片</h4>
            <div style={{ flex: 1, background: '#f0f0f0', borderRadius: 8, overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              {selectedAvatar?.original_image_path ? (() => {
                const imgPath = normalizeImagePath(selectedAvatar.original_image_path)
                return (
                  <img
                    src={`http://localhost:8000${imgPath}`}
                    alt={selectedAvatar.name}
                    style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                  />
                )
              })() : (
                <span>无照片</span>
              )}
            </div>
          </div>

          {/* 3D */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
            <h4 style={{ marginBottom: 8 }}>
              3D 模型
              {meshLoading && <Tag color="blue" style={{ marginLeft: 8 }}>生成中...</Tag>}
              {!meshLoading && !meshData && <Tag color="orange" style={{ marginLeft: 8 }}>照片驱动</Tag>}
              {meshData && <Tag color="green" style={{ marginLeft: 8 }}>已生成</Tag>}
            </h4>
            <div style={{ flex: 1, background: '#f0f0f0', borderRadius: 8, overflow: 'hidden', position: 'relative' }}>
              {meshLoading ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                  <div>正在从照片生成3D人脸...</div>
                </div>
              ) : meshData ? (
                <ThreeAvatarViewer
                  meshData={meshData}
                  imageUrl={selectedAvatar?.original_image_path ? `http://localhost:8000${normalizeImagePath(selectedAvatar.original_image_path)}` : null}
                />
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', flexDirection: 'column', color: '#999' }}>
                  <p>照片驱动3D人脸生成</p>
                  <p style={{ fontSize: 12 }}>请上传包含正脸的照片</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </Modal>
    </div>
  )
}

export default AvatarManager
