import React, { useState, useEffect } from 'react'
import { Row, Col, Card, Button, Typography, Space, Tag } from 'antd'
import {
  UserOutlined,
  AudioOutlined,
  MessageOutlined,
  ThunderboltOutlined,
  VideoCameraOutlined,
  FilePptOutlined,
  ArrowRightOutlined,
  RobotOutlined,
  EyeOutlined,
  ApiOutlined,
  SettingOutlined,
} from '@ant-design/icons'
import { Link } from 'react-router-dom'
import axios from 'axios'

const { Title, Paragraph, Text } = Typography

function HomePage() {
  const [stats, setStats] = useState({ avatars: 0, voices: 0, conversations: 0 })

  useEffect(() => {
    const load = async () => {
      try {
        const [avatarResp, voiceResp] = await Promise.all([
          axios.get('/api/v1/avatars/'),
          axios.get('/api/v1/voices/'),
        ])
        setStats({
          avatars: avatarResp.data?.length || 0,
          voices: voiceResp.data?.length || 0,
          conversations: 0,
        })
      } catch {
        setStats({ avatars: 0, voices: 0, conversations: 0 })
      }
    }
    load()
  }, [])

  const statCards = [
    { title: '数字人形象', value: stats.avatars, icon: <UserOutlined />, color: 'purple', link: '/avatars' },
    { title: '克隆音色', value: stats.voices, icon: <AudioOutlined />, color: 'cyan', link: '/voices' },
    { title: '对话记录', value: stats.conversations, icon: <MessageOutlined />, color: 'pink', link: '/chat' },
  ]

  const features = [
    {
      title: '形象管理',
      desc: '上传真人照片生成数字人形象，支持2D写实与3D展示',
      icon: <UserOutlined />,
      color: 'purple',
      link: '/avatars',
    },
    {
      title: '音色克隆',
      desc: '录制3-10秒参考音频，克隆专属音色，支持14种预置音色',
      icon: <AudioOutlined />,
      color: 'cyan',
      link: '/voices',
    },
    {
      title: '智能对话',
      desc: '基于LLM的实时对话，数字人口型同步，自然交互',
      icon: <MessageOutlined />,
      color: 'pink',
      link: '/chat',
    },
    {
      title: '演讲视频',
      desc: '输入文字生成数字人演讲视频，口型同步+语音合成',
      icon: <VideoCameraOutlined />,
      color: 'green',
      link: '/speech',
    },
    {
      title: 'PPT讲解',
      desc: '上传PPT自动提取内容，数字人画中画讲解，一键生成视频',
      icon: <FilePptOutlined />,
      color: 'purple',
      link: '/ppt',
    },
    {
      title: '系统设置',
      desc: '配置API密钥、模型路径、服务地址等参数',
      icon: <SettingOutlined />,
      color: 'cyan',
      link: '/settings',
    },
  ]

  const colorMap = {
    purple: { bg: 'rgba(91, 91, 214, 0.1)', color: '#5b5bd6' },
    cyan: { bg: 'rgba(6, 182, 212, 0.1)', color: '#06b6d4' },
    pink: { bg: 'rgba(236, 72, 153, 0.1)', color: '#ec4899' },
    green: { bg: 'rgba(16, 185, 129, 0.1)', color: '#10b981' },
  }

  return (
    <div>
      {/* Hero */}
      <div className="hero-section fade-in">
        <div className="hero-badge">
          <ThunderboltOutlined />
          AI Powered Digital Human Platform
        </div>
        <h1 className="hero-title">
          打造你的<span>AI数字分身</span>
        </h1>
        <p className="hero-subtitle">
          从照片到数字人，从文字到语音，从PPT到讲解视频——一站式AI数字人创作平台
        </p>
      </div>

      {/* 统计卡片 */}
      <Row gutter={[20, 20]} style={{ marginBottom: 32 }}>
        {statCards.map((stat, i) => {
          const c = colorMap[stat.color]
          return (
            <Col xs={24} sm={8} key={stat.title}>
              <Link to={stat.link}>
                <div className={`stat-card fade-in fade-in-delay-${i + 1}`}>
                  <div className="stat-icon" style={{ background: c.bg, color: c.color }}>
                    {stat.icon}
                  </div>
                  <div className="stat-value">{stat.value}</div>
                  <div className="stat-label">{stat.title}</div>
                </div>
              </Link>
            </Col>
          )
        })}
      </Row>

      {/* 功能区 */}
      <div style={{ marginBottom: 16 }}>
        <div className="section-title">核心功能</div>
        <div className="section-subtitle">点击进入对应功能模块</div>
      </div>

      <Row gutter={[20, 20]}>
        {features.map((feat, i) => {
          const c = colorMap[feat.color]
          return (
            <Col xs={24} sm={12} lg={8} key={feat.title}>
              <Link to={feat.link}>
                <div className={`feature-card fade-in fade-in-delay-${(i % 6) + 1}`}>
                  <div className="feature-icon" style={{ background: c.bg, color: c.color }}>
                    {feat.icon}
                  </div>
                  <div className="feature-title">{feat.title}</div>
                  <div className="feature-desc">{feat.desc}</div>
                  <ArrowRightOutlined className="feature-arrow" />
                </div>
              </Link>
            </Col>
          )
        })}
      </Row>
    </div>
  )
}

export default HomePage
