import React, { useState, useEffect } from 'react'
import { Row, Col, Card, Statistic, Button, Typography, Space } from 'antd'
import { UserOutlined, AudioOutlined, MessageOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { Link } from 'react-router-dom'

const { Title, Paragraph } = Typography

function HomePage() {
  const [stats, setStats] = useState({
    avatars: 0,
    voices: 0,
    conversations: 0,
  })

  useEffect(() => {
    // 模拟加载统计数据
    setTimeout(() => {
      setStats({ avatars: 3, voices: 2, conversations: 12 })
    }, 500)
  }, [])

  return (
    <div>
      <Title level={2}>欢迎使用 AI 数字人平台</Title>
      <Paragraph type="secondary">
        基于真人照片与语音，快速创建可对话的2D/3D数字人分身。
      </Paragraph>

      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="数字人形象" value={stats.avatars} prefix={<UserOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="克隆音色" value={stats.voices} prefix={<AudioOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="对话次数" value={stats.conversations} prefix={<MessageOutlined />} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="系统状态" value="运行中" prefix={<ThunderboltOutlined />} valueStyle={{ color: '#52c41a' }} />
          </Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col span={12}>
          <Card title="快速开始">
            <Space direction="vertical" style={{ width: '100%' }}>
              <Link to="/avatars">
                <Button type="primary" block size="large" icon={<UserOutlined />}>
                  创建数字人形象
                </Button>
              </Link>
              <Link to="/voices">
                <Button block size="large" icon={<AudioOutlined />}>
                  上传并克隆音色
                </Button>
              </Link>
              <Link to="/chat">
                <Button block size="large" icon={<MessageOutlined />}>
                  开始对话
                </Button>
              </Link>
            </Space>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="功能特性">
            <ul>
              <li>上传真人照片，生成2D/3D数字人形象</li>
              <li>10秒语音样本克隆专属音色</li>
              <li>大语言模型驱动自然对话</li>
              <li>实时口型同步与表情驱动</li>
              <li>支持Web浏览器直接交互</li>
              <li>预留机器人实体API接口</li>
            </ul>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default HomePage
