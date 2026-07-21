import os

skills_dir = r'C:\Users\yj821\.psacowork\skills'

skills = {}

skills['musetalk-deploy'] = r'''---
name: musetalk-deploy
description: MuseTalk口型同步模型部署与远程推理。Use when 部署MuseTalk、配置远程推理、解决MuseTalk超时/卡死/GPU OOM、启动文件中转服务。涵盖Windows部署、PyTorch兼容性修复、远程HTTP文件传输。
---

# MuseTalk 部署与远程推理

## 部署环境
- Python 3.10 + PyTorch 2.3.0+cu121（RTX 4090）
- Python 3.10 + PyTorch 2.8.0+cu129（RTX 5090 sm_120）
- conda环境名：musetalk，模型约8.6GB

## 启动
cd MuseTalk && python musetalk_api_server.py --host 0.0.0.0 --port 7861

## 常见问题
- PyTorch 2.8 weights_only=True不兼容旧模型 -> 添加weights_only=False
- /release_gpu后推理失败 -> musetalk_infer开始时自动reload到GPU
- mmcv版本检查 -> patch mmcv_maximum_version到2.3.0, setuptools<81

## 远程推理文件中转
MuseTalk API只接受本地路径。跨机器需file_server.py（端口7862）：
- POST /upload 上传文件返回远程路径
- POST /download 下载远程文件

## 远程调用流程
1. 上传图片音频到远程共享目录
2. 调用MuseTalk API传入远程路径
3. 下载生成的视频到本地

## 健康检查
curl http://localhost:7861/health
models_loaded=false时调用/reload_gpu
'''

skills['gpt-sovits-tts'] = r'''---
name: gpt-sovits-tts
description: GPT-SoVITS音色克隆TTS服务部署与GPU协调。Use when 部署GPT-SoVITS、音色克隆、TTS生成、解决GPU争抢/CPU-CUDA设备不匹配、参考音频裁剪、g2p_en依赖缺失。
---

# GPT-SoVITS TTS 服务

## 部署
- Python 3.10 + torch 2.3.0+cu121
- conda环境名：gpt-sovits
- API端口：9880

## 启动
cd GPT-SoVITS && python api_server.py

## 音色克隆要求
- 参考音频3~10秒，需_trim_ref_audio()自动裁剪
- g2p_en依赖必须安装否则TTS报错

## GPU协调
GPT-SoVITS和MuseTalk共享GPU时会CUDA OOM：
1. 不要同时运行两个模型推理
2. MuseTalk请求加120秒超时防止卡死
3. CUDA OOM时自动降级到Edge-TTS
4. 切换时先释放对方GPU：POST http://localhost:7861/release_gpu

## CPU-CUDA设备不匹配
MuseTalk释放GPU后模型在CPU，GPT-SoVITS输入在GPU。
修复：确保输入tensor和模型在同一设备。
'''

skills['ppt-digital-human'] = r'''---
name: ppt-digital-human
description: PPT数字人讲解视频生成，分段管理+选择性合成。Use when 生成PPT讲解视频、逐页生成、分段预览、选择性合成、讲稿编辑、画中画合成、翻页过渡。
---

# PPT数字人讲解视频

## 核心流程
上传PPT -> 提取页面(图片+文字) -> 编辑讲稿 -> 选择形象+音色 -> 逐页生成(TTS+MuseTalk) -> 合成画中画 -> 翻页过渡 -> 输出视频

## 分段管理模式
- 每页独立生成TTS音频+MuseTalk口型视频+画中画合成
- 支持单页生成、重新生成、选择性合成
- 已生成页面不重复生成（断点续传）

## 两阶段策略
Phase 1: 批量TTS（释放MuseTalk GPU -> 逐页生成音频 -> 释放GPT-SoVITS GPU）
Phase 2: 批量MuseTalk（重新加载到GPU -> 逐页生成口型视频 -> 合成）

## API
- POST /ppt/upload 上传PPT
- POST /ppt/projects/{id}/slides/{slide_id}/generate 生成单页
- POST /ppt/projects/{id}/merge 合成选中页
- POST /ppt/projects/{id}/generate 全量生成（支持start_slide/end_slide）

## 可配参数（前台设置）
- segment_duration: 分段时长（秒），默认30，范围10-120
- bbox_shift: 面部偏移，默认0
- musetalk_timeout_per_second: 每秒音频超时倍数，默认30

## PPT解析
- python-pptx提取文字
- comtypes(PowerPoint COM)导出高清图片
- COM失败时降级到python-pptx
'''

