# 机器B MuseTalk 部署指南

## 目标
在第二台机器（RTX 4090）上部署MuseTalk，作为口型同步推理服务器，与机器A局域网通信。

## 架构
```
机器A（当前机器）                    机器B（新机器）
├── 前端 :5173                       └── MuseTalk :7861
├── 后端API :8000                        ↑
├── GPT-SoVITS :9880                     │
└── ──────── 局域网/WiFi ────────────────┘
     backend/.env: MUSETALK_API_URL=http://机器B_IP:7861
```

## 步骤

### 1. 机器B基础环境

```powershell
# 安装Miniconda（如果没有）
# 下载: https://docs.conda.io/en/latest/miniconda.html
# 安装到 C:\Users\用户名\miniconda3

# 创建conda环境
conda create -n musetalk python=3.10 -y
conda activate musetalk
```

### 2. 安装PyTorch（CUDA 12.4）

```powershell
conda activate musetalk
pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu121
```

### 3. 复制MuseTalk代码

从机器A复制整个MuseTalk目录到机器B：
```powershell
# 方法1：用U盘/移动硬盘复制
# 复制 C:\Users\yj821\.psacowork\workspace\20260630120021\MuseTalk\ 到机器B

# 方法2：局域网共享文件夹
# 机器A上右键MuseTalk目录 → 共享 → 高级共享
# 机器B上 \\机器A的IP\MuseTalk 复制过来
```

### 4. 安装依赖

```powershell
cd MuseTalk
conda activate musetalk
pip install -r requirements.txt
```

### 5. 下载模型权重

MuseTalk需要以下模型文件（从机器A复制即可）：
```
MuseTalk\models/
├── dwpose/
│   └── dw-ll_ucoco_389.pth.tar
├── mask/
│   └── parsing_atr.onnx
├── resnet50/
│   └── resnet50-0676ba61.pth
├── sd-vae-ft-ema/
│   └── (多个文件)
├── sd/
│   └── v1-5-pruned-emaonly.safetensors
└── muse/
    └── musev_t2v.json
```

从机器A复制 `MuseTalk\models\` 目录到机器B相同位置。

### 6. 启动MuseTalk（绑定0.0.0.0）

```powershell
cd MuseTalk
conda activate musetalk
python musetalk_api_server.py --host 0.0.0.0 --port 7861
```

### 7. 机器B防火墙放行

```powershell
# 管理员权限运行
netsh advfirewall firewall add rule name="MuseTalk" dir=in action=allow protocol=TCP localport=7861
```

### 8. 获取机器B的IP

```powershell
ipconfig
# 找到 "无线局域网适配器 WLAN" 下的 IPv4 地址
# 例如: 192.168.1.100
```

### 9. 机器A配置修改

修改机器A的 `backend/.env`：
```
MUSETALK_API_URL=http://192.168.1.100:7861
```

然后重启机器A的后端。

### 10. 验证连通性

在机器A上：
```powershell
curl http://192.168.1.100:7861/health
# 应返回 {"status":"ok",...}
```

## 注意事项

1. **两台机器必须在同一网段**（如都是192.168.1.x）
2. **机器B不需要安装GPT-SoVITS**，只跑MuseTalk
3. **机器B不需要前端/后端**，纯推理服务器
4. **首次推理会慢**（模型加载到GPU需要2-3分钟）
5. **如果WiFi不稳定**，建议用网线直连两台机器（设置静态IP）
6. **模型文件约15GB**，复制需要时间

## 故障排查

| 问题 | 解决方案 |
|---|---|
| 机器A无法访问机器B:7861 | 检查防火墙、IP地址、MuseTalk是否绑定0.0.0.0 |
| CUDA out of memory | 机器B上不要运行其他GPU程序 |
| 推理超时 | 首次推理需要预热，发一次小请求让模型加载 |
| 模型文件缺失 | 从机器A完整复制models/目录 |
