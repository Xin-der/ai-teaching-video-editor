"""MoviePy 渲染引擎 — edit_ops.json → mp4"""
import json, os, sys, math
import numpy as np
from dotenv import load_dotenv
load_dotenv()

try:
    from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, TextClip
    from moviepy import concatenate_videoclips
except ImportError:
    print("MoviePy 未安装或版本不对，请运行: pip install moviepy")
    sys.exit(1)

import cv2

EDIT_OPS = "work/edit_ops.json"
FFMPEG = r"D:\tools\ffmpeg\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"

os.environ["IMAGEIO_FFMPEG_EXE"] = FFMPEG


def blue_chroma_key(frame, lower_blue=(100, 60, 60), upper_blue=(135, 255, 255)):
    """蓝色色度抠图 → 透明背景"""
    hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    mask_inv = cv2.bitwise_not(mask)

    # 创建 RGBA 帧
    rgba = cv2.cvtColor(frame, cv2.COLOR_RGB2RGBA)
    rgba[:, :, 3] = mask_inv  # 蓝色区域 alpha=0（透明）
    return rgba


def create_red_dot(size=12):
    """创建一个红色圆点 ImageClip（带透明背景的RGBA numpy数组）"""
    img = np.zeros((size, size, 4), dtype=np.uint8)
    center = size // 2
    radius = size // 2 - 1
    for y in range(size):
        for x in range(size):
            if (x - center) ** 2 + (y - center) ** 2 <= radius ** 2:
                img[y, x] = [255, 30, 30, 255]  # 红色, 不透明
    return img


def load_route_map(path, max_width=400):
    """加载路线图，做蓝色色度抠图，返回 RGBA ImageClip"""
    img = cv2.imread(path)
    if img is None:
        print(f"  ⚠ 无法加载路线图: {path}")
        return None
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    # 蓝色色度抠图
    img_rgba = blue_chroma_key(img_rgb)

    clip = ImageClip(img_rgba, duration=None)  # duration 后续设置
    # 缩放到指定宽度
    h, w = img_rgba.shape[:2]
    if w > max_width:
        scale = max_width / w
        clip = clip.resized(scale)
    return clip