skills['avatar-bg-removal'] = r'''---
name: avatar-bg-removal
description: 数字人形象去背景，生成透明PNG。Use when 去除人物背景、生成透明数字人、rembg部署、u2net模型下载、背景替换、绿幕处理。
---

# 数字人形象去背景

## 方案
用户上传照片时自动调用rembg去背景，生成透明PNG。MuseTalk用透明图片做参考帧，输出视频自然无背景。

## rembg部署
pip install rembg
模型u2net.onnx（176MB）放在 ~/.u2net/u2net.onnx

## u2net.onnx下载
GitHub: https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2net.onnx
国内网络不稳定时用断点续传：curl -L -C - -o u2net.onnx <url>

## 去背景API
POST /avatars/{id}/remove-bg
- 读取原始图片
- rembg.remove()生成透明PNG
- 保存transparent_image_path到DB

## 数据模型
Avatar新增字段：transparent_image_path（透明PNG路径）

## MuseTalk使用透明图片
image_path = avatar.transparent_image_path or avatar.styled_image_path or avatar.original_image_path

## 默认背景图
uploads/backgrounds/目录下提供：white、light_gray、dark_blue、green_screen、warm
GET /avatars/backgrounds/list 获取背景列表

## 降级方案
rembg不可用时用OpenCV GrabCut替代（效果较差）
'''

skills['dual-machine-gpu'] = r'''---
name: dual-machine-gpu
description: 双机GPU协作部署，局域网文件传输+远程推理。Use when 配置双机器GPU分工、网线直连静态IP、HTTP文件中转、远程MuseTalk调用、GPU争抢解决。
---

# 双机GPU协作

## 架构
机器A（前端+后端+GPT-SoVITS） <-> 网线直连 <-> 机器B（MuseTalk）

## 网络配置
网线直连两台PC，手动设置静态IP：
- 机器A: 192.168.100.1/24
- 机器B: 192.168.100.3/24

netsh interface ip set address name="以太网" static 192.168.100.1 255.255.255.0

## 防火墙
放行MuseTalk端口7861和文件中转端口7862

## 文件中转服务
机器B运行file_server.py（端口7862），接收机器A上传的图片/音频，返回远程路径。

## 配置
机器A的backend/.env:
MUSETALK_API_URL=http://192.168.100.3:7861

## 优势
- 彻底解决GPU争抢
- 不再OOM，不再降级为静态图片
- 24GB显存充裕
'''

skills['voice-blending'] = r'''---
name: voice-blending
description: 音色混合功能，支持多音色加权混合并保存复用。Use when 混合音色、音色权重调节、保存混合音色、预置音色+自定义音色混合、Edge-TTS音频混合。
---

# 音色混合

## 混合方式
- audio方法：Edge-TTS分别生成各音色音频，按权重加权混合
- embedding方法：GPT-SoVITS spk_emb向量插值（高级）

## API
- POST /voice-lib/blend 生成混合音频预览
- POST /voice-lib/blend/save 保存混合音色到我的音色库
- POST /voice-lib/blend/preview 预览混合效果

## 保存混合音色
保存后可在PPT讲解、演讲视频、对话等模块使用。

## 前端交互（参考豆包）
- 可视化滑块调节权重
- 每个音色可独立试听
- 内嵌音频播放器
- 输入名称+描述后生成并保存
- 生成后停留在当前页可重新调试

## 预置音色库
14个预置音色分类：温柔知性、活泼开朗、沉稳大气、专业理性、亲切自然
'''

skills['lip-sync-service'] = r'''---
name: lip-sync-service
description: 口型同步服务封装，支持分段推理+超时重试+远程调用。Use when 调用MuseTalk生成口型视频、音频分段、超时处理、重试机制、远程推理文件传输。
---

# 口型同步服务

## 核心类 LipSyncService
- generate_lip_sync_video(): 主入口
- _generate_with_musetalk(): MuseTalk调用
- 支持本地和远程模式

## 分段推理
长音频按segment_duration切分，每段单独推理后拼接。
默认30秒/段（可配），用ffmpeg拼接。

## 超时计算
timeout = max(300, audio_duration * musetalk_timeout_per_second)

## 重试机制
- 最多3次重试
- 超时后检查MuseTalk健康状态
- models_loaded=false时调用/reload_gpu

## 远程模式
- 自动检测MUSETALK_API_URL是否为远程
- 远程时先上传文件到file_server（端口7862）
- 下载结果到本地

## GPU协调
- asyncio.Lock延迟初始化（Python 3.14兼容）
- 远程MuseTalk时跳过GPU协调
'''

