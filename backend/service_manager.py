"""
AI数字人平台 - 服务管理器
一键启动/停止/重启/查看所有服务状态
"""
import os
import sys
import time
import json
import subprocess
import threading
import socket
import requests
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
MUSETALK_DIR = PROJECT_ROOT / "MuseTalk"
GPT_SOVITS_DIR = PROJECT_ROOT / "GPT-SoVITS"

# 服务配置
SERVICES = {
    "backend": {
        "name": "后端API",
        "port": 8000,
        "health_url": "http://localhost:8000/",
        "start_cmd": ["backend\\venv\\Scripts\\uvicorn.exe", "app.main:app", "--host", "0.0.0.0", "--port", "8000"],
        "cwd": str(BACKEND_DIR),
        "process": None,
    },
    "frontend": {
        "name": "前端",
        "port": 5173,
        "health_url": "http://localhost:5173/",
        "start_cmd": ["npx", "vite", "--host", "0.0.0.0", "--port", "5173"],
        "cwd": str(FRONTEND_DIR),
        "process": None,
    },
    "musetalk": {
        "name": "MuseTalk",
        "port": 7861,
        "health_url": "http://localhost:7861/health",
        "start_cmd": ["C:\\Users\\yj821\\miniconda3\\envs\\musetalk\\python.exe", "musetalk_api_server.py", "--host", "0.0.0.0", "--port", "7861"],
        "cwd": str(MUSETALK_DIR),
        "process": None,
    },
    "gpt_sovits": {
        "name": "GPT-SoVITS",
        "port": 9880,
        "health_url": "http://localhost:9880/",
        "start_cmd": ["C:\\Users\\yj821\\miniconda3\\Scripts\\conda.exe", "run", "-n", "gpt-sovits", "python", "api_server.py"],
        "cwd": str(GPT_SOVITS_DIR),
        "process": None,
    },
}

STATUS_FILE = Path(__file__).parent / "service_status.json"


def is_port_listening(port):
    """检查端口是否在监听"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except:
        return False


def check_health(url):
    """检查HTTP健康状态"""
    try:
        r = requests.get(url, timeout=5)
        return r.status_code == 200
    except:
        return False


def get_service_status(svc_key):
    """获取单个服务状态"""
    svc = SERVICES[svc_key]
    port_ok = is_port_listening(svc["port"])
    health_ok = check_health(svc["health_url"]) if port_ok else False
    
    status = "online" if health_ok else ("degraded" if port_ok else "offline")
    return {
        "key": svc_key,
        "name": svc["name"],
        "port": svc["port"],
        "status": status,
        "port_listening": port_ok,
        "health_ok": health_ok,
        "url": svc["health_url"],
    }


def get_all_status():
    """获取所有服务状态"""
    return {key: get_service_status(key) for key in SERVICES}


def start_service(svc_key):
    """启动单个服务"""
    svc = SERVICES[svc_key]
    if is_port_listening(svc["port"]):
        return {"success": False, "message": f"{svc['name']}已在运行（端口{svc['port']}）"}
    
    try:
        # 使用CREATE_NEW_CONSOLE让服务在独立窗口运行
        proc = subprocess.Popen(
            svc["start_cmd"],
            cwd=svc["cwd"],
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        svc["process"] = proc
        time.sleep(3)
        
        if is_port_listening(svc["port"]):
            return {"success": True, "message": f"{svc['name']}启动成功（端口{svc['port']}）"}
        else:
            return {"success": False, "message": f"{svc['name']}启动中，等待端口就绪..."}
    except Exception as e:
        return {"success": False, "message": f"{svc['name']}启动失败: {str(e)}"}


def stop_service(svc_key):
    """停止单个服务"""
    svc = SERVICES[svc_key]
    if not is_port_listening(svc["port"]):
        return {"success": False, "message": f"{svc['name']}未在运行"}
    
    try:
        # 通过端口找进程并杀掉
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.split("\n"):
            if f":{svc['port']}" in line and "LISTENING" in line:
                parts = line.strip().split()
                if len(parts) >= 5:
                    pid = int(parts[-1])
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True, timeout=5)
        
        time.sleep(2)
        if not is_port_listening(svc["port"]):
            return {"success": True, "message": f"{svc['name']}已停止"}
        else:
            return {"success": False, "message": f"{svc['name']}停止失败"}
    except Exception as e:
        return {"success": False, "message": f"停止失败: {str(e)}"}


def restart_service(svc_key):
    """重启单个服务"""
    stop_service(svc_key)
    time.sleep(2)
    return start_service(svc_key)


def start_all():
    """启动所有服务"""
    results = {}
    for key in ["musetalk", "gpt_sovits", "backend", "frontend"]:
        results[key] = start_service(key)
        time.sleep(2)
    return results


def stop_all():
    """停止所有服务"""
    results = {}
    for key in ["frontend", "backend", "gpt_sovits", "musetalk"]:
        results[key] = stop_service(key)
    return results


def save_status():
    """保存状态到文件"""
    status = get_all_status()
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    return status


def print_status():
    """打印状态表"""
    status = get_all_status()
    print("\n" + "=" * 60)
    print("  AI数字人平台 - 服务状态")
    print("=" * 60)
    for key, s in status.items():
        icon = "✅" if s["status"] == "online" else ("⚠️" if s["status"] == "degraded" else "❌")
        print(f"  {icon} {s['name']:12s} 端口:{s['port']:5d}  状态:{s['status']}")
    print("=" * 60 + "\n")
    return status


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python service_manager.py [status|start|stop|restart|start-all|stop-all]")
        print("  status     - 查看所有服务状态")
        print("  start <名> - 启动指定服务 (backend/frontend/musetalk/gpt_sovits)")
        print("  stop <名>  - 停止指定服务")
        print("  restart <名> - 重启指定服务")
        print("  start-all  - 启动所有服务")
        print("  stop-all   - 停止所有服务")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        print_status()
    elif cmd == "start" and len(sys.argv) > 2:
        result = start_service(sys.argv[2])
        print(result["message"])
    elif cmd == "stop" and len(sys.argv) > 2:
        result = stop_service(sys.argv[2])
        print(result["message"])
    elif cmd == "restart" and len(sys.argv) > 2:
        result = restart_service(sys.argv[2])
        print(result["message"])
    elif cmd == "start-all":
        results = start_all()
        for key, r in results.items():
            print(f"  {SERVICES[key]['name']}: {r['message']}")
    elif cmd == "stop-all":
        results = stop_all()
        for key, r in results.items():
            print(f"  {SERVICES[key]['name']}: {r['message']}")
    else:
        print(f"未知命令: {cmd}")
