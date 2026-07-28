"""
多平台视频导出器 — MoviePy 模板渲染

支持的平台:
  - douyin:      9:16 竖屏 + 大字幕 + 关键词弹窗 + 进度条
  - bilibili:    16:9 横屏 + 标准字幕 + 知识卡片 + 章节标记
  - xiaohongshu: 1:1 方形 + 要点列表 + 封面图

渲染管线:
  源视频片段 → 裁切适配比例 → 叠加标题卡 → 叠加字幕轨道 → 叠加进度条 → 叠加卡片/弹窗 → 导出
"""

import json
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

# MoviePy 2.x
from moviepy import VideoFileClip, TextClip, CompositeVideoClip, ColorClip
from moviepy.video.fx import FadeIn, FadeOut
import moviepy.config as mpconfig

from .scorer import SegmentScorer


# ------------------------------------------------------------------
# 字体检测
# ------------------------------------------------------------------
def _detect_chinese_font() -> str:
    """检测系统中可用的中文字体，返回完整路径"""
    if os.name == "nt":
        # Windows 字体目录
        font_dir = os.environ.get("WINDIR", r"C:\Windows") + r"\Fonts"
        candidates = [
            os.path.join(font_dir, "simhei.ttf"),
            os.path.join(font_dir, "msyh.ttf"),
            os.path.join(font_dir, "simsun.ttf"),
            os.path.join(font_dir, "SIMHEI.TTF"),
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        ]

    for path in candidates:
        if os.path.exists(path):
            try:
                from PIL import ImageFont
                ImageFont.truetype(path, 20)
                return path
            except Exception:
                continue

    # 最后尝试按名称加载
    for name in ["SimHei", "Arial"]:
        try:
            from PIL import ImageFont
            ImageFont.truetype(name, 20)
            return name
        except Exception:
            continue

    return "Arial"


