# AI Digital Human Platform v2.0

基于AI技术的数字人分身平台，支持真人/图片生成数字人、语音对话、PPT数字人讲解、演讲视频生成等功能。

## ✨ v2.0 新功能

- 🎭 **LivePortrait高质量模式** — 自然微表情+头部运动+眼神移动
- 🖥️ **双机GPU协作** — 机器A(TTS) + 机器B(MuseTalk/LivePortrait)，彻底解决GPU争抢
- 📑 **PPT分段管理** — 逐页生成+预览+选择性合成，支持暂停/重新生成
- 🎨 **背景替换** — 9个默认背景（办公室/博物馆/舞台等）+ 自定义上传
- 🎵 **音色混合** — 2~3个音色加权混合，保存后可在所有模块使用
- 👤 **形象去背景** — rembg+u2net自动提取人物，透明PNG叠加到任意背景
- ⚡ **微表情增强器** — 眨眼+眉毛+头部摆动+呼吸感（MuseTalk模式）
- 📊 **服务管理** — 健康检查+自动恢复守护
- 🎨 **前端UI升级** — 简洁明亮风格+卡片式布局

## 功能特性

| 模块 | 说明 |
|---|---|
| **数字人形象管理** | 上传照片→自动去背景→生成透明PNG，卡片式对比预览 |
| **音色管理** | 自定义音色克隆(GPT-SoVITS) + 14种预置音色 + 音色混合 |
| **2D口型同步** | MuseTalk（快速）+ LivePortrait（高质量）双模式 |
| **PPT数字人讲解** | 上传PPT→提取页面→编辑讲稿→画中画合成视频 |
| **演讲视频生成** | 文字→TTS→口型同步→背景替换→微表情增强 |
| **3D数字人展示** | Three.js + WebGL2 渲染 |
| **智能对话** | WebSocket实时对话，支持多LLM后端 |

## 技术栈

| 模块 | 技术 |
|---|---|
| 后端 | FastAPI + SQLite + Python 3.14 |
| 前端 | React + Vite + Ant Design + Three.js |
| TTS | Edge-TTS + GPT-SoVITS（音色克隆）|
| 口型同步 | MuseTalk + LivePortrait |
| 微表情增强 | OpenCV（眨眼/眉毛/头部摆动/呼吸感）|
| 去背景 | rembg + u2net |
| GPU | CUDA 12.4+（双机协作：RTX 4090 + RTX 5090）|

## 架构图

```
机器A (RTX 4090 Laptop, 16GB)          机器B (RTX 5090 Laptop, 24GB)
├── 前端 :5173                          ├── MuseTalk :7861（快速模式）
├── 后端API :8000                       ├── LivePortrait :7863（高质量模式）
├── GPT-SoVITS :9880                    ├── 文件中转服务 :7862
└── ──────── 网线直连 2ms ──────────────┘
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- NVIDIA GPU (8GB+ VRAM)

### 后端启动

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

### MuseTalk部署

参考 [MuseTalk](https://github.com/TMElyralab/MuseTalk) 官方文档。

### LivePortrait部署（可选，高质量模式）

参考 [LivePortrait](https://github.com/KwaiVGI/LivePortrait) 官方文档。

### 配置

在 `backend/.env` 中配置：

```env
LIP_SYNC_MODEL=musetalk
TTS_PROVIDER=edge-tts
GPT_SOVITS_API_URL=http://localhost:9880
MUSETALK_API_URL=http://localhost:7861
LIVEPORTRAIT_API_URL=http://localhost:7863
OPENAI_API_KEY=your_key_here
QWEN_API_KEY=your_key_here
```

## 项目结构

```
├── backend/                    # 后端API
│   ├── app/
│   │   ├── main.py             # FastAPI入口 + 服务健康检查
│   │   ├── config.py           # 配置
│   │   ├── routers/            # API路由
│   │   │   ├── avatar.py       # 形象管理 + 去背景 + 背景图
│   │   │   ├── voice.py        # 音色管理
│   │   │   ├── voice_lib.py    # 预置音色库 + 混合
│   │   │   ├── speech.py       # 演讲视频生成
│   │   │   ├── ppt.py          # PPT讲解（分段管理）
│   │   │   └── chat.py         # WebSocket对话
│   │   ├── services/
│   │   │   ├── lip_sync_service.py          # 口型同步（MuseTalk+LivePortrait）
│   │   │   ├── liveportrait_service.py      # LivePortrait封装
│   │   │   ├── micro_expression_enhancer.py # 微表情增强
│   │   │   ├── gpu_coordinator.py           # GPU内存管理
│   │   │   ├── tts_service.py               # TTS封装
│   │   │   ├── voice_blending.py            # 音色混合
│   │   │   ├── ppt_video_composer.py        # 画中画合成
│   │   │   └── avatar_service.py            # 形象处理
│   │   └── models/             # 数据模型
│   └── requirements.txt
├── frontend/                   # 前端
│   └── src/
│       ├── App.jsx             # 路由布局
│       ├── pages/
│       │   ├── HomePage.jsx         # 首页
│       │   ├── AvatarManager.jsx    # 形象管理（卡片式）
│       │   ├── VoiceManager.jsx     # 音色管理（混合+试听）
│       │   ├── SpeechVideo.jsx      # 演讲视频（背景+分辨率+占比）
│       │   ├── PPTPresenter.jsx     # PPT讲解（分段管理）
│       │   └── ChatPage.jsx         # 对话
│       └── components/
│           └── ThreeAvatarViewer.jsx # 3D渲染
└── docs/
    └── skills-reference.md     # 10个Skill技能文档
```

## 双机部署

详见 `机器B-MuseTalk部署指南.md`

### 机器A（主机）
- 前端 + 后端API + GPT-SoVITS
- IP: 192.168.100.1

### 机器B（推理机）
- MuseTalk + LivePortrait + 文件中转服务
- IP: 192.168.100.3

## 版本历史

- **v2.0.0** — 微表情增强+LivePortrait+双机GPU+PPT分段管理+背景替换+音色混合
- **v1.0.0** — 初始版本：形象管理+音色管理+口型同步+PPT讲解+对话

## License

MIT
