"""
数字人微表情增强器 v4
基于大卫视频真实参数：
- 头部水平移动69px，垂直移动50px
- 眨眼频率1.1次/秒
- 眼睛/嘴巴/下巴运动量均衡（0.8-0.9）
修复：中间一条线问题（用边缘融合替代硬裁剪）
"""
import os
import cv2
import numpy as np
import logging
import random

logger = logging.getLogger(__name__)


def enhance_video(
    video_path: str,
    output_path: str,
    blink_interval: float = 1.0,  # 大卫视频1.1次/秒
    head_sway_amplitude: float = 30.0,  # 大卫视频69px范围，用30px幅度
    head_sway_frequency: float = 0.15,
    breathing_rate: float = 0.2,
    target_resolution: tuple = None,
    avatar_scale: float = 1.0,
) -> str:
    """增强视频微表情，保留音频"""
    try:
        import tempfile, shutil, subprocess
        import imageio_ffmpeg

        # 用OpenCV读取视频
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            temp_input = os.path.join(tempfile.gettempdir(), 'enhance_input.mp4')
            shutil.copy2(video_path, temp_input)
            cap = cv2.VideoCapture(temp_input)
            video_path = temp_input

        fps = int(cap.get(cv2.CAP_PROP_FPS) or 24)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0

        if target_resolution:
            w, h = int(target_resolution[0]), int(target_resolution[1])
        else:
            w, h = orig_w, orig_h

        logger.info(f"Enhancing {total_frames} frames, {w}x{h}, {fps}fps, duration={duration:.1f}s")

        # 临时视频文件（无音频）
        temp_video = output_path.replace('.mp4', '_temp.mp4')
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_video, fourcc, fps, (w, h))

        # 面部检测器
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

        # 预生成随机眨眼时间点（1.1次/秒）
        blink_times = []
        t = random.uniform(0.5, 1.5)
        while t < duration:
            blink_times.append(t)
            t += random.uniform(0.7, 1.5)  # 大卫视频1.1次/秒

        # 预生成随机头部运动轨迹（平滑随机游走）
        head_x_offsets = np.zeros(total_frames)
        head_y_offsets = np.zeros(total_frames)
        for i in range(1, total_frames):
            # 平滑随机游走 + 正弦波
            head_x_offsets[i] = head_x_offsets[i-1] * 0.95 + random.gauss(0, 2) + 15 * np.sin(2 * np.pi * 0.15 * i / fps)
            head_y_offsets[i] = head_y_offsets[i-1] * 0.95 + random.gauss(0, 1.5) + 10 * np.sin(2 * np.pi * 0.1 * i / fps + 1.5)
            # 限制范围
            head_x_offsets[i] = np.clip(head_x_offsets[i], -head_sway_amplitude, head_sway_amplitude)
            head_y_offsets[i] = np.clip(head_y_offsets[i], -head_sway_amplitude * 0.6, head_sway_amplitude * 0.6)

        # 预生成眼神移动
        gaze_offsets = np.zeros(total_frames)
        gaze_change_time = 0
        gaze_target = 0
        for i in range(total_frames):
            if i / fps >= gaze_change_time:
                gaze_change_time = i / fps + random.uniform(1.0, 3.0)
                gaze_target = random.randint(-5, 5)
            gaze_offsets[i] = gaze_offsets[i-1] * 0.9 + gaze_target * 0.1 if i > 0 else 0

        frame_idx = 0
        last_face = None

        while True:
            ret, frame = cap.read()
            if not ret or frame is None:
                break

            t = frame_idx / fps

            # 调整分辨率
            if (orig_w, orig_h) != (w, h):
                frame = cv2.resize(frame, (w, h))

            # 每3帧检测一次面部（性能优化）
            if frame_idx % 3 == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                if len(faces) > 0:
                    last_face = max(faces, key=lambda f: f[2] * f[3])

            # 1. 头部运动（用warpAffine + 边缘融合，避免中间一条线）
            dx = head_x_offsets[frame_idx] if frame_idx < len(head_x_offsets) else 0
            dy = head_y_offsets[frame_idx] if frame_idx < len(head_y_offsets) else 0
            if abs(dx) > 0.5 or abs(dy) > 0.5:
                frame = _apply_head_motion_smooth(frame, dx, dy)

            # 2. 眨眼
            for blink_t in blink_times:
                blink_phase = t - blink_t
                if 0 <= blink_phase <= 0.25:  # 眨眼持续0.25秒
                    # 快速闭眼（0-0.1s）+ 慢速睁开（0.1-0.25s）
                    if blink_phase < 0.1:
                        intensity = blink_phase / 0.1  # 0->1
                    else:
                        intensity = 1.0 - (blink_phase - 0.1) / 0.15  # 1->0
                    if last_face is not None:
                        frame = _apply_blink(frame, last_face, intensity)
                    break

            # 3. 眼神移动
            gaze_x = gaze_offsets[frame_idx] if frame_idx < len(gaze_offsets) else 0
            if abs(gaze_x) > 0.5 and last_face is not None:
                frame = _apply_gaze_shift(frame, last_face, gaze_x)

            # 4. 呼吸感
            breath_scale = 1.0 + 0.008 * np.sin(2 * np.pi * breathing_rate * t)
            if abs(breath_scale - 1.0) > 0.001:
                frame = _apply_breathing(frame, last_face, breath_scale)

            out.write(frame)
            frame_idx += 1

        cap.release()
        out.release()

        # 用ffmpeg合并音频
        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        temp_audio = output_path.replace('.mp4', '_audio.aac')

        # 提取原始音频
        subprocess.run([
            ffmpeg_exe, '-y', '-i', video_path,
            '-vn', '-acodec', 'copy', temp_audio
        ], capture_output=True, timeout=60)

        if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 0:
            # 合并视频和音频
            subprocess.run([
                ffmpeg_exe, '-y',
                '-i', temp_video,
                '-i', temp_audio,
                '-c:v', 'libx264', '-c:a', 'aac',
                '-shortest', output_path
            ], capture_output=True, timeout=120)
            os.remove(temp_audio)
        else:
            # 没有音频，直接复制视频
            subprocess.run([
                ffmpeg_exe, '-y', '-i', temp_video,
                '-c:v', 'libx264', output_path
            ], capture_output=True, timeout=120)

        # 清理临时文件
        if os.path.exists(temp_video):
            os.remove(temp_video)

        logger.info(f"Enhanced video: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Enhance failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def _apply_head_motion_smooth(frame, dx, dy):
    """头部运动 - 用边缘镜像填充避免中间一条线"""
    h, w = frame.shape[:2]
    dx_int = int(dx)
    dy_int = int(dy)

    if abs(dx_int) < 1 and abs(dy_int) < 1:
        return frame

    # 创建边缘镜像填充的画布
    pad = max(abs(dx_int), abs(dy_int)) + 2
    padded = cv2.copyMakeBorder(frame, pad, pad, pad, pad, cv2.BORDER_REFLECT_101)

    # 计算偏移后的区域
    x1 = pad + dx_int
    y1 = pad + dy_int
    x2 = x1 + w
    y2 = y1 + h

    return padded[y1:y2, x1:x2].copy()


def _apply_blink(frame, face, intensity):
    """眨眼 - 对眼睛区域做纵向压缩"""
    fx, fy, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])

    # 眼睛区域：面部上1/3
    eye_y1 = fy + int(fh * 0.15)
    eye_y2 = fy + int(fh * 0.40)
    eye_x1 = fx + int(fw * 0.1)
    eye_x2 = fx + int(fw * 0.9)

    # 确保在画面内
    eye_y1 = max(0, eye_y1)
    eye_y2 = min(frame.shape[0], eye_y2)
    eye_x1 = max(0, eye_x1)
    eye_x2 = min(frame.shape[1], eye_x2)

    region = frame[eye_y1:eye_y2, eye_x1:eye_x2]
    if region.size == 0:
        return frame

    new_h = max(1, int(region.shape[0] * (1 - intensity * 0.85)))
    compressed = cv2.resize(region, (region.shape[1], new_h))

    # 用边缘颜色填充剩余空间（避免黑色线）
    if new_h < region.shape[0]:
        # 上下用边缘行填充
        gap = region.shape[0] - new_h
        top_gap = gap // 2
        bottom_gap = gap - top_gap
        frame[eye_y1:eye_y1+top_gap, eye_x1:eye_x2] = region[0:1, :, :].repeat(top_gap, axis=0)
        frame[eye_y1+top_gap:eye_y1+top_gap+new_h, eye_x1:eye_x2] = compressed
        frame[eye_y1+top_gap+new_h:eye_y2, eye_x1:eye_x2] = region[-1:, :, :].repeat(bottom_gap, axis=0)
    else:
        frame[eye_y1:eye_y2, eye_x1:eye_x2] = compressed

    return frame


