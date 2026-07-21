import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App.jsx'
import './global.css'

const theme = {
  token: {
    colorPrimary: '#5b5bd6',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#ffffff',
    colorText: '#1a1a2e',
    colorTextSecondary: '#6b7280',
    colorBorder: '#e8e8f0',
    colorBgLayout: 'transparent',
    borderRadius: 12,
    fontSize: 14,
    fontFamily: "'Inter', 'PingFang SC', 'Microsoft YaHei', -apple-system, sans-serif",
  },
  components: {
    Layout: {
      siderBg: '#fafafa',
      headerBg: 'rgba(255, 255, 255, 0.85)',
      bodyBg: 'transparent',
    },
    Menu: {
      itemBg: 'transparent',
      subMenuItemBg: 'transparent',
      itemSelectedBg: 'rgba(91, 91, 214, 0.08)',
      itemHoverBg: 'rgba(91, 91, 214, 0.05)',
      itemColor: '#6b7280',
      itemSelectedColor: '#5b5bd6',
    },
    Card: {
      colorBgContainer: '#ffffff',
      colorBorderSecondary: '#e8e8f0',
      boxShadowTertiary: '0 2px 8px rgba(0,0,0,0.04)',
    },
    Button: {
      primaryShadow: '0 2px 8px rgba(91, 91, 214, 0.25)',
    },
    Statistic: {
      contentFontSize: 28,
    },
  },
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN} theme={theme}>
      <App />
    </ConfigProvider>
  </React.StrictMode>,
)
