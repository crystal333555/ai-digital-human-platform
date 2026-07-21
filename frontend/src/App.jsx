import React, { useState, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Link, useLocation } from 'react-router-dom'
import { Layout, Menu, Button, Tooltip } from 'antd'
import {
  HomeOutlined,
  UserOutlined,
  AudioOutlined,
  MessageOutlined,
  SettingOutlined,
  VideoCameraOutlined,
  FilePptOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import axios from 'axios'

import HomePage from './pages/HomePage.jsx'
import AvatarManager from './pages/AvatarManager.jsx'
import VoiceManager from './pages/VoiceManager.jsx'
import ChatPage from './pages/ChatPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import SpeechVideo from './pages/SpeechVideo.jsx'
import PPTPresenter from './pages/PPTPresenter.jsx'

const { Sider, Content, Header } = Layout

function ServiceStatus() {
  const [services, setServices] = useState({ musetalk: {}, gpt_sovits: {} })

  useEffect(() => {
    const check = async () => {
      try {
        const resp = await axios.get('/api/v1/system/services')
        setServices(resp.data)
      } catch {
        setServices({
          musetalk: { status: 'offline' },
          gpt_sovits: { status: 'offline' },
        })
      }
    }
    check()
    const timer = setInterval(check, 30000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div className="service-status">
      <Tooltip title={`MuseTalk: ${services.musetalk?.status || 'unknown'}`}>
        <div className="status-item">
          <span className={`status-dot ${services.musetalk?.status === 'online' ? 'online' : 'offline'}`} />
          <span>MuseTalk</span>
        </div>
      </Tooltip>
      <Tooltip title={`TTS: ${services.gpt_sovits?.status || 'unknown'}`}>
        <div className="status-item">
          <span className={`status-dot ${services.gpt_sovits?.status === 'online' ? 'online' : 'offline'}`} />
          <span>TTS</span>
        </div>
      </Tooltip>
    </div>
  )
}

function App() {
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()

  const menuItems = [
    { key: '/', icon: <HomeOutlined />, label: <Link to="/">首页</Link> },
    { key: '/avatars', icon: <UserOutlined />, label: <Link to="/avatars">形象管理</Link> },
    { key: '/voices', icon: <AudioOutlined />, label: <Link to="/voices">音色管理</Link> },
    { key: '/speech', icon: <VideoCameraOutlined />, label: <Link to="/speech">演讲视频</Link> },
    { key: '/ppt', icon: <FilePptOutlined />, label: <Link to="/ppt">PPT讲解</Link> },
    { key: '/chat', icon: <MessageOutlined />, label: <Link to="/chat">对话</Link> },
    { key: '/settings', icon: <SettingOutlined />, label: <Link to="/settings">设置</Link> },
  ]

  const selectedKey = '/' + location.pathname.split('/')[1]

  return (
    <Layout className="app-layout" style={{ minHeight: '100vh' }}>
      <div className="app-bg" />
      <div className="app-bg-blob blob-1" />
      <div className="app-bg-blob blob-2" />

      <Sider
        trigger={null}
        collapsible
        collapsed={collapsed}
        className="app-sider"
        style={{
          overflow: 'auto',
          height: '100vh',
          position: 'fixed',
          left: 0,
          top: 0,
          bottom: 0,
          zIndex: 10,
        }}
      >
        <div className="app-logo">
          <div className="app-logo-icon">
            <ThunderboltOutlined />
          </div>
          {!collapsed && (
            <div className="app-logo-text">
              <span>数字人</span>平台
            </div>
          )}
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
        />
      </Sider>

      <Layout style={{ marginLeft: collapsed ? 80 : 200, transition: 'all 0.2s', position: 'relative', zIndex: 1 }}>
        <Header className="app-header">
          <Button
            type="text"
            onClick={() => setCollapsed(!collapsed)}
            style={{ fontSize: 18, color: 'var(--text-secondary)' }}
          >
            {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          </Button>
          <ServiceStatus />
        </Header>

        <Content className="app-content">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/avatars" element={<AvatarManager />} />
            <Route path="/voices" element={<VoiceManager />} />
            <Route path="/speech" element={<SpeechVideo />} />
            <Route path="/ppt" element={<PPTPresenter />} />
            <Route path="/chat" element={<ChatPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  )
}

export default function AppWrapper() {
  return (
    <BrowserRouter>
      <App />
    </BrowserRouter>
  )
}
