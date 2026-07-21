"""PPT数字人讲解视频合成服务

支持两种布局模式：
1. pip（画中画）：数字人在PPT右下角，传统叠加
2. bottom_bar（底部横条）：数字人站在PPT下方1/6讲台区域，更自然

底部横条模式参考2025行业最佳实践：
- 数字人占画面1/6高度，像站在PPT前面
- 半透明渐变背景，模拟讲台效果
- 支持左/中/右位置，翻页时可平滑切换
"""

import os
import logging
import numpy as np
from typing import List, Optional, Tuple
from PIL import Image, ImageDraw, ImageFilter

logger = logging.getLogger(__name__)

# ============ 背景去除 ============

def remove_background(image_path: str, output_path: str) -> str:
    """使用rembg去除图片背景，生成透明PNG"""
    try:
        from rembg import remove
        input_img = Image.open(image_path)
        output_img = remove(input_img)
        output_img.save(output_path, "PNG")
        return output_path
    except ImportError:
        logger.warning("[PPTComposer] rembg not installed, using circle mask fallback")
        return _circle_mask_fallback(image_path, output_path)
    except Exception as e:
        logger.warning(f"[PPTComposer] rembg failed: {e}, using circle mask fallback")
        return _circle_mask_fallback(image_path, output_path)


def _circle_mask_fallback(image_path: str, output_path: str) -> str:
    """降级方案：用椭圆遮罩模拟去背景（半身像更自然）"""
    img = Image.open(image_path).convert("RGBA")
    w, h = img.size
    mask = Image.new("L", (w, h), 0)
    
    draw = ImageDraw.Draw(mask)
    # 椭圆遮罩，适合半身像（宽:高 = 3:4）
    cx, cy = w // 2, int(h * 0.45)
    rx, ry = int(w * 0.48), int(h * 0.45)
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
    
    # 羽化边缘
    mask = mask.filter(ImageFilter.GaussianBlur(radius=8))
    
    img.putalpha(mask)
    img.save(output_path, "PNG")
    return output_path


# ============ 渐变遮罩生成 ============

def create_gradient_bar(width: int, bar_height: int, 
                        color: Tuple[int, int, int] = (30, 30, 50),
                        opacity_start: float = 0.0, opacity_end: float = 0.85) -> Image.Image:
    """创建底部横条的渐变遮罩
    
    从上到下：透明 → 半透明深色
    模拟讲台效果，数字人像站在PPT前面
    
    Args:
        width: 视频宽度
        bar_height: 横条高度
        color: 横条颜色 (R, G, B)
        opacity_start: 顶部透明度（0=完全透明）
        opacity_end: 底部透明度（1=完全不透明）
    """
    img = Image.new("RGBA", (width, bar_height), (0, 0, 0, 0))
    
    for y in range(bar_height):
        ratio = y / max(bar_height - 1, 1)
        # 使用 ease-in 曲线让渐变更自然
        ratio = ratio * ratio
        alpha = int(255 * (opacity_start + (opacity_end - opacity_start) * ratio))
        for x in range(width):
            img.putpixel((x, y), (color[0], color[1], color[2], alpha))
    
    return img


def create_gradient_bar_fast(width: int, bar_height: int,
                              color: Tuple[int, int, int] = (30, 30, 50),
                              opacity_start: float = 0.0, opacity_end: float = 0.85) -> np.ndarray:
    """快速版渐变遮罩生成（numpy向量化）"""
    y_coords = np.arange(bar_height)
    ratio = y_coords / max(bar_height - 1, 1)
    ratio = ratio * ratio  # ease-in
    alpha = (255 * (opacity_start + (opacity_end - opacity_start) * ratio)).astype(np.uint8)
    
    # (bar_height, width, 4) RGBA
    bar = np.zeros((bar_height, width, 4), dtype=np.uint8)
    bar[:, :, 0] = color[0]
    bar[:, :, 1] = color[1]
    bar[:, :, 2] = color[2]
    bar[:, :, 3] = alpha[:, np.newaxis]
    
    return bar


