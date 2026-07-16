# AI Digital Human Platform

基于AI技术的数字人分身平台，支持真人/图片生成数字人、语音对话、PPT数字人讲解等功能。

## 功能特性

- **数字人形象管理**：上传真人照片，自动生成数字人形象
- **音色管理**：支持自定义音色克隆（GPT-SoVITS）+ 14种预置音色
- **2D口型同步**：基于MuseTalk的实时口型同步技术
- **PPT数字人讲解**：上传PPT，自动提取内容，生成数字人讲解视频
- **3D数字人展示**：基于Three.js的3D模型渲染
- **智能对话**：支持多LLM后端（OpenAI/通义千问）

## 技术栈

| 模块 | 技术 |
|---|---|
| 后端 | FastAPI + SQLite + Python 3.14 |
| 前端 | React + Vite + Ant Design + Three.js |
| TTS | Edge-TTS + GPT-SoVITS |
| 口型同步 | MuseTalk |
| GPU | CUDA 12.4+ |

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
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

### MuseTalk部署

参考 [MuseTalk](https://github.com/TMElyralab/MuseTalk) 官方文档部署MuseTalk服务。

### 配置

在 `backend/.env` 中配置：

```env
LIP_SYNC_MODEL=musetalk
TTS_PROVIDER=edge-tts
GPT_SOVITS_API_URL=http://localhost:9880
MUSETALK_API_URL=http://localhost:7861
OPENAI_API_KEY=your_key_here
QWEN_API_KEY=your_key_here
```

## 项目结构

```
├── backend/                # 后端API
│   ├── app/
│   │   ├── main.py         # FastAPI入口
│   │   ├── config.py       # 配置
│   │   ├── database.py     # 数据库
│   │   ├── models/         # 数据模型
│   │   ├── routers/        # API路由
│   │   └── services/       # 业务服务
│   └── requirements.txt
├── frontend/               # 前端
│   ├── src/
│   │   ├── App.jsx         # 主应用
│   │   ├── pages/          # 页面组件
│   │   ├── components/     # 通用组件
│   │   └── services/       # API封装
│   └── package.json
├── MuseTalk/               # 口型同步（git submodule或独立部署）
└── GPT-SoVITS/             # 音色克隆（git submodule或独立部署）
```

## License

MIT License

## 致谢

- [MuseTalk](https://github.com/TMElyralab/MuseTalk) - 口型同步
- [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) - 音色克隆
- [Edge-TTS](https://github.com/rany2/edge-tts) - TTS