def render_segment(video_clip, seg, route_map_clip, red_dot_img):
    """渲染单个分段"""
    t_start = seg["t_start"]
    t_end = seg["t_end"]
    duration = t_end - t_start
    if duration <= 0:
        return None

    # 提取子片段
    try:
        clip = video_clip.subclipped(t_start, t_end)
    except Exception as e:
        print(f"  ⚠ seg{seg['segment_id']:03d}: subclip 失败 ({e})")
        return None

    overlays = [clip]
    has_text = seg.get("has_text_overlay", False)
    has_speech = seg.get("has_speech", False)

    for op in seg.get("operations", []):
        op_name = op["op"]
        params = op.get("params", {})

        if op_name == "overlay_route_map" and route_map_clip is not None:
            rm = route_map_clip.with_duration(duration)
            pos = params.get("position", "右上角")
            # 计算位置
            if pos == "右上角":
                rm = rm.with_position(("right", "top"))
            elif pos == "左上角":
                rm = rm.with_position(("left", "top"))
            else:
                rm = rm.with_position(("right", "top"))
            # 透明度
            opacity = params.get("opacity", 0.9)
            rm = rm.with_opacity(opacity)
            overlays.append(rm)

        elif op_name == "animate_red_dot" and route_map_clip is not None:
            # 红点动画：如果没有坐标数据，默认从路线图顶部匀速移动到底部
            path_data = params.get("path", "linear_top_to_bottom")
            rm_h = route_map_clip.h if route_map_clip else 200

            dot = ImageClip(red_dot_img, duration=duration)
            dot = dot.with_opacity(0.95)

            # 默认：从路线图顶部匀速移动到底部
            def make_pos_func(rm_height):
                def pos_func(t):
                    progress = t / duration if duration > 0 else 0
                    y = int(rm_height * 0.05 + progress * rm_height * 0.85)  # 5%→90%
                    return (360, y)  # 路线图区域x≈360
                return pos_func

            dot = dot.with_position(make_pos_func(rm_h))
            overlays.append(dot)

        elif op_name == "zoom_keyframe":
            scale_start = params.get("scale_start", 1.0)
            scale_end = params.get("scale_end", 1.12)

            def make_zoom(orig_w, orig_h, start_s, end_s, dur):
                def zoom_effect(get_frame, t):
                    progress = t / dur if dur > 0 else 0
                    # ease_out: 1 - (1-t)^2
                    eased = 1 - (1 - progress) ** 2
                    scale = start_s + (end_s - start_s) * eased
                    frame = get_frame(t)
                    h, w = frame.shape[:2]
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    resized = cv2.resize(frame, (new_w, new_h))
                    # 中心裁剪
                    x1 = (new_w - w) // 2
                    y1 = (new_h - h) // 2
                    return resized[y1:y1+h, x1:x1+w]
                return zoom_effect

            clip = clip.transform(make_zoom(clip.w, clip.h, scale_start, scale_end, duration))

        elif op_name == "add_pip_if_available":
            pip_pos = params.get("foot_closeup", {}).get("position", "左下角")
            pip_scale = params.get("foot_closeup", {}).get("scale", 0.25)

            # 检查是否有脚部特写素材
            for src_key in ["foot_closeup", "dashboard_closeup"]:
                src_info = params.get(src_key, {})
                src_path = src_info.get("source", "")
                if os.path.exists(src_path):
                    pip_clip = None
                    if src_path.endswith(".mp4"):
                        pip_clip = VideoFileClip(src_path).subclipped(0, min(duration, 10))
                    elif src_path.endswith((".jpg", ".png")):
                        pip_clip = ImageClip(src_path, duration=duration)

                    if pip_clip is not None:
                        pip_pos_name = src_info.get("position", "左上角")
                        pip_w = int(clip.w * pip_scale)
                        pip_clip = pip_clip.resized(width=pip_w)
                        pip_clip = pip_clip.with_duration(duration)

                        if pip_pos_name == "左上角":
                            pip_clip = pip_clip.with_position((10, 10))
                        elif pip_pos_name == "左下角":
                            pip_clip = pip_clip.with_position((10, clip.h - pip_clip.h - 10))
                        elif pip_pos_name == "右上角":
                            pip_clip = pip_clip.with_position((clip.w - pip_clip.w - 10, 10))

                        pip_clip = pip_clip.with_opacity(0.9)
                        overlays.append(pip_clip)

        elif op_name == "burn_subtitles":
            if has_speech:
                # 从 ASR 数据获取字幕文本
                transcript = seg.get("transcript", "")
                if transcript:
                    # 限制字幕长度
                    if len(transcript) > 60:
                        # 分行显示
                        mid = len(transcript) // 2
                        # 尝试在空格处断开
                        space_idx = transcript.rfind(" ", 0, mid + 20)
                        if space_idx < 0:
                            space_idx = mid
                        line1 = transcript[:space_idx].strip()
                        line2 = transcript[space_idx:].strip()
                        subtitle_text = line1 + "\n" + line2
                    else:
                        subtitle_text = transcript

                    # 使用 TextClip（需要系统有中文字体）
                    try:
                        txt = TextClip(
                            text=subtitle_text,
                            font_size=32,
                            color="white",
                            stroke_color="black",
                            stroke_width=6,
                            font="Arial",
                            duration=duration
                        )
                        txt = txt.with_position(("center", clip.h - txt.h - 40))
                        overlays.append(txt)
                    except Exception as e:
                        # TextClip 渲染可能因为字体问题失败，跳过字幕
                        pass

        elif op_name == "skip_route_overlay":
            # 分支D：不叠加路线图
            pass

    # 合成
    if len(overlays) > 1:
        result = CompositeVideoClip(overlays, size=(clip.w, clip.h))
    else:
        result = clip

    return result