# ============ 画中画模式（原版） ============

def compose_pip_video(
    slide_image_path: str,
    human_video_path: str,
    output_path: str,
    position: str = "bottom-right",
    size_ratio: float = 0.25,
    fps: int = 25,
) -> str:
    """画中画模式：数字人叠加在PPT上方"""
    from moviepy import VideoFileClip, ImageClip, CompositeVideoClip
    
    human_clip = VideoFileClip(human_video_path)
    duration = human_clip.duration
    
    slide_clip = ImageClip(slide_image_path, duration=duration)
    
    slide_w, slide_h = slide_clip.size
    human_w = int(slide_w * size_ratio)
    human_h = int(human_w * human_clip.h / human_clip.w)
    human_resized = human_clip.resized((human_h, human_w))
    
    margin = int(slide_w * 0.02)
    if position == "bottom-right":
        pos = (slide_w - human_w - margin, slide_h - human_h - margin)
    elif position == "bottom-left":
        pos = (margin, slide_h - human_h - margin)
    elif position == "bottom-center":
        pos = ((slide_w - human_w) // 2, slide_h - human_h - margin)
    elif position == "top-right":
        pos = (slide_w - human_w - margin, margin)
    elif position == "top-left":
        pos = (margin, margin)
    else:
        pos = (slide_w - human_w - margin, slide_h - human_h - margin)
    
    human_with_pos = human_resized.with_position(pos)
    
    final = CompositeVideoClip([slide_clip, human_with_pos])
    final = final.with_audio(human_clip.audio)
    
    final.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )
    
    human_clip.close()
    slide_clip.close()
    final.close()
    
    return output_path


# ============ 底部横条模式（推荐） ============

def compose_bottom_bar_video(
    slide_image_path: str,
    human_video_path: str,
    output_path: str,
    position: str = "bottom-center",
    bar_ratio: float = 1/6,
    bar_color: Tuple[int, int, int] = (30, 30, 50),
    bar_opacity: float = 0.85,
    fps: int = 25,
) -> str:
    """底部横条模式：数字人站在PPT下方讲台区域
    
    布局：
    +------------------------------------------+
    |  ┌────────────────────────────────────┐  |
    |  │                                    │  |
    |  │         PPT 页面内容区              │  |
    |  │         （上方 5/6 高度）            │  |
    |  │                                    │  |
    |  ├────────────────────────────────────┤  |
    |  │  🧑‍💼 数字人半身像  ←── 底部横条 ──→  │  |
    |  │     （下方 1/6 高度，渐变背景）       │  |
    |  └────────────────────────────────────┘  |
    +------------------------------------------+
    
    Args:
        slide_image_path: PPT页面图片路径
        human_video_path: 数字人口型视频路径（MuseTalk输出）
        output_path: 输出视频路径
        position: 数字人位置 (bottom-left, bottom-center, bottom-right)
        bar_ratio: 底部横条占画面高度比例（默认1/6）
        bar_color: 横条颜色
        bar_opacity: 横条不透明度
        fps: 帧率
    """
    from moviepy import (VideoFileClip, ImageClip, CompositeVideoClip, 
                          ColorClip, VideoClip)
    
    human_clip = VideoFileClip(human_video_path)
    audio = human_clip.audio
    duration = human_clip.duration
    
    # 目标视频尺寸（16:9）
    video_w, video_h = 1920, 1080
    
    # PPT内容区高度
    ppt_h = int(video_h * (1 - bar_ratio))
    bar_h = video_h - ppt_h
    
    # 1. PPT图片缩放到上方区域
    slide_img = Image.open(slide_image_path)
    slide_img = slide_img.resize((video_w, ppt_h), Image.LANCZOS)
    slide_clip = ImageClip(np.array(slide_img), duration=duration)
    slide_clip = slide_clip.with_position((0, 0))
    
    # 2. 底部渐变横条
    gradient_bar = create_gradient_bar_fast(video_w, bar_h, bar_color, 0.0, bar_opacity)
    gradient_clip = ImageClip(gradient_bar, duration=duration)
    gradient_clip = gradient_clip.with_position((0, ppt_h))
    
    # 3. 数字人视频 - 去背景后放在底部横条
    # 数字人高度 = 横条高度 * 1.6（头部超出横条，更自然）
    avatar_h = int(bar_h * 1.6)
    avatar_w = int(avatar_h * human_clip.w / human_clip.h)
    human_resized = human_clip.resized((avatar_h, avatar_w))
    
    # 数字人位置（水平方向）
    margin = int(video_w * 0.03)
    if position == "bottom-left":
        avatar_x = margin
    elif position == "bottom-center":
        avatar_x = (video_w - avatar_w) // 2
    elif position == "bottom-right":
        avatar_x = video_w - avatar_w - margin
    else:
        avatar_x = (video_w - avatar_w) // 2
    
    # 数字人垂直位置：底部对齐视频底边，头部超出横条
    avatar_y = video_h - avatar_h
    
    human_with_pos = human_resized.with_position((avatar_x, avatar_y))
    
    # 4. 合成所有层
    final = CompositeVideoClip([slide_clip, gradient_clip, human_with_pos])
    if audio is not None:
        final = final.with_audio(audio)
    
    final.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )
    
    human_clip.close()
    slide_clip.close()
    final.close()
    
    return output_path


