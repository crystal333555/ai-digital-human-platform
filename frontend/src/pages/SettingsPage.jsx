import React, { useState, useEffect, useCallback } from 'react'
import { Card, Form, Input, Select, Button, message, Divider, Row, Col, Tag, Space, Spin, Tooltip, Statistic, Typography } from 'antd'
import { 
  PlayCircleOutlined, PauseCircleOutlined, ReloadOutlined, 
  CheckCircleOutlined, CloseCircleOutlined, LoadingOutlined,
  CloudServerOutlined, ThunderboltOutlined, ApiOutlined
} from '@ant-design/icons'
import axios from 'axios'

const { Option } = Select
const { Title, Text } = Typography

function SettingsPage() {
  const [llmForm] = Form.useForm()
  const [ttsForm] = Form.useForm()
  const [services, setServices] = useState({})
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState({})

  const loadServices = useCallback(async () => {
    try {
      const res = await axios.get('/api/v1/system/services/all')
      setServices(res.data)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    loadServices()
    const timer = setInterval(loadServices, 10000)
    return () => clearInterval(timer)
  }, [loadServices])

  const handleServiceAction = async (key, action) => {
    setActionLoading(prev => ({ ...prev, [`${key}_${action}`]: true }))
    try {
      const res = await axios.post(`/api/v1/system/services/${key}/${action}`)
      message[res.data.success ? 'success' : 'warning'](res.data.message)
      setTimeout(loadServices, 2000)
    } catch (err) {
      message.error('操作失败: ' + (err.response?.data?.detail || err.message))
    } finally {
      setActionLoading(prev => ({ ...prev, [`${key}_${action}`]: false }))
    }
  }

  const saveLLMSettings = (values) => {
    console.log('LLM设置:', values)
    message.success('LLM配置已保存（本地演示）')
  }

  const saveTTSSettings = (values) => {
    console.log('TTS设置:', values)
    message.success('TTS配置已保存（本地演示）')
  }

  const statusIcon = (status) => {
    if (status === 'online') return <CheckCircleOutlined style={{ color: '#52c41a' }} />
    if (status === 'degraded') return <LoadingOutlined style={{ color: '#faad14' }} />
    return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
  }

  const statusColor = (status) => {
    if (status === 'online') return 'success'
    if (status === 'degraded') return 'warning'
    return 'error'
  }

  const serviceIcons = {
    backend: <ApiOutlined />,
    frontend: <CloudServerOutlined />,
    musetalk: <ThunderboltOutlined />,
    gpt_sovits: <ThunderboltOutlined />,
  }

  return (
    <div>
      <Title level={4}>系统设置</Title>

      {/* 服务控制面板 */}
      <Card 
        title={<Space><CloudServerOutlined /> 服务控制面板</Space>}
        extra={<Button size="small" onClick={loadServices} loading={loading}>刷新</Button>}
        style={{ marginBottom: 24, borderRadius: 12 }}
      >
        <Row gutter={[16, 16]}>
          {Object.entries(services).map(([key, svc]) => (
            <Col span={12} key={key}>
              <Card 
                size="small" 
                style={{ 
                  borderRadius: 8,
                  border: svc.status === 'online' ? '1px solid #b7eb8f' : 
                          svc.status === 'degraded' ? '1px solid #ffd591' : '1px solid #ffa39e',
                  background: svc.status === 'online' ? '#f6ffed' :
                              svc.status === 'degraded' ? '#fffbe6' : '#fff2f0',
                }}
              >
                <Row align="middle" justify="space-between">
                  <Col>
                    <Space>
                      {serviceIcons[key]}
                      <Text strong>{svc.name}</Text>
                      {statusIcon(svc.status)}
                      <Tag color={statusColor(svc.status)}>
                        {svc.status === 'online' ? '在线' : svc.status === 'degraded' ? '部分可用' : '离线'}
                      </Tag>
                    </Space>
                  </Col>
                </Row>
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    端口: {svc.port} | 监听: {svc.port_listening ? '✅' : '❌'} | 健康: {svc.health_ok ? '✅' : '❌'}
                  </Text>
                </div>
                {key !== 'backend' && (
                  <Space style={{ marginTop: 12 }}>
                    <Button
                      size="small"
                      type="primary"
                      icon={<PlayCircleOutlined />}
                      loading={actionLoading[`${key}_start`]}
                      disabled={svc.status === 'online'}
                      onClick={() => handleServiceAction(key, 'start')}
                    >
                      启动
                    </Button>
                    <Button
                      size="small"
                      danger
                      icon={<PauseCircleOutlined />}
                      loading={actionLoading[`${key}_stop`]}
                      disabled={svc.status === 'offline'}
                      onClick={() => handleServiceAction(key, 'stop')}
                    >
                      停止
                    </Button>
                    <Button
                      size="small"
                      icon={<ReloadOutlined />}
                      loading={actionLoading[`${key}_restart`]}
                      onClick={() => handleServiceAction(key, 'restart')}
                    >
                      重启
                    </Button>
                  </Space>
                )}
              </Card>
            </Col>
          ))}
        </Row>
        <Divider />
        <Text type="secondary" style={{ fontSize: 12 }}>
          💡 页面每10秒自动刷新服务状态。服务停止后可在面板一键重启。
          后端API无法通过面板停止（需手动关闭命令行窗口）。
        </Text>
      </Card>

      <Card title="LLM 大模型配置" style={{ marginBottom: 24, borderRadius: 12 }}>
        <Form form={llmForm} onFinish={saveLLMSettings} layout="vertical">
          <Form.Item name="provider" label="提供商" initialValue="openai">
            <Select>
              <Option value="openai">OpenAI</Option>
              <Option value="qwen">通义千问</Option>
            </Select>
          </Form.Item>
          <Form.Item name="api_key" label="API Key">
            <Input.Password placeholder="sk-..." />
          </Form.Item>
          <Form.Item name="model" label="模型" initialValue="gpt-4">
            <Input />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit">保存配置</Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="TTS 语音配置" style={{ borderRadius: 12 }}>
        <Form form={ttsForm} onFinish={saveTTSSettings} layout="vertical">
          <Form.Item name="provider" label="TTS引擎" initialValue="edge-tts">
            <Select>
              <Option value="edge-tts">Edge-TTS（免费）</Option>
              <Option value="gpt-sovits">GPT-SoVITS（克隆）</Option>
            </Select>
          </Form.Item>
          <Form.Item name="gpt_sovits_url" label="GPT-SoVITS API地址">
            <Input placeholder="http://localhost:9880" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit">保存配置</Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  )
}

export default SettingsPage