# ------------------------------------------------------------------
# 配置加载
# ------------------------------------------------------------------
def _load_template(platform: str) -> dict:
    """加载平台模板"""
    template_dir = Path(__file__).parent.parent / "templates"
    path = template_dir / f"{platform}.json"
    if not path.exists():
        raise FileNotFoundError(f"模板不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------
# 导出器主类
# ------------------------------------------------------------------
class VideoExporter:
    """多平台视频导出器"""

    def __init__(self, output_dir: str = "output", font: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.font = font or _detect_chinese_font()
        # 用于文案生成的 scorer（复用其知识库）
        self._scorer: Optional[SegmentScorer] = None

    # ------------------------------------------------------------------
    # 公开入口
    # ------------------------------------------------------------------

    def export(self, segment: dict, source_video: str,
               platform: str, asr_segments: Optional[list] = None) -> dict:
        """导出一个片段到指定平台

        Args:
            segment:   片段数据 {id, topic, start, end, duration, transcript, ...}
            source_video: 源视频路径
            platform:  平台名 douyin | bilibili | xiaohongshu
            asr_segments: ASR 字幕段列表（可选，用于精确字幕时间轴）

        Returns:
            {output_path, platform, segment_id, duration, ...}
        """
        template = _load_template(platform)

        # 创建片段输出目录
        seg_name = self._safe_filename(segment.get("topic", f"segment_{segment['id']}"))
        seg_dir = self.output_dir / seg_name
        seg_dir.mkdir(parents=True, exist_ok=True)

        output_path = str(seg_dir / f"{platform}.mp4")

        print(f"\n{'='*60}")
        print(f"  导出: [{platform}] {segment.get('topic', '无主题')}")
        print(f"  片段: {segment['start']:.1f}s - {segment['end']:.1f}s ({segment['duration']:.1f}s)")
        print(f"  输出: {output_path}")
        print(f"{'='*60}")

        # 渲染
        self._render(segment, source_video, template, output_path, asr_segments or [])

        # 生成封面（小红书需要）
        cover_path = None
        if platform == "xiaohongshu" and template["layout"]["cover_image"]["enabled"]:
            cover_path = self._generate_cover(segment, source_video, template, seg_dir)

        # 生成文案
        copy_path = self._generate_copy(segment, platform, template, seg_dir)

        return {
            "output_path": output_path,
            "cover_path": cover_path,
            "copy_path": copy_path,
            "platform": platform,
            "segment_id": segment["id"],
            "duration": segment["duration"],
        }

    def export_all(self, segments: list, source_video: str,
                   platforms: Optional[list] = None,
                   asr_segments: Optional[list] = None) -> list:
        """批量导出所有片段到所有平台"""
        if platforms is None:
            platforms = ["douyin", "bilibili", "xiaohongshu"]

        results = []
        for seg in segments:
            for plat in platforms:
                # 检查该平台是否适合
                suit = seg.get("score_result", {}).get("platform_suitability", {}).get(plat, "中")
                if suit == "低":
                    print(f"  ⏭ 跳过 [{plat}] {seg.get('topic')} — 不适合该平台")
                    continue
                try:
                    res = self.export(seg, source_video, plat, asr_segments)
                    results.append(res)
                except Exception as e:
                    print(f"  ✗ [{plat}] {seg.get('topic')} 导出失败: {e}")
                    import traceback
                    traceback.print_exc()

        return results

    # ------------------------------------------------------------------
    # 渲染核心
    # ------------------------------------------------------------------

    def _render(self, segment: dict, source_video: str,
                template: dict, output_path: str, asr_segments: list):
        """渲染单个片段为视频文件"""
        layout = template["layout"]
        video_cfg = template["video"]
        out_w, out_h = video_cfg["output_resolution"]
        fps = video_cfg["fps"]
        seg_start = segment["start"]
        seg_end = segment["end"]
        seg_duration = seg_end - seg_start

        # ---------- 1. 加载并裁切源视频 ----------
        clip = VideoFileClip(source_video).subclipped(seg_start, seg_end)

        # 计算裁切参数（中心裁切到目标比例）
        src_w, src_h = clip.size
        target_ratio = out_w / out_h
        src_ratio = src_w / src_h

        if target_ratio > src_ratio:
            # 目标更宽 → 裁切上下
            new_h = int(src_w / target_ratio)
            crop_y = (src_h - new_h) // 2
            clip = clip.cropped(y1=crop_y, y2=crop_y + new_h)
        elif target_ratio < src_ratio:
            # 目标更高 → 裁切左右
            new_w = int(src_h * target_ratio)
            crop_x = (src_w - new_w) // 2
            clip = clip.cropped(x1=crop_x, x2=crop_x + new_w)

        # 缩放到输出分辨率
        clip = clip.resized((out_w, out_h))

        # ---------- 2. 构建叠加层 ----------
        overlays = [clip]
        current_time = 0.0

        # --- 标题卡 ---
        if layout.get("title_card", {}).get("enabled"):
            title_dur = layout["title_card"]["duration_seconds"]
            title_clip = self._make_title_card(
                segment.get("topic", ""),
                template, out_w, out_h, title_dur
            )
            if title_clip is not None:
                overlays.append(title_clip.with_start(0))
                current_time += title_dur

        # --- 结尾卡 ---
        end_dur = 0
        if layout.get("ending_card", {}).get("enabled"):
            end_dur = layout["ending_card"]["duration_seconds"]
            end_clip = self._make_ending_card(template, out_w, out_h, end_dur)
            if end_clip is not None:
                end_start = max(seg_duration - end_dur, 0)
                overlays.append(end_clip.with_start(end_start))

        # --- 字幕轨道 ---
        if layout.get("subtitle", {}).get("enabled"):
            sub_clips = self._make_subtitle_clips(
                segment, asr_segments, template, out_w, out_h, seg_start, seg_end
            )
            overlays.extend(sub_clips)

        # --- 关键词弹窗（抖音） ---
        if layout.get("keyword_popup", {}).get("enabled"):
            popup_clips = self._make_keyword_popups(
                segment, asr_segments, template, out_w, out_h
            )
            overlays.extend(popup_clips)

        # --- 知识卡片（B站） ---
        if layout.get("knowledge_card", {}).get("enabled"):
            kc = self._make_knowledge_card(
                segment, template, out_w, out_h, seg_duration
            )
            if kc is not None:
                overlays.append(kc)

        # --- 要点覆盖（小红书） ---
        if layout.get("key_points_overlay", {}).get("enabled"):
            kp = self._make_key_points_overlay(
                segment, template, out_w, out_h, seg_duration
            )
            if kp is not None:
                overlays.append(kp)

        # --- 进度条 ---
        if layout.get("progress_bar", {}).get("enabled"):
            pb = self._make_progress_bar(template, out_w, out_h, seg_duration)
            if pb is not None:
                overlays.append(pb.with_start(0))

        # ---------- 3. 合成并导出 ----------
        final = CompositeVideoClip(overlays, size=(out_w, out_h))

        # 限制总时长
        final = final.subclipped(0, seg_duration)

        # 导出
        final.write_videofile(
            output_path,
            fps=fps,
            codec=video_cfg.get("codec", "libx264"),
            bitrate=video_cfg.get("bitrate", "8M"),
            audio_codec=video_cfg.get("audio_codec", "aac"),
            audio_bitrate=video_cfg.get("audio_bitrate", "256k"),
            logger=None,
        )

        # 清理
        clip.close()
        final.close()
        for ov in overlays:
            try:
                ov.close()
            except Exception:
                pass

        print(f"  ✓ 导出完成: {output_path}")

    # ------------------------------------------------------------------
    # UI 组件构建
    # ------------------------------------------------------------------

    def _make_title_card(self, topic: str, template: dict,
                         out_w: int, out_h: int, duration: float) -> Optional[VideoFileClip]:
        """标题卡：顶部或全屏文字"""
        cfg = template["layout"]["title_card"]
        if not topic:
            return None

        font_size = int(out_h * cfg.get("font_size_ratio", 0.06))
        color = cfg.get("color", "#FFFFFF")
        stroke_color = cfg.get("stroke_color", "#000000")
        stroke_w = cfg.get("stroke_width", 3)
        bg = cfg.get("bg_color", "rgba(0,0,0,0.5)")

        try:
            # 背景层
            bg_clip = ColorClip(size=(out_w, int(out_h * cfg.get("bg_height_ratio", 0.12))),
                                color=self._parse_rgba(bg))

            # 文字层
            txt_clip = TextClip(
                text=topic,
                font=self.font,
                font_size=font_size,
                color=color,
                stroke_color=stroke_color,
                stroke_width=stroke_w,
            ).with_duration(duration)

            # 组合：背景 + 居中文字
            combined = CompositeVideoClip([
                bg_clip.with_position(("center", 0)),
                txt_clip.with_position(("center", "center")),
            ], size=(out_w, out_h)).with_duration(duration)

            return combined.with_effects([FadeIn(0.3)])
        except Exception as e:
            print(f"  ⚠ 标题卡渲染失败: {e}")
            return None

    def _make_ending_card(self, template: dict, out_w: int, out_h: int,
                          duration: float) -> Optional[VideoFileClip]:
        """结尾互动卡片"""
        cfg = template["layout"]["ending_card"]
        text = cfg.get("text", "")
        if not text:
            return None

        font_size = int(out_h * cfg.get("font_size_ratio", 0.04))
        color = cfg.get("color", "#FFFFFF")
        bg = cfg.get("bg_color", "rgba(0,0,0,0.7)")

        try:
            bg_clip = ColorClip(size=(out_w, out_h), color=self._parse_rgba(bg))
            txt_clip = TextClip(
                text=text,
                font=self.font,
                font_size=font_size,
                color=color,
            ).with_duration(duration).with_position(("center", "center"))

            return CompositeVideoClip([bg_clip, txt_clip]).with_duration(duration)
        except Exception as e:
            print(f"  ⚠ 结尾卡渲染失败: {e}")
            return None

    def _make_subtitle_clips(self, segment: dict, asr_segments: list,
                             template: dict, out_w: int, out_h: int,
                             seg_start: float, seg_end: float) -> list:
        """生成字幕片段列表"""
        cfg = template["layout"]["subtitle"]
        font_size = int(out_h * cfg.get("font_size_ratio", 0.045))
        color = cfg.get("color", "#FFFFFF")
        stroke_color = cfg.get("stroke_color", "#000000")
        stroke_w = cfg.get("stroke_width", 4)
        pos_y_ratio = cfg.get("position_y_ratio", 0.80)
        max_chars = cfg.get("max_chars_per_line", 18)

        clips = []

        # 筛选片段时间范围内的 ASR 段
        seg_asr = [
            s for s in asr_segments
            if s.get("start", 0) >= seg_start and s.get("end", 0) <= seg_end
        ]

        # 如果没有 ASR，用 transcript 做一个静态字幕
        if not seg_asr:
            transcript = segment.get("transcript", "")
            if transcript:
                try:
                    txt = TextClip(
                        text=self._wrap_text(transcript, max_chars),
                        font=self.font,
                        font_size=font_size,
                        color=color,
                        stroke_color=stroke_color,
                        stroke_width=stroke_w,
                    ).with_duration(segment["duration"]).with_position(
                        ("center", int(out_h * pos_y_ratio))
                    )
                    clips.append(txt)
                except Exception:
                    pass
            return clips

        # 逐句字幕
        for s in seg_asr:
            text = s.get("text", "")
            if not text:
                continue

            t_start = s["start"] - seg_start
            t_end = s["end"] - seg_start
            t_dur = t_end - t_start

            if t_dur <= 0:
                continue

            try:
                txt = TextClip(
                    text=self._wrap_text(text, max_chars),
                    font=self.font,
                    font_size=font_size,
                    color=color,
                    stroke_color=stroke_color,
                    stroke_width=stroke_w,
                ).with_duration(t_dur).with_position(
                    ("center", int(out_h * pos_y_ratio))
                ).with_start(t_start)

                clips.append(txt)
            except Exception:
                continue

        return clips

    def _make_keyword_popups(self, segment: dict, asr_segments: list,
                             template: dict, out_w: int, out_h: int) -> list:
        """关键词弹窗（抖音特效）"""
        cfg = template["layout"]["keyword_popup"]
        trigger_words = set(cfg.get("trigger_keywords", []))
        if not trigger_words:
            return []

        font_size = int(out_h * cfg.get("font_size_ratio", 0.05))
        color = cfg.get("color", "#FFD700")
        stroke_color = cfg.get("stroke_color", "#CC0000")
        stroke_w = cfg.get("stroke_width", 3)
        pos_y = int(out_h * cfg.get("position_y_ratio", 0.50))
        duration = cfg.get("duration_seconds", 1.5)
        bg_color = cfg.get("bg_color", "rgba(255,0,0,0.8)")

        clips = []
        popup_start = segment["start"]

        for s in asr_segments:
            text = s.get("text", "")
            if not text:
                continue

            # 检测触发词
            triggered = [kw for kw in trigger_words if kw in text]
            if not triggered:
                continue

            t_start = s["start"] - popup_start
            if t_start < 0:
                continue

            try:
                # 背景
                kw_text = triggered[0]  # 取第一个触发的关键词
                txt_clip = TextClip(
                    text=kw_text,
                    font=self.font,
                    font_size=font_size,
                    color=color,
                    stroke_color=stroke_color,
                    stroke_width=stroke_w,
                )

                # 半透明红底
                txt_w, txt_h = txt_clip.size if hasattr(txt_clip, 'size') else (out_w * 0.3, font_size * 1.5)
                padding = 20
                bg_w = txt_w + padding * 2
                bg_h = txt_h + padding

                bg_clip = ColorClip(
                    size=(bg_w, bg_h),
                    color=self._parse_rgba(bg_color),
                )

                popup = CompositeVideoClip([
                    bg_clip,
                    txt_clip.with_position("center"),
                ]).with_duration(duration).with_position(
                    ("center", pos_y)
                ).with_start(t_start).with_effects([FadeIn(0.15), FadeOut(0.3)])

                clips.append(popup)
            except Exception:
                continue

        return clips

    def _make_knowledge_card(self, segment: dict, template: dict,
                             out_w: int, out_h: int, seg_duration: float
                             ) -> Optional[VideoFileClip]:
        """知识卡片（B站右侧浮层）"""
        cfg = template["layout"]["knowledge_card"]
        if not segment.get("topic"):
            return None

        # 从知识库获取扣分点
        deduction_points = self._get_deduction_points(segment.get("topic", ""))
        if not deduction_points:
            return None

        card_w = int(out_w * cfg.get("width_ratio", 0.30))
        card_h = int(out_h * cfg.get("height_ratio", 0.25))
        margin_r = int(out_w * cfg.get("margin_right_ratio", 0.03))
        margin_t = int(out_h * cfg.get("margin_top_ratio", 0.12))
        font_size = int(out_h * cfg.get("font_size_ratio", 0.025))
        color = cfg.get("color", "#333333")
        bg = self._parse_rgba(cfg.get("bg_color", "rgba(255,255,255,0.92)"))
        border_color = cfg.get("border_color", "#FF6600")
        icon = cfg.get("icon", "💡")
        title = cfg.get("title", "扣分提示")
        duration = cfg.get("show_duration_seconds", 5.0)
        max_lines = cfg.get("max_lines", 4)

        try:
            # 背景
            bg_clip = ColorClip(size=(card_w, card_h), color=bg)

            # 构建文字内容
            lines = [f"{icon} {title}"] + [f"• {p}" for p in deduction_points[:max_lines]]
            text = "\n".join(lines)

            txt_clip = TextClip(
                text=text,
                font=self.font,
                font_size=font_size,
                color=color,
            ).with_position((10, 10))

            card = CompositeVideoClip([
                bg_clip,
                txt_clip,
            ], size=(card_w, card_h)).with_duration(duration).with_position(
                (out_w - card_w - margin_r, margin_t)
            ).with_start(1.0).with_effects([FadeIn(0.3)])

            return card
        except Exception as e:
            print(f"  ⚠ 知识卡片渲染失败: {e}")
            return None

    def _make_key_points_overlay(self, segment: dict, template: dict,
                                 out_w: int, out_h: int, seg_duration: float
                                 ) -> Optional[VideoFileClip]:
        """要点列表覆盖（小红书右侧）"""
        cfg = template["layout"]["key_points_overlay"]
        transcript = segment.get("transcript", "")
        if not transcript:
            return None

        # 从 transcript 中提取要点（按标点分句，取前几条）
        sentences = re.split(r'[，,。！!？?；;]', transcript)
        points = [s.strip() for s in sentences if len(s.strip()) >= 4]
        max_items = cfg.get("max_items", 6)

        if not points:
            return None

        points = points[:max_items]
        prefix = cfg.get("item_prefix", "●")

        overlay_w = int(out_w * cfg.get("width_ratio", 0.35))
        font_size = int(out_h * cfg.get("font_size_ratio", 0.028))
        color = cfg.get("color", "#FFFFFF")
        stroke_color = cfg.get("stroke_color", "#000000")
        stroke_w = cfg.get("stroke_width", 2)
        margin_r = int(out_w * cfg.get("margin_right_ratio", 0.03))
        margin_t = int(out_h * cfg.get("margin_top_ratio", 0.08))
        bg_color = cfg.get("bg_color", "rgba(0,0,0,0.6)")
        line_spacing = cfg.get("line_spacing", 1.6)

        try:
            # 构建文字
            lines = [f"{prefix} {p}" for p in points]
            text = "\n".join(lines)

            # 估算高度
            line_height = int(font_size * line_spacing)
            text_h = line_height * len(lines) + 30
            text_h = min(text_h, out_h - margin_t - 40)

            bg_clip = ColorClip(size=(overlay_w, text_h), color=self._parse_rgba(bg_color))

            txt_clip = TextClip(
                text=text,
                font=self.font,
                font_size=font_size,
                color=color,
                stroke_color=stroke_color,
                stroke_width=stroke_w,
            ).with_position((15, 15))

            overlay = CompositeVideoClip([
                bg_clip,
                txt_clip,
            ], size=(overlay_w, text_h)).with_duration(seg_duration).with_position(
                (out_w - overlay_w - margin_r, margin_t)
            ).with_effects([FadeIn(0.3)])

            return overlay
        except Exception as e:
            print(f"  ⚠ 要点覆盖渲染失败: {e}")
            return None

    def _make_progress_bar(self, template: dict, out_w: int, out_h: int,
                           seg_duration: float) -> Optional[VideoFileClip]:
        """底部进度条"""
        cfg = template["layout"]["progress_bar"]
        bar_h = cfg.get("height_px", 4)
        color = cfg.get("color", "#FF4444")
        bg_color = cfg.get("bg_color", "rgba(255,255,255,0.3)")
        pos = cfg.get("position", "bottom")

        try:
            # 背景条（全宽）
            bg_bar = ColorClip(
                size=(out_w, bar_h),
                color=self._parse_rgba(bg_color),
            )

            # 进度条（从零到满宽）
            # MoviePy 不支持直接 t 参数动画，我们用多个静态帧模拟
            # 简化：用最终长度的静态条
            fg_bar = ColorClip(
                size=(out_w, bar_h),
                color=self._parse_rgba(color),
            ).with_duration(seg_duration)

            # 简化版：全宽进度条（v2 可做动画）
            y_pos = out_h - bar_h - 2 if pos == "bottom" else 2
            combined = CompositeVideoClip([
                bg_bar,
                fg_bar,
            ], size=(out_w, bar_h)).with_duration(seg_duration).with_position(
                (0, y_pos)
            )

            return combined
        except Exception as e:
            print(f"  ⚠ 进度条渲染失败: {e}")
            return None

    # ------------------------------------------------------------------
    # 封面生成
    # ------------------------------------------------------------------

    def _generate_cover(self, segment: dict, source_video: str,
                        template: dict, seg_dir: Path) -> Optional[str]:
        """从小红书片段生成封面图（首帧 + 标题叠加）"""
        cfg = template["layout"]["cover_image"]
        out_w, out_h = template["video"]["output_resolution"]
        cover_path = str(seg_dir / cfg.get("output_path", "cover.jpg"))

        try:
            # 抽取第一帧
            seg_start = segment["start"]
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_name = tmp.name

            subprocess.run([
                "ffmpeg", "-ss", str(seg_start), "-i", source_video,
                "-vframes", "1", "-q:v", "2", "-y", tmp_name,
            ], capture_output=True, check=True)

            # 用 Pillow 叠加标题文字
            from PIL import Image, ImageDraw, ImageFont

            img = Image.open(tmp_name)
            # 裁切为 1:1
            w, h = img.size
            crop_size = min(w, h)
            left = (w - crop_size) // 2
            top = (h - crop_size) // 2
            img = img.crop((left, top, left + crop_size, top + crop_size))
            img = img.resize((out_w, out_h), Image.LANCZOS)

            # 叠加半透明黑色层
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 100))
            img = img.convert("RGBA")
            img = Image.alpha_composite(img, overlay)

            # 添加标题文字
            draw = ImageDraw.Draw(img)
            font_size = int(out_h * cfg.get("cover_text_font_size_ratio", 0.06))
            try:
                font = ImageFont.truetype(self.font, font_size)
            except Exception:
                font = ImageFont.load_default()

            topic = segment.get("topic", "")
            # 文字居中
            bbox = draw.textbbox((0, 0), topic, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            text_x = (out_w - text_w) // 2
            text_y = (out_h - text_h) // 2

            # 描边
            stroke_w = cfg.get("cover_text_stroke_width", 3)
            for dx in range(-stroke_w, stroke_w + 1):
                for dy in range(-stroke_w, stroke_w + 1):
                    if dx == 0 and dy == 0:
                        continue
                    draw.text((text_x + dx, text_y + dy), topic,
                              font=font, fill=cfg.get("cover_text_stroke", "#000000"))

            # 主文字
            draw.text((text_x, text_y), topic,
                      font=font, fill=cfg.get("cover_text_color", "#FFFFFF"))

            img = img.convert("RGB")
            img.save(cover_path, "JPEG", quality=90)

            # 清理
            os.unlink(tmp_name)
            print(f"  ✓ 封面生成: {cover_path}")
            return cover_path

        except Exception as e:
            print(f"  ⚠ 封面生成失败: {e}")
            return None

    # ------------------------------------------------------------------
    # 文案生成
    # ------------------------------------------------------------------

    def _generate_copy(self, segment: dict, platform: str,
                       template: dict, seg_dir: Path) -> Optional[str]:
        """生成各平台文案（调用 LLM）"""
        copy_cfg = template.get("copy_config", {})
        if not copy_cfg.get("include_title"):
            return None

        copy_path = str(seg_dir / "copy.md")

        try:
            title = self._generate_title(segment, platform)
            hashtags = self._get_hashtags(segment)
            description = self._generate_description(segment, platform)

            lines = [
                f"# {platform.upper()} 发布文案",
                "",
                f"## 标题",
                title,
                "",
                f"## 简介",
                description,
                "",
                f"## 标签",
                " ".join(hashtags),
            ]

            with open(copy_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

            print(f"  ✓ 文案生成: {copy_path}")
            return copy_path
        except Exception as e:
            print(f"  ⚠ 文案生成失败: {e}")
            return None

    def _generate_title(self, segment: dict, platform: str) -> str:
        """用 LLM 生成标题"""
        topic = segment.get("topic", "")
        transcript = segment.get("transcript", "")

        # 先尝试用知识库模板
        knowledge = self._get_knowledge()
        templates = knowledge.get("platform_copy_templates", {}).get(platform, {}).get("title_patterns", [])

        if templates:
            # 简单模板填充
            tpl = templates[0]
            title = tpl.replace("{topic}", topic)
            # 估算要点数
            num_points = len(re.split(r'[，,。！!？?；;]', transcript))
            title = title.replace("{num_points}", str(max(1, min(num_points, 5))))

            # 截断到最大长度
            max_len = knowledge.get("platform_copy_templates", {}).get(platform, {}).get("copy_config", {}).get("max_title_length", 50)
            if len(title) > max_len:
                title = title[:max_len - 1] + "…"
            return title

        # 降级：直接返回 topic
        return topic if topic else "驾考教学视频"

    def _generate_description(self, segment: dict, platform: str) -> str:
        """生成简介/描述"""
        topic = segment.get("topic", "")
        transcript = segment.get("transcript", "")

        if platform == "xiaohongshu":
            # 要点列表
            sentences = [s.strip() for s in re.split(r'[，,。！!？?；;]', transcript) if len(s.strip()) >= 4]
            points = "\n".join([f"> {i+1}. {s}" for i, s in enumerate(sentences[:5])])
            return f"📝 {topic} 操作要点：\n\n{points}\n\n💾 收藏起来考前看一遍！"

        elif platform == "bilibili":
            return f"本期讲解{topic}的完整操作步骤和常见扣分点。\n\n📌 重点提示：\n> {transcript[:200]}..."

        else:
            return f"{topic} | 驾考教学 | 科目三必看"

    def _get_hashtags(self, segment: dict) -> list:
        """获取推荐标签"""
        knowledge = self._get_knowledge()
        base_tags = knowledge.get("platform_copy_templates", {}).get("douyin", {}).get("hashtags", [])
        topic_tag = f"#{segment.get('topic', '驾考')}"
        return [topic_tag] + base_tags[:4]

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _get_knowledge(self) -> dict:
        """懒加载知识库"""
        if self._scorer is None:
            self._scorer = SegmentScorer()
        return self._scorer.knowledge

    def _get_deduction_points(self, topic: str) -> list:
        """从知识库查找扣分点"""
        knowledge = self._get_knowledge()
        topic_lower = topic.lower()
        for entry in knowledge.get("high_frequency_topics", []):
            if entry["topic"] in topic or topic in entry["topic"]:
                return entry.get("deduction_points", [])
            for alias in entry.get("aliases", []):
                if alias in topic_lower or topic_lower in alias:
                    return entry.get("deduction_points", [])
        return []

    def _safe_filename(self, name: str) -> str:
        """将话题名转为安全文件名"""
        # 移除非法字符
        safe = re.sub(r'[<>:"/\\|?*]', '', name)
        safe = safe.strip().replace(" ", "_") or "segment"
        return safe

    def _parse_rgba(self, color_str: str) -> tuple:
        """解析颜色字符串为 MoviePy 可用格式"""
        if color_str.startswith("rgba("):
            # rgba(r, g, b, a) → (r, g, b)  # MoviePy v2 使用 0-255 RGB 或 0-1
            parts = re.findall(r'[\d.]+', color_str)
            if len(parts) >= 3:
                return tuple(int(p) for p in parts[:3])
        if color_str.startswith("#"):
            h = color_str.lstrip("#")
            if len(h) == 6:
                return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            elif len(h) == 3:
                return tuple(int(h[i]*2, 16) for i in range(3))
        # fallback
        return (0, 0, 0)

    def _wrap_text(self, text: str, max_chars: int) -> str:
        """文本自动换行"""
        if len(text) <= max_chars:
            return text
        lines = []
        current = ""
        for char in text:
            current += char
            if len(current) >= max_chars:
                lines.append(current)
                current = ""
        if current:
            lines.append(current)
        return "\n".join(lines)


# ------------------------------------------------------------------
# 快速测试
# ------------------------------------------------------------------
if __name__ == "__main__":
    print(f"检测到中文字体: {_detect_chinese_font()}")

    # 测试模板加载
    for p in ["douyin", "bilibili", "xiaohongshu"]:
        tpl = _load_template(p)
        print(f"[{p}] {tpl['name']} → {tpl['video']['output_resolution']}")