skills['fastapi-async-task'] = r'''---
name: fastapi-async-task
description: FastAPI后台异步任务管理，线程池+进度追踪。Use when 实现长时间运行的后台任务、进度查询、任务取消、Python 3.14 asyncio兼容、BackgroundTasks不执行问题。
---

# FastAPI后台异步任务

## 问题
FastAPI的BackgroundTasks对async函数支持有问题（Python 3.14），任务不执行。

## 解决方案：线程池
用threading.Thread替代BackgroundTasks：
- 线程内创建新事件循环
- 线程内重新创建DB Session
- SQLAlchemy对象需在线程内重新查询

## 注意事项
- asyncio.Lock()在Python 3.14中不能在模块级创建，需延迟初始化
- 用简单标志位替代Lock避免事件循环问题

## 任务状态管理
_tasks字典存储：task_id -> {status, progress, message}
- GET /tasks/{id} 查询状态
- POST /tasks/{id}/cancel 取消任务
'''

skills['video-composer'] = r'''---
name: video-composer
description: 视频合成服务，moviepy画中画+过渡+拼接。Use when 合成画中画视频、PPT+数字人叠加、翻页过渡效果、视频拼接、rembg逐帧去背景。
---

# 视频合成服务

## 画中画合成
PPT全屏背景 + 数字人半身像叠加

## 翻页过渡
- fade: CrossFadeIn + CrossFadeOut
- moviepy 2.x用with_effects
- 降级为直接concatenate

## 透明背景叠加
数字人形象已去背景，MuseTalk输出无背景视频，直接叠加无需逐帧rembg。

## 注意事项
- moviepy 2.x API变化：with_position替代set_position
- 长视频内存占用大，需分段处理
- ffmpeg路径：imageio_ffmpeg.get_ffmpeg_exe()
'''

skills['digital-human-platform'] = r'''---
name: digital-human-platform
description: AI数字人分身平台整体架构，前后端+多模型协调。Use when 搭建数字人平台、配置技术栈、协调多个AI模型、磁盘空间管理、路径解析、服务启动顺序。
---

# AI数字人分身平台

## 技术栈
- 后端：FastAPI + SQLite + Python 3.14
- 前端：React + Vite + Ant Design + Three.js
- TTS：Edge-TTS + GPT-SoVITS
- 口型同步：MuseTalk
- GPU：RTX 4090（机器A）+ RTX 5090（机器B）

## 服务端口
- 前端：localhost:5173
- 后端API：localhost:8000
- GPT-SoVITS：localhost:9880
- MuseTalk：192.168.100.3:7861（机器B）
- 文件中转：192.168.100.3:7862（机器B）

## 启动顺序
1. 启动机器B的MuseTalk + file_server
2. 启动机器A的GPT-SoVITS
3. 启动机器A的后端API
4. 启动机器A的前端

## 磁盘空间管理
- 大文件存D盘（D:\AI_Avatar_Data\）
- 大模型文件用junction链接（mklink /J）
- pip cache purge释放缓存

## 路径解析
- uploads目录用项目根绝对路径
- D盘文件通过/data/静态路由访问
- 前端axios baseURL设为/api/v1

## 功能模块
1. 形象管理：上传+去背景+3D查看
2. 音色管理：自定义+预置+混合
3. PPT讲解：分段生成+选择性合成
4. 演讲视频：文字->TTS->口型视频
5. 智能对话：WebSocket+LLM
6. 3D展示：Three.js（待接入真实模型）

## 后期规划
- 实时语音：WebRTC + 流式ASR
- 机器人实体对接
- 3D真实模型替换
'''

for skill_name, content in skills.items():
    skill_path = os.path.join(skills_dir, skill_name, 'SKILL.md')
    with open(skill_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Written: {skill_name}')

print(f'\nTotal: {len(skills)} skills written')