def main():
    if not os.path.exists(EDIT_OPS):
        print(f"❌ 未找到 {EDIT_OPS}")
        print("   请先运行: python scripts/match_style.py")
        sys.exit(1)

    with open(EDIT_OPS, encoding="utf-8") as f:
        edit_data = json.load(f)

    video_source = edit_data.get("video_source", "input/video.mp4")
    route_map_source = edit_data.get("route_map")
    has_foot = edit_data.get("has_foot_closeup", False)
    has_dash = edit_data.get("has_dash_closeup", False)

    # 检查输入视频
    if not os.path.exists(video_source):
        # 尝试使用参考视频
        alt_video = "ref/SGOI6715.MOV"
        if os.path.exists(alt_video):
            video_source = alt_video
            print(f"📹 使用参考视频: {video_source}")
        else:
            print(f"❌ 未找到输入视频: {video_source}")
            print("   请将视频放到 input/video.mp4 或 ref/ 目录")
            sys.exit(1)
    else:
        print(f"📹 输入视频: {video_source}")

    # 加载路线图
    route_map_clip = None
    red_dot_img = create_red_dot()
    if route_map_source and os.path.exists(route_map_source):
        print(f"🗺 路线图: {route_map_source}")
        route_map_clip = load_route_map(route_map_source)
    elif os.path.exists("ref/materials/f6100a8c536c5084cd3add7c4858e7d.jpg"):
        route_map_source = "ref/materials/f6100a8c536c5084cd3add7c4858e7d.jpg"
        print(f"🗺 路线图(默认): {route_map_source}")
        route_map_clip = load_route_map(route_map_source)

    print(f"🎬 分段数: {edit_data['total_segments']}")
    if has_foot:
        print(f"🦶 脚部特写: 有")
    if has_dash:
        print(f"📊 仪表盘特写: 有")
    print()

    # 加载视频
    print("加载视频...")
    video = VideoFileClip(video_source)
    print(f"  分辨率: {video.w}x{video.h}, 时长: {video.duration:.0f}s, fps: {video.fps}\n")

    # 逐段渲染
    rendered_segments = []
    total_segs = edit_data["total_segments"]

    for i, seg in enumerate(edit_data["segments"]):
        seg_id = seg["segment_id"]
        # 只渲染主轨（track 0）的分段，叠加轨道的内容已经体现在主轨上
        if seg.get("track", 0) != 0:
            continue

        print(f"  渲染 seg{seg_id:03d} [{seg['t_start']:.0f}s-{seg['t_end']:.0f}s] "
              f"activity={seg.get('activity','?')} "
              f"ops={len(seg.get('operations',[]))}", end=" ", flush=True)

        try:
            result = render_segment(video, seg, route_map_clip, red_dot_img)
            if result is not None:
                rendered_segments.append(result)
                print("✓")
            else:
                print("✗ 跳过")
        except Exception as e:
            print(f"✗ {type(e).__name__}: {e}")

    if not rendered_segments:
        print("\n❌ 没有成功渲染的分段")
        video.close()
        sys.exit(1)

    # 拼接所有分段
    print(f"\n拼接 {len(rendered_segments)} 段...")
    final = concatenate_videoclips(rendered_segments)

    # 输出
    output_path = "output/成片.mp4"
    os.makedirs("output", exist_ok=True)

    print(f"输出到 {output_path} ...")
    final.write_videofile(
        output_path,
        codec="libx264",
        audio_codec="aac",
        fps=video.fps,
        preset="medium",
        threads=4
    )

    # 清理
    final.close()
    video.close()
    if route_map_clip:
        route_map_clip.close()
    for seg in rendered_segments:
        seg.close()

    output_size = os.path.getsize(output_path) / (1024 * 1024)
    print(f"\n✅ 渲染完成! {output_path} ({output_size:.1f}MB)")


if __name__ == "__main__":
    main()