# ============ 带位置过渡的底部横条模式 ============

def compose_bottom_bar_with_transition(
    slide_image_path: str,
    human_video_path: str,
    output_path: str,
    position: str = "bottom-center",
    next_position: Optional[str] = None,
    transition_duration: float = 0.5,
    bar_ratio: float = 1/6,
    bar_color: Tuple[int, int, int] = (30, 30, 50),
    bar_opacity: float = 0.85,
    fps: int = 25,
) -> str:
    """带位置过渡的底部横条模式
    
    当下一页PPT数字人位置不同时，在视频末尾添加平滑滑动过渡
    
    Args:
        position: 当前页数字人位置
        next_position: 下一页数字人位置（None则不添加过渡）
        transition_duration: 过渡时长（秒）
    """
    from moviepy import (VideoFileClip, ImageClip, CompositeVideoClip, 
                          ColorClip, VideoClip)
    
    if next_position is None or next_position == position:
        # 无过渡，直接合成
        return compose_bottom_bar_video(
            slide_image_path, human_video_path, output_path,
            position, bar_ratio, bar_color, bar_opacity, fps
        )
    
    human_clip = VideoFileClip(human_video_path)
    audio = human_clip.audio
    duration = human_clip.duration
    
    video_w, video_h = 1920, 1080
    ppt_h = int(video_h * (1 - bar_ratio))
    bar_h = video_h - ppt_h
    
    # 数字人尺寸
    avatar_h = int(bar_h * 1.6)
    avatar_w = int(avatar_h * human_clip.w / human_clip.h)
    
    margin = int(video_w * 0.03)
    
    def get_x(pos):
        if pos == "bottom-left":
            return margin
        elif pos == "bottom-right":
            return video_w - avatar_w - margin
        else:
            return (video_w - avatar_w) // 2
    
    start_x = get_x(position)
    end_x = get_x(next_position)
    avatar_y = video_h - avatar_h
    
    # 1. PPT图片
    slide_img = Image.open(slide_image_path).resize((video_w, ppt_h), Image.LANCZOS)
    slide_clip = ImageClip(np.array(slide_img), duration=duration)
    slide_clip = slide_clip.with_position((0, 0))
    
    # 2. 渐变横条
    gradient_bar = create_gradient_bar_fast(video_w, bar_h, bar_color, 0.0, bar_opacity)
    gradient_clip = ImageClip(gradient_bar, duration=duration)
    gradient_clip = gradient_clip.with_position((0, ppt_h))
    
    # 3. 数字人 - 位置动画
    human_resized = human_clip.resized((avatar_h, avatar_w))
    
    def avatar_position(t):
        """数字人位置随时间变化"""
        if t < duration - transition_duration:
            # 主体阶段：固定位置
            return (start_x, avatar_y)
        else:
            # 过渡阶段：平滑滑动到下一页位置
            progress = (t - (duration - transition_duration)) / transition_duration
            # ease-in-out 缓动
            progress = progress * progress * (3 - 2 * progress)
            current_x = int(start_x + (end_x - start_x) * progress)
            return (current_x, avatar_y)
    
    human_with_pos = human_resized.with_position(avatar_position)
    
    # 4. 合成
    final = CompositeVideoClip([slide_clip, gradient_clip, human_with_pos])
    if audio is not None:
        final = final.with_audio(audio)
    
    final = final.resized((video_h, video_w))
    
    final.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )
    
    human_clip.close()
    slide_clip.close()
    final.close()
    
    return output_path