def _apply_gaze_shift(frame, face, gaze_x):
    """眼神移动 - 对瞳孔区域做水平偏移"""
    fx, fy, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])

    # 眼睛区域
    eye_y1 = fy + int(fh * 0.20)
    eye_y2 = fy + int(fh * 0.35)
    eye_x1 = fx + int(fw * 0.15)
    eye_x2 = fx + int(fw * 0.85)

    eye_y1 = max(0, eye_y1)
    eye_y2 = min(frame.shape[0], eye_y2)
    eye_x1 = max(0, eye_x1)
    eye_x2 = min(frame.shape[1], eye_x2)

    region = frame[eye_y1:eye_y2, eye_x1:eye_x2]
    if region.size == 0:
        return frame

    # 水平平移
    shift = int(gaze_x)
    if abs(shift) < 1:
        return frame

    M = np.float32([[1, 0, shift], [0, 1, 0]])
    shifted = cv2.warpAffine(region, M, (region.shape[1], region.shape[0]),
                             borderMode=cv2.BORDER_REFLECT_101)
    frame[eye_y1:eye_y2, eye_x1:eye_x2] = shifted

    return frame


def _apply_breathing(frame, face, scale):
    """呼吸感 - 肩膀区域轻微缩放"""
    h, w = frame.shape[:2]

    if face is not None:
        fx, fy, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
        nose_y = fy + fh // 2
    else:
        nose_y = h // 3

    shoulder = frame[nose_y:, :]
    if shoulder.size == 0:
        return frame

    new_h = int(shoulder.shape[0] * scale)
    if new_h <= 0 or abs(new_h - shoulder.shape[0]) < 1:
        return frame

    resized = cv2.resize(shoulder, (w, new_h))

    if new_h > shoulder.shape[0]:
        frame[nose_y:, :] = resized[:shoulder.shape[0], :]
    else:
        frame[nose_y:nose_y + new_h, :] = resized
        # 用最后一行填充剩余
        if new_h < shoulder.shape[0]:
            frame[nose_y + new_h:, :] = resized[-1:, :, :].repeat(shoulder.shape[0] - new_h, axis=0)

    return frame
