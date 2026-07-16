import React, { useState } from 'react'
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom'
import { Layout, Menu, Button, theme } from 'antd'
import {
  HomeOutlined,
  UserOutlined,
  AudioOutlined,
  MessageOutlined,
  SettingOutlined,
  VideoCameraOutlined,
  FilePptOutlined,
} from '@ant-design/icons'

import HomePage from './pages/HomePage.jsx'
import AvatarManager from './pages/AvatarManager.jsx'
import VoiceManager from './pages/VoiceManager.jsx'
import ChatPage from './pages/ChatPage.jsx'
import SettingsPage from './pages/SettingsPage.jsx'
import SpeechVideo from './pages/SpeechVideo.jsx'
import PPTPresenter from './pages/PPTPresenter.jsx'

const { Sider, Content, Header } = Layout

function App() {
  const [collapsed, setCollapsed] = useState(false)
  const {
    token: { colorBgContainer },
  } = theme.useToken()

  const menuItems = [
    { key: '/', icon: <HomeOutlined />, label: <Link to="/">首页</Link> },
    { key: '/avatars', icon: <UserOutlined />, label: <Link to="/avatars">形象管理</Link> },
    { key: '/voices', icon: <AudioOutlined />, label: <Link to="/voices">音色管理</Link> },
    { key: '/speech', icon: <VideoCameraOutlined />, label: <Link to="/speech">演讲视频</Link> },
    { key: '/ppt', icon: <FilePptOutlined />, label: <Link to="/ppt">PPT讲解</Link> },
    { key: '/chat', icon: <MessageOutlined />, label: <Link to="/chat">对话</Link> },
    { key: '/settings', icon: <SettingOutlined />, label: <Link to="/settings">设置</Link> },
  ]

  return (
    <BrowserRouter>
      <Layout style={{ minHeight: '100vh' }}>
        <Sider
          trigger={null}
          collapsible
          collapsed={collapsed}
          theme="dark"
          style={{
            overflow: 'auto',
            height: '100vh',
            position: 'fixed',
            left: 0,
            top: 0,
            bottom: 0,
          }}
        >
          <div className="logo" style={{ height: 64, color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: collapsed ? 14 : 18, fontWeight: 'bold' }}>
            {collapsed ? 'AI' : 'AI数字人'}
          </div>
          <Menu theme="dark" mode="inline" defaultSelectedKeys={['/']} items={menuItems} />
        </Sider>
        <Layout style={{ marginLeft: collapsed ? 80 : 200, transition: 'all 0.2s' }}>
          <Header style={{ padding: 0, background: colorBgContainer, display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingLeft: 24, paddingRight: 24 }}>
            <Button type="text" onClick={() => setCollapsed(!collapsed)}>
              {collapsed ? '展开' : '收起'}
            </Button>
            <div style={{ fontWeight: 'bold', fontSize: 18 }}>AI数字人平台</div>
            <div></div>
          </Header>
          <Content style={{ margin: '24px 16px', padding: 24, background: colorBgContainer, borderRadius: 8, minHeight: 280 }}>
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
    </BrowserRouter>
  )
}

export default App
