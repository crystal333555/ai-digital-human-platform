# AI数字人平台 - Skill技能清单

> 本文档记录了从AI数字人分身平台项目中提炼的10个可复用Skill。
> 这些Skill可在后续优化和研究AI数字人时直接调用，避免重复踩坑。

## Skill总览

| # | Skill名称 | 触发场景 | 文件位置 |
|---|---|---|---|
| 1 | `musetalk-deploy` | 部署MuseTalk、远程推理、超时/卡死修复 | `~/.psacowork/skills/musetalk-deploy/SKILL.md` |
| 2 | `gpt-sovits-tts` | GPT-SoVITS音色克隆、GPU协调 | `~/.psacowork/skills/gpt-sovits-tts/SKILL.md` |
| 3 | `ppt-digital-human` | PPT数字人讲解视频生成 | `~/.psacowork/skills/ppt-digital-human/SKILL.md` |
| 4 | `avatar-bg-removal` | 数字人去背景、透明PNG生成 | `~/.psacowork/skills/avatar-bg-removal/SKILL.md` |
| 5 | `dual-machine-gpu` | 双机GPU协作、网线直连、文件中转 | `~/.psacowork/skills/dual-machine-gpu/SKILL.md` |
| 6 | `voice-blending` | 音色混合、权重调节、保存复用 | `~/.psacowork/skills/voice-blending/SKILL.md` |
| 7 | `lip-sync-service` | 口型同步服务、分段推理、超时重试 | `~/.psacowork/skills/lip-sync-service/SKILL.md` |
| 8 | `fastapi-async-task` | FastAPI后台任务、Python 3.14兼容 | `~/.psacowork/skills/fastapi-async-task/SKILL.md` |
| 9 | `video-composer` | 视频合成、画中画、翻页过渡 | `~/.psacowork/skills/video-composer/SKILL.md` |
| 10 | `digital-human-platform` | 平台整体架构、技术栈、启动顺序 | `~/.psacowork/skills/digital-human-platform/SKILL.md` |

---

## 各Skill详细说明

### 1. musetalk-deploy（MuseTalk部署与远程推理）

**解决的问题**：
- MuseTalk在Windows上部署的各种坑（mmcv版本、setuptools、PyTorch兼容性）
- PyTorch 2.8的weights_only=True不兼容旧模型格式
- /release_gpu后推理失败（CPU/CUDA设备不匹配）
- 跨机器调用MuseTalk时文件路径不共享

**核心知识点**：
- PyTorch 2.8需要添加weights_only=False
- 远程推理需要file_server.py文件中转服务
- 健康检查API：`/health`返回models_loaded状态

**调用方式**：当用户提到MuseTalk部署、远程推理、口型同步服务问题时自动触发

---

### 2. gpt-sovits-tts（GPT-SoVITS音色克隆）

**解决的问题**：
- GPT-SoVITS和MuseTalk共享GPU导致CUDA OOM
- 参考音频格式不对（需要3~10秒WAV）
- g2p_en依赖缺失导致TTS报错
- CPU/CUDA设备不匹配

**核心知识点**：
- 参考音频需要_trim_ref_audio()自动裁剪到3~10秒
- GPU切换时先释放对方GPU
- Edge-TTS作为降级方案

---

### 3. ppt-digital-human（PPT数字人讲解）

**解决的问题**：
- PPT讲解视频一次性生成太慢
- 无法逐页预览和修改
- 生成失败后需要全部重来

**核心知识点**：
- 分段管理模式：每页独立生成
- 两阶段策略：先批量TTS再批量MuseTalk
- 选择性合成：勾选页面合成最终视频
- 可配参数：segment_duration、bbox_shift、timeout

---

### 4. avatar-bg-removal（数字人去背景）

**解决的问题**：
- MuseTalk输出带原始照片背景
- 逐帧rembg去背景太慢
- PPT合成时数字人背景遮挡内容

**核心知识点**：
- 上传时自动去背景，生成transparent_image_path
- u2net.onnx模型（176MB）下载和部署
- MuseTalk用透明图片做参考帧
- 默认背景图：white、light_gray、dark_blue、green_screen、warm

---

### 5. dual-machine-gpu（双机GPU协作）

**解决的问题**：
- 单机器GPU显存不够，两个模型争抢
- 公司网络封了RDP端口
- 跨机器文件传输

**核心知识点**：
- 网线直连+静态IP配置
- file_server.py文件中转服务
- 远程MuseTalk调用流程
- 防火墙端口放行

---

### 6. voice-blending（音色混合）

**解决的问题**：
- 单一音色不够丰富
- 混合音色无法保存复用
- 混合结果播放不了

**核心知识点**：
- audio方法：Edge-TTS音频加权混合
- 保存混合配置到voices表
- 前端交互参考豆包：滑块调节+内嵌播放器

---

### 7. lip-sync-service（口型同步服务）

**解决的问题**：
- 长音频推理超时
- MuseTalk卡死后无法自动恢复
- 远程推理文件传输

**核心知识点**：
- 分段推理：按segment_duration切分
- 超时计算：max(300, audio_dur * timeout_per_second)
- 重试机制：3次重试+健康检查
- 远程模式自动检测和文件上传/下载

---

### 8. fastapi-async-task（FastAPI后台任务）

**解决的问题**：
- BackgroundTasks在Python 3.14中不执行async函数
- asyncio.Lock()在模块级创建会卡住
- 线程中SQLAlchemy Session已关闭

**核心知识点**：
- 用threading.Thread替代BackgroundTasks
- 线程内创建新事件循环和DB Session
- asyncio.Lock延迟初始化
- 简单标志位替代Lock

---

### 9. video-composer（视频合成）

**解决的问题**：
- moviepy 2.x API变化
- CrossFadeIn/CrossFadeOut导入失败
- 画中画合成内存占用大

**核心知识点**：
- moviepy 2.x用with_position替代set_position
- 透明背景直接叠加（无需逐帧rembg）
- 分段合成避免内存溢出

---

### 10. digital-human-platform（平台整体架构）

**解决的问题**：
- 多个AI模型协调
- 磁盘空间不足
- 路径解析错误
- 服务启动顺序

**核心知识点**：
- 技术栈：FastAPI + React + MuseTalk + GPT-SoVITS
- 大文件存D盘，junction链接
- 服务端口和启动顺序
- 前端axios配置

---

## 使用方式

### 自动触发
当用户提到相关关键词时，天璇CoWork会自动加载对应Skill：
- "MuseTalk超时" → 加载 `musetalk-deploy`
- "音色克隆失败" → 加载 `gpt-sovits-tts`
- "PPT讲解视频" → 加载 `ppt-digital-human`
- "去背景" → 加载 `avatar-bg-removal`
- 等等

### 手动调用
在对话中指定Skill：
```
[Skill: musetalk-deploy] 帮我检查MuseTalk服务状态
```

### SkillSearch搜索
```
搜索：数字人去背景
搜索：PPT视频生成
搜索：双机GPU协作
```

---

## 维护说明

- Skill文件位置：`C:\Users\yj821\.psacowork\skills\<skill-name>\SKILL.md`
- 修改Skill后无需重启，下次调用自动加载最新版本
- 新增Skill用 `skill-creator` 的 `init_skill.py` 初始化
- 打包分发用 `package_skill.py`

---

*最后更新：2026-07-16*
*项目：AI数字人分身平台*
*GitHub：https://github.com/crystal333555/ai-digital-human-platform*
