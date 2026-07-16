import React, { useState } from 'react'
import { Card, Form, Input, Select, Button, message, Divider } from 'antd'

const { Option } = Select

function SettingsPage() {
  const [llmForm] = Form.useForm()
  const [ttsForm] = Form.useForm()

  const saveLLMSettings = (values) => {
    // 实际应调用API保存配置
    console.log('LLM设置:', values)
    message.success('LLM配置已保存（本地演示）')
  }

  const saveTTSSettings = (values) => {
    console.log('TTS设置:', values)
    message.success('TTS配置已保存（本地演示）')
  }

  return (
    <div>
      <h2>系统设置</h2>

      <Card title="LLM 大模型配置" style={{ marginBottom: 24 }}>
        <Form form={llmForm} onFinish={saveLLMSettings} layout="vertical">
          <Form.Item name="provider" label="提供商" initialValue="openai">
            <Select>
              <Option value="openai">OpenAI</Option>
              <Option value="qwen">通义千问</Option>
              <Option value="azure">Azure OpenAI</Option>
            </Select>
          </Form.Item>
          <Form.Item name="api_key" label="API Key">
            <Input.Password placeholder="输入API Key" />
          </Form.Item>
          <Form.Item name="base_url" label="Base URL">
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item name="model" label="模型" initialValue="gpt-4">
            <Input placeholder="gpt-4 / qwen-max" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit">保存配置</Button>
          </Form.Item>
        </Form>
      </Card>

      <Card title="TTS 语音合成配置">
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