# ============ 完整PPT视频拼接 ============

def compose_full_ppt_video(
    slide_composed_videos: List[str],
    output_path: str,
    transition: str = "fade",
    fps: int = 25,
    transition_duration: float = 0.5,
) -> str:
    """将所有页面的画中画视频拼接为完整PPT讲解视频
    
    Args:
        slide_composed_videos: 每页PPT的合成视频路径列表
        output_path: 最终输出路径
        transition: 翻页过渡效果 ("fade" | "slide" | "none")
        fps: 帧率
        transition_duration: 过渡时长（秒）
    """
    from moviepy import VideoFileClip, concatenate_videoclips
    
    clips = []
    for vp in slide_composed_videos:
        clip = VideoFileClip(vp)
        clips.append(clip)
    
    if transition == "fade" and len(clips) > 1:
        # 简单拼接，后续可加过渡效果
        try:
            from moviepy.video.fx import CrossFadeIn, CrossFadeOut
            faded_clips = []
            for i, clip in enumerate(clips):
                if i > 0:
                    clip = clip.with_effects([CrossFadeIn(transition_duration)])
                if i < len(clips) - 1:
                    clip = clip.with_effects([CrossFadeOut(transition_duration)])
                faded_clips.append(clip)
            final_clip = concatenate_videoclips(faded_clips, method="compose")
        except ImportError:
            # moviepy 2.x 没有 CrossFadeIn/CrossFadeOut，直接拼接
            final_clip = concatenate_videoclips(clips, method="compose")
    else:
        final_clip = concatenate_videoclips(clips, method="compose")
    
    final_clip.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )
    
    for clip in clips:
        clip.close()
    final_clip.close()
    
    return output_path


# ============ 统一入口 ============

def compose_slide_video(
    slide_image_path: str,
    human_video_path: str,
    output_path: str,
    layout_mode: str = "bottom_bar",
    position: str = "bottom-center",
    next_position: Optional[str] = None,
    size_ratio: float = 0.25,
    bar_ratio: float = 1/6,
    bar_color: Tuple[int, int, int] = (30, 30, 50),
    bar_opacity: float = 0.85,
    transition_duration: float = 0.5,
    fps: int = 25,
) -> str:
    """统一入口：根据layout_mode选择合成方式
    
    Args:
        layout_mode: "pip"（画中画）或 "bottom_bar"（底部横条，推荐）
        position: 数字人位置
        next_position: 下一页数字人位置（仅bottom_bar模式支持过渡）
        size_ratio: 数字人占比（pip模式）
        bar_ratio: 底部横条占比（bottom_bar模式）
        bar_color: 横条颜色
        bar_opacity: 横条不透明度
    """
    if layout_mode == "bottom_bar":
        return compose_bottom_bar_with_transition(
            slide_image_path, human_video_path, output_path,
            position=position,
            next_position=next_position,
            transition_duration=transition_duration,
            bar_ratio=bar_ratio,
            bar_color=bar_color,
            bar_opacity=bar_opacity,
            fps=fps,
        )
    else:
        return compose_pip_video(
            slide_image_path, human_video_path, output_path,
            position=position,
            size_ratio=size_ratio,
            fps=fps,
        )
