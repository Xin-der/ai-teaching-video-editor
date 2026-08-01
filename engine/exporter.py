"""
多平台视频导出器 — ffmpeg CLI 渲染（支持 NVENC 硬件编码）

支持的平台:
  - douyin:      9:16 竖屏 + 大字幕 + 关键词弹窗 + 进度条
  - bilibili:    16:9 横屏 + 标准字幕 + 知识卡片 + 章节标记
  - xiaohongshu: 1:1 方形 + 要点列表 + 封面图

渲染管线:
  源视频片段 → ffmpeg 裁切/缩放 → ASS 字幕叠加 → NVENC/libx264 编码 → mp4

技术选择:
  - 使用 ASS 字幕格式处理所有文字叠加（比 drawtext 滤镜更强大，原生支持中文）
  - 使用 ffmpeg 原生滤镜处理视频变换和进度条
  - 编码端优先 NVENC 硬件加速，不可用时降级到 libx264
  - 不再依赖 MoviePy（避免逐帧处理的性能问题）
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from .scorer import SegmentScorer


# ------------------------------------------------------------------
# 编码器探测
# ------------------------------------------------------------------
def _detect_encoder() -> tuple:
    """检测可用的 H.264 编码器，优先 NVENC（含实际编码测试）

    Returns:
        (encoder_name, encoder_params_dict)
    """
    ffmpeg = os.environ.get("FFMPEG", "ffmpeg")

    # 先用编码器列表检查 NVENC 是否存在
    try:
        result = subprocess.run(
            [ffmpeg, "-encoders"],
            capture_output=True, text=True, timeout=10
        )
        has_nvenc = "h264_nvenc" in result.stdout
    except Exception:
        has_nvenc = False

    # 对 NVENC 做实际编码测试（部分 GPU 如 Blackwell 可能不兼容）
    if has_nvenc:
        try:
            test_out = os.path.join(tempfile.gettempdir(), "_nvenc_test.mp4")
            r = subprocess.run([
                ffmpeg, "-y", "-f", "lavfi", "-i", "color=size=32x32:rate=1:duration=1",
                "-c:v", "h264_nvenc", "-preset", "p4", "-b:v", "100k",
                "-an", "-t", "1", test_out,
            ], capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                try:
                    os.remove(test_out)
                except Exception:
                    pass
                return "h264_nvenc", {
                    "preset": "p4",
                    "cq": "23",
                    "rc": "vbr",
                }
        except Exception:
            pass

    # 降级到 libx264（NVENC 不可用或不兼容）
    # medium 预设比 fast 慢约 2x 但画质好很多；crf 21 导出质量接近源素材
    return "libx264", {
        "preset": "medium",
        "crf": "21",
    }


# ------------------------------------------------------------------
# 字体检测
# ------------------------------------------------------------------
def _detect_chinese_font() -> str:
    """检测系统中可用的中文字体名，返回 ffmpeg/libass 可识别的字体名

    ASS 字幕使用字体名（非路径），ffmpeg 通过 fontconfig/系统字体目录查找。
    同时验证 Pillow 能否加载（用于封面图生成）。
    """
    if os.name == "nt":
        # Windows: 字体名 + 文件路径映射
        font_dir = os.environ.get("WINDIR", r"C:\Windows") + r"\Fonts"
        candidates = [
            ("SimHei", os.path.join(font_dir, "simhei.ttf")),
            ("Microsoft YaHei", os.path.join(font_dir, "msyh.ttf")),
            ("SimSun", os.path.join(font_dir, "simsun.ttc")),
            ("SimHei", os.path.join(font_dir, "SIMHEI.TTF")),
        ]
    else:
        font_dir = "/usr/share/fonts"
        candidates = [
            ("Noto Sans CJK SC", f"{font_dir}/truetype/noto/NotoSansCJK-Regular.ttf"),
            ("Noto Sans CJK", f"{font_dir}/opentype/noto/NotoSansCJK-Regular.ttc"),
            ("WenQuanYi Micro Hei", f"{font_dir}/truetype/wqy/wqy-microhei.ttc"),
        ]

    from PIL import ImageFont

    for font_name, font_path in candidates:
        # 优先用路径验证（Pillow 需要路径，ASS 需要名称）
        if os.path.exists(font_path):
            try:
                ImageFont.truetype(font_path, 20)
                return font_name  # 返回字体名（ASS 用），但路径已验证
            except Exception:
                continue

    # 降级：尝试只用名称
    for name in ["SimHei", "Arial"]:
        try:
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
    """多平台视频导出器（ffmpeg CLI 后端）"""

    def __init__(self, output_dir: str = "output", font: Optional[str] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.font = font or _detect_chinese_font()
        self._scorer: Optional[SegmentScorer] = None

        # 探测编码器（只执行一次）
        self._encoder, self._encoder_params = _detect_encoder()

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

        seg_name = self._make_seg_dirname(segment)
        seg_dir = self.output_dir / seg_name
        seg_dir.mkdir(parents=True, exist_ok=True)

        output_path = str(seg_dir / f"{platform}.mp4")

        print(f"\n{'='*60}")
        print(f"  导出: [{platform}] {segment.get('topic', '无主题')}")
        print(f"  片段: {segment['start']:.1f}s - {segment['end']:.1f}s ({segment['duration']:.1f}s)")
        print(f"  编码: {self._encoder}")
        print(f"  输出: {output_path}")
        print(f"{'='*60}")

        # 渲染
        self._render_ffmpeg(segment, source_video, template, output_path,
                            asr_segments or [], seg_dir, platform)

        # 生成封面（小红书需要）
        cover_path = None
        if platform == "xiaohongshu" and template["layout"].get("cover_image", {}).get("enabled"):
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
    # ffmpeg 渲染核心
    # ------------------------------------------------------------------

    def _render_ffmpeg(self, segment: dict, source_video: str,
                       template: dict, output_path: str,
                       asr_segments: list, seg_dir: Path,
                       platform: str = "douyin"):
        """使用 ffmpeg CLI 渲染视频（含 BGM 混音 + 效果）"""
        video_cfg = template["video"]
        layout = template["layout"]
        audio_cfg = template.get("audio", {})
        out_w, out_h = video_cfg["output_resolution"]
        fps = video_cfg["fps"]
        seg_start = segment["start"]
        seg_end = segment["end"]
        seg_duration = seg_end - seg_start

        # ---------- 1. 生成 ASS 字幕文件 ----------
        ass_path = str(seg_dir / f"subtitles_{platform}.ass")
        self._write_ass_file(
            segment, template, asr_segments, ass_path,
            out_w, out_h, seg_start, seg_duration
        )

        # ---------- 2. 构建视频滤镜链 ----------
        filter_parts = self._build_video_filters(
            source_video, template, ass_path,
            out_w, out_h, seg_duration
        )

        # ---------- 3. 音频处理 ----------
        bgm_enabled = audio_cfg.get("bgm", {}).get("enabled", False)
        bgm_volume = audio_cfg.get("bgm", {}).get("volume_ratio", 0.15)
        orig_volume = audio_cfg.get("original_audio", {}).get("volume_ratio", 1.0)
        bgm_file = self._find_bgm()

        # ---------- 4. 编码参数 ----------
        if self._encoder == "h264_nvenc":
            vcodec_params = [
                "-c:v", "h264_nvenc",
                "-preset", self._encoder_params["preset"],
                "-cq", self._encoder_params["cq"],
                "-rc", self._encoder_params["rc"],
            ]
        else:
            vcodec_params = [
                "-c:v", "libx264",
                "-preset", self._encoder_params["preset"],
                "-crf", self._encoder_params["crf"],
            ]

        ffmpeg = os.environ.get("FFMPEG", "ffmpeg")

        # ---------- 5. 构建命令 ----------
        if bgm_enabled and bgm_file and os.path.exists(bgm_file):
            # 使用 filter_complex 进行音频混合
            video_filter_str = ",".join(filter_parts)
            bgm_dur = self._probe_duration(bgm_file)
            loop_count = max(1, int(seg_duration / max(bgm_dur, 1)) + 1)

            filter_complex = (
                f"[0:v]{video_filter_str}[v];"
                f"[0:a]volume={orig_volume}[a0];"
                f"[1:a]volume={bgm_volume},"
                f"afade=t=in:d=2,"
                f"afade=t=out:st={seg_duration-2}:d=2[bgm];"
                f"[a0][bgm]amix=inputs=2:duration=first:dropout_transition=2[a]"
            )

            cmd = [
                ffmpeg,
                "-ss", str(seg_start), "-t", str(seg_duration),
                "-i", source_video,
                "-stream_loop", str(loop_count), "-i", bgm_file,
                "-filter_complex", filter_complex,
                "-map", "[v]", "-map", "[a]",
                "-r", str(fps),
                *vcodec_params,
                "-b:v", video_cfg.get("bitrate", "8M"),
                "-c:a", video_cfg.get("audio_codec", "aac"),
                "-b:a", video_cfg.get("audio_bitrate", "256k"),
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y", output_path,
            ]
        else:
            # 无 BGM：简单模式
            cmd = [
                ffmpeg,
                "-ss", str(seg_start), "-t", str(seg_duration),
                "-i", source_video,
                "-vf", ",".join(filter_parts),
                "-r", str(fps),
                *vcodec_params,
                "-b:v", video_cfg.get("bitrate", "8M"),
                "-filter:a", f"volume={orig_volume}",
                "-c:a", video_cfg.get("audio_codec", "aac"),
                "-b:a", video_cfg.get("audio_bitrate", "256k"),
                "-pix_fmt", "yuv420p",
                "-movflags", "+faststart",
                "-y", output_path,
            ]

        print(f"  ffmpeg cmd: {' '.join(cmd)[:200]}...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
            )
            if result.returncode != 0:
                stderr_tail = result.stderr.strip().split("\n")[-10:]
                print(f"  ⚠ ffmpeg 错误:\n" + "\n".join(stderr_tail))
                raise RuntimeError(f"ffmpeg 导出失败 (code={result.returncode})")

            print(f"  ✓ 导出完成: {output_path}")

        except subprocess.TimeoutExpired:
            raise RuntimeError("ffmpeg 导出超时（10分钟）")
        except FileNotFoundError:
            raise RuntimeError("找不到 ffmpeg，请确认已安装并加入 PATH")

    def _find_bgm(self) -> Optional[str]:
        """查找 BGM 文件"""
        bgm_dirs = [
            Path(__file__).parent.parent / "assets" / "bgm",
        ]
        for d in bgm_dirs:
            if d.exists():
                for ext in (".m4a", ".mp3", ".aac", ".wav", ".ogg"):
                    for f in d.glob(f"*{ext}"):
                        return str(f)
        return None

    def _probe_duration(self, audio_path: str) -> float:
        """探测音频文件时长"""
        try:
            ffprobe = os.environ.get("FFPROBE", "ffprobe")
            result = subprocess.run(
                [ffprobe, "-v", "quiet", "-show_entries",
                 "format=duration", "-of", "csv=p=0", audio_path],
                capture_output=True, text=True, timeout=10
            )
            return float(result.stdout.strip())
        except Exception:
            return 60.0  # 默认 60 秒

    # ------------------------------------------------------------------
    # ASS 字幕文件生成
    # ------------------------------------------------------------------

    def _write_ass_file(self, segment: dict, template: dict,
                        asr_segments: list, ass_path: str,
                        out_w: int, out_h: int,
                        seg_start: float, seg_duration: float):
        """生成 ASS 字幕文件，包含所有文字叠加层"""
        layout = template["layout"]

        # 收集所有 ASS 对话事件
        events = []

        # --- 标题卡 ---
        if layout.get("title_card", {}).get("enabled"):
            events.extend(self._ass_title_card(segment, template, out_w, out_h))

        # --- 结尾卡 ---
        if layout.get("ending_card", {}).get("enabled"):
            events.extend(self._ass_ending_card(template, out_w, out_h, seg_duration))

        # --- 字幕 ---
        if layout.get("subtitle", {}).get("enabled"):
            events.extend(self._ass_subtitles(
                segment, asr_segments, template, out_w, out_h, seg_start
            ))

        # --- 关键词弹窗（抖音） ---
        if layout.get("keyword_popup", {}).get("enabled"):
            events.extend(self._ass_keyword_popups(
                segment, asr_segments, template, out_w, out_h
            ))

        # --- 知识卡片（B站） ---
        if layout.get("knowledge_card", {}).get("enabled"):
            events.extend(self._ass_knowledge_card(
                segment, template, out_w, out_h, seg_duration
            ))

        # --- 要点覆盖（小红书） ---
        if layout.get("key_points_overlay", {}).get("enabled"):
            events.extend(self._ass_key_points_overlay(
                segment, template, out_w, out_h, seg_duration
            ))

        # 写入 ASS 文件
        header = self._ass_header(template, out_w, out_h)
        with open(ass_path, "w", encoding="utf-8-sig") as f:
            f.write(header)
            f.write("\n[Events]\n")
            f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
            for evt in events:
                f.write(evt + "\n")

        print(f"  ✓ ASS 字幕: {ass_path} ({len(events)} 事件)")

    def _ass_header(self, template: dict, out_w: int, out_h: int) -> str:
        """生成 ASS 文件头部（含样式定义）"""
        video_cfg = template["video"]
        layout = template["layout"]

        # 基础字体大小（按分辨率缩放）
        base_fs = int(out_h * 0.04)

        # 颜色转换: #RRGGBB or rgba(r,g,b,a) -> &HAABBGGRR
        def ass_color(hex_or_rgba: str, alpha: int = 0) -> str:
            """转 ASS 颜色格式 &HAABBGGRR"""
            r, g, b = 255, 255, 255
            a = alpha
            if hex_or_rgba.startswith("rgba("):
                parts = re.findall(r'[\d.]+', hex_or_rgba)
                if len(parts) >= 4:
                    r, g, b, a_frac = int(parts[0]), int(parts[1]), int(parts[2]), float(parts[3])
                    a = int((1 - a_frac) * 255)  # ASS alpha: 0=opaque, 255=transparent
            elif hex_or_rgba.startswith("#"):
                h = hex_or_rgba.lstrip("#")
                if len(h) == 6:
                    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                elif len(h) == 3:
                    r, g, b = int(h[0]*2, 16), int(h[1]*2, 16), int(h[2]*2, 16)
            return f"&H{a:02X}{b:02X}{g:02X}{r:02X}"

        # 样式定义
        styles = []

        # Default
        styles.append(
            f"Style: Default,{self.font},{base_fs},"
            f"&H00FFFFFF,&H00000000,&H00000000,&H00000000,"
            f"0,0,0,0,100,100,0,0,1,0,0,2,10,10,10,1"
        )

        # Title — 顶部居中，半透明黑底
        title_cfg = layout.get("title_card", {})
        title_fs = int(out_h * title_cfg.get("font_size_ratio", 0.06))
        title_color = ass_color(title_cfg.get("color", "#FFFFFF"))
        title_stroke = ass_color(title_cfg.get("stroke_color", "#000000"))
        styles.append(
            f"Style: Title,{self.font},{title_fs},"
            f"{title_color},&H00000000,{title_stroke},&H80000000,"
            f"1,0,0,0,100,100,0,0,3,3,0,8,10,10,10,1"
        )

        # Subtitle — 底部居中，黑色描边
        sub_cfg = layout.get("subtitle", {})
        sub_fs = int(out_h * sub_cfg.get("font_size_ratio", 0.045))
        sub_color = ass_color(sub_cfg.get("color", "#FFFFFF"))
        sub_stroke = ass_color(sub_cfg.get("stroke_color", "#000000"))
        styles.append(
            f"Style: Subtitle,{self.font},{sub_fs},"
            f"{sub_color},&H00000000,{sub_stroke},&H00000000,"
            f"0,0,0,0,100,100,0,0,1,4,0,2,10,10,10,1"
        )

        # Popup — 居中，红底黄字
        popup_cfg = layout.get("keyword_popup", {})
        popup_fs = int(out_h * popup_cfg.get("font_size_ratio", 0.05))
        popup_color = ass_color(popup_cfg.get("color", "#FFD700"))
        popup_stroke = ass_color(popup_cfg.get("stroke_color", "#CC0000"))
        styles.append(
            f"Style: Popup,{self.font},{popup_fs},"
            f"{popup_color},&H00000000,{popup_stroke},&HCC0000FF,"
            f"1,0,0,0,100,100,0,0,3,3,0,5,10,10,10,1"
        )

        # KnowledgeCard — 右侧浮层，白底深色字
        kc_cfg = layout.get("knowledge_card", {})
        kc_fs = int(out_h * kc_cfg.get("font_size_ratio", 0.025))
        kc_color = ass_color(kc_cfg.get("color", "#333333"))
        styles.append(
            f"Style: KnowledgeCard,{self.font},{kc_fs},"
            f"{kc_color},&H00000000,&H00000000,&HEBFFFFFF,"
            f"0,0,0,0,100,100,0,0,3,0,0,7,10,10,10,1"
        )

        # KeyPoints — 右侧覆盖，半透明黑底白字
        kp_cfg = layout.get("key_points_overlay", {})
        kp_fs = int(out_h * kp_cfg.get("font_size_ratio", 0.028))
        kp_color = ass_color(kp_cfg.get("color", "#FFFFFF"))
        kp_stroke = ass_color(kp_cfg.get("stroke_color", "#000000"))
        styles.append(
            f"Style: KeyPoints,{self.font},{kp_fs},"
            f"{kp_color},&H00000000,{kp_stroke},&H99000000,"
            f"0,0,0,0,100,100,0,0,3,2,0,7,10,10,10,1"
        )

        # Ending — 全屏居中
        end_cfg = layout.get("ending_card", {})
        end_fs = int(out_h * end_cfg.get("font_size_ratio", 0.04))
        end_color = ass_color(end_cfg.get("color", "#FFFFFF"))
        styles.append(
            f"Style: Ending,{self.font},{end_fs},"
            f"{end_color},&H00000000,&H00000000,&HB2000000,"
            f"1,0,0,0,100,100,0,0,3,0,0,5,10,10,10,1"
        )

        # ChapterMarker — 左上角
        styles.append(
            f"Style: ChapterMarker,{self.font},{int(out_h*0.03)},"
            f"&H000066FF,&H00000000,&H00000000,&H00000000,"
            f"1,0,0,0,100,100,0,0,1,2,0,7,10,10,10,1"
        )

        return (
            f"[Script Info]\n"
            f"Title: AI Teaching Video Export\n"
            f"ScriptType: v4.00+\n"
            f"PlayResX: {out_w}\n"
            f"PlayResY: {out_h}\n"
            f"WrapStyle: 0\n"
            f"ScaledBorderAndShadow: yes\n"
            f"\n"
            f"[V4+ Styles]\n"
            f"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
            f"OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
            f"ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            f"Alignment, MarginL, MarginR, MarginV, Encoding\n"
            + "\n".join(styles) + "\n"
        )

    # ------------------------------------------------------------------
    # ASS 事件生成器
    # ------------------------------------------------------------------

    def _sec_to_ass_time(self, seconds: float) -> str:
        """秒 → ASS 时间格式 H:MM:SS.cc"""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def _escape_ass_text(self, text: str) -> str:
        """转义 ASS 特殊字符"""
        # ASS 中不需要转义大多数字符，但需要处理换行 \N
        return text.replace("\n", "\\N").replace("{", "\\{").replace("}", "\\}")

    def _ass_title_card(self, segment: dict, template: dict,
                        out_w: int, out_h: int) -> list:
        """标题卡 ASS 事件"""
        cfg = template["layout"]["title_card"]
        topic = segment.get("topic", "")
        if not topic:
            return []

        duration = cfg.get("duration_seconds", 2.0)
        text = self._escape_ass_text(topic)
        # 顶部居中偏上
        y_pos = int(out_h * 0.06)

        # 滑入动画：从顶部外滑入 + 淡入
        anim_start_y = -int(out_h * 0.08)
        return [
            f"Dialogue: 0,{self._sec_to_ass_time(0)},"
            f"{self._sec_to_ass_time(duration)},"
            f"Title,,0,0,0,,{{\\pos({out_w//2},{anim_start_y})"
            f"\\t(0,500,\\pos({out_w//2},{y_pos}))"
            f"\\fad(200,0)}}{text}"
        ]

    def _ass_ending_card(self, template: dict, out_w: int, out_h: int,
                         seg_duration: float) -> list:
        """结尾卡 ASS 事件"""
        cfg = template["layout"]["ending_card"]
        text = cfg.get("text", "")
        if not text:
            return []

        duration = cfg.get("duration_seconds", 3.0)
        start_t = max(seg_duration - duration, 0)
        text = self._escape_ass_text(text)

        return [
            f"Dialogue: 0,{self._sec_to_ass_time(start_t)},"
            f"{self._sec_to_ass_time(seg_duration)},"
            f"Ending,,0,0,0,,{{\\pos({out_w//2},{out_h//2})\\fad(500,0)}}{text}"
        ]

    def _ass_subtitles(self, segment: dict, asr_segments: list,
                       template: dict, out_w: int, out_h: int,
                       seg_start: float) -> list:
        """字幕 ASS 事件"""
        cfg = template["layout"]["subtitle"]
        pos_y_ratio = cfg.get("position_y_ratio", 0.80)
        pos_y = int(out_h * pos_y_ratio)
        max_chars = cfg.get("max_chars_per_line", 18)
        max_lines = cfg.get("max_lines", 2)
        font_size_ratio = cfg.get("font_size_ratio", 0.045)
        font_size = int(out_h * font_size_ratio)

        # 标题卡时长，字幕在其结束后才开始
        title_dur = template["layout"].get("title_card", {}).get("duration_seconds", 0)
        MAX_SUB_DURATION = 5.0  # 单句字幕最长显示时间

        seg_end = seg_start + segment["duration"]
        seg_asr = [
            s for s in asr_segments
            if s.get("start", 0) >= seg_start - 0.1
            and s.get("end", 0) <= seg_end + 0.1
        ]

        if not seg_asr:
            transcript = segment.get("transcript", "")
            if transcript:
                # 用安全的字符数换行（clip 是最后防线）
                safe_chars = int(out_w / font_size * 0.85)
                text = self._escape_ass_text(
                    self._wrap_text(transcript, safe_chars)
                )
                text = self._truncate_lines(text, max_lines)
                safe_m = int(out_w * 0.04)
                return [
                    f"Dialogue: 0,{self._sec_to_ass_time(title_dur)},"
                    f"{self._sec_to_ass_time(min(title_dur+MAX_SUB_DURATION, segment['duration']))},"
                    f"Subtitle,,0,0,0,,"
                    f"{{\\clip({safe_m},{int(out_h*0.60)},{out_w-safe_m},{out_h})"
                    f"\\pos({out_w//2},{pos_y})"
                    f"\\3c&H88000000\\bord12\\shad0}}{text}"
                ]
            return []

        # 字幕安全区：底部区域，左右留边距，硬裁剪防止溢出
        margin_x = int(out_w * 0.04)
        safe_left = margin_x
        safe_right = out_w - margin_x
        safe_top = int(out_h * 0.60)
        safe_bottom = out_h

        events = []
        for s in seg_asr:
            raw_text = s.get("text", "")
            if not raw_text:
                continue

            t_start = max(s["start"] - seg_start, title_dur)
            t_end = min(s["end"] - seg_start, segment["duration"])
            if t_end <= t_start:
                continue

            if t_end - t_start > MAX_SUB_DURATION:
                t_end = t_start + MAX_SUB_DURATION

            # 安全换行 + \clip 硬裁剪（双重保障）
            safe_chars = int(out_w / font_size * 0.85)
            text = self._escape_ass_text(
                self._wrap_text(raw_text, safe_chars)
            )
            text = self._truncate_lines(text, max_lines)
            events.append(
                f"Dialogue: 0,{self._sec_to_ass_time(t_start)},"
                f"{self._sec_to_ass_time(t_end)},"
                f"Subtitle,,0,0,0,,"
                f"{{\\clip({safe_left},{safe_top},{safe_right},{safe_bottom})"
                f"\\pos({out_w//2},{pos_y})"
                f"\\3c&H88000000\\bord12\\shad0}}{text}"
            )

        return events

    def _truncate_lines(self, text: str, max_lines: int) -> str:
        """截断超出 max_lines 的行"""
        if max_lines <= 0:
            return text
        lines = text.split("\\N")
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            # 最后一行加省略号标记
            lines[-1] = lines[-1].rstrip() + "…"
        return "\\N".join(lines)

    def _ass_keyword_popups(self, segment: dict, asr_segments: list,
                            template: dict, out_w: int, out_h: int) -> list:
        """关键词弹窗 ASS 事件"""
        cfg = template["layout"]["keyword_popup"]
        trigger_words = set(cfg.get("trigger_keywords", []))
        if not trigger_words:
            return []

        pos_y = int(out_h * cfg.get("position_y_ratio", 0.50))
        duration = cfg.get("duration_seconds", 1.5)

        events = []
        popup_start = segment["start"]

        for s in asr_segments:
            text = s.get("text", "")
            if not text:
                continue

            triggered = [kw for kw in trigger_words if kw in text]
            if not triggered:
                continue

            t_start = s["start"] - popup_start
            if t_start < 0:
                continue
            t_end = t_start + duration

            kw_text = self._escape_ass_text(triggered[0])
            # 弹跳动画：从 150% 缩小到 100% + 淡入淡出
            events.append(
                f"Dialogue: 0,{self._sec_to_ass_time(t_start)},"
                f"{self._sec_to_ass_time(t_end)},"
                f"Popup,,0,0,0,,{{\\pos({out_w//2},{pos_y})"
                f"\\fscx150\\fscy150\\t(0,250,\\fscx100\\fscy100)"
                f"\\fad(100,300)}}{kw_text}"
            )

        return events

    def _ass_knowledge_card(self, segment: dict, template: dict,
                            out_w: int, out_h: int, seg_duration: float) -> list:
        """知识卡片 ASS 事件（B站）"""
        cfg = template["layout"]["knowledge_card"]
        if not segment.get("topic"):
            return []

        deduction_points = self._get_deduction_points(segment.get("topic", ""))
        if not deduction_points:
            return []

        card_w = int(out_w * cfg.get("width_ratio", 0.30))
        margin_r = int(out_w * cfg.get("margin_right_ratio", 0.03))
        margin_t = int(out_h * cfg.get("margin_top_ratio", 0.12))
        x_pos = out_w - card_w - margin_r
        max_lines = cfg.get("max_lines", 4)
        icon = cfg.get("icon", "💡")
        title = cfg.get("title", "扣分提示")
        show_dur = cfg.get("show_duration_seconds", 5.0)

        lines = [f"{icon} {title}"] + [f"• {p}" for p in deduction_points[:max_lines]]
        text = self._escape_ass_text("\\N".join(lines))

        return [
            f"Dialogue: 0,{self._sec_to_ass_time(1.0)},"
            f"{self._sec_to_ass_time(1.0 + show_dur)},"
            f"KnowledgeCard,,0,0,0,,{{\\pos({x_pos},{margin_t})\\fad(300,0)}}{text}"
        ]

    def _ass_key_points_overlay(self, segment: dict, template: dict,
                                out_w: int, out_h: int, seg_duration: float) -> list:
        """要点列表覆盖 ASS 事件（小红书）"""
        cfg = template["layout"]["key_points_overlay"]
        transcript = segment.get("transcript", "")
        if not transcript:
            return []

        sentences = re.split(r'[，,。！!？?；;]', transcript)
        points = [s.strip() for s in sentences if len(s.strip()) >= 4]
        max_items = cfg.get("max_items", 6)
        if not points:
            return []

        points = points[:max_items]
        prefix = cfg.get("item_prefix", "●")

        overlay_w = int(out_w * cfg.get("width_ratio", 0.35))
        margin_r = int(out_w * cfg.get("margin_right_ratio", 0.03))
        margin_t = int(out_h * cfg.get("margin_top_ratio", 0.08))
        x_pos = out_w - overlay_w - margin_r

        lines = [f"{prefix} {p}" for p in points]
        text = self._escape_ass_text("\\N".join(lines))

        return [
            f"Dialogue: 0,{self._sec_to_ass_time(0)},"
            f"{self._sec_to_ass_time(seg_duration)},"
            f"KeyPoints,,0,0,0,,{{\\pos({x_pos},{margin_t})\\fad(300,0)}}{text}"
        ]

    # ------------------------------------------------------------------
    # 视频滤镜链
    # ------------------------------------------------------------------

    def _build_video_filters(self, source_video: str, template: dict,
                             ass_path: str, out_w: int, out_h: int,
                             seg_duration: float) -> list:
        """构建 ffmpeg 视频滤镜链

        Returns:
            滤镜字符串列表，用逗号连接后传给 -vf
        """
        layout = template["layout"]
        filters = []

        # 1. 探测源视频分辨率
        src_w, src_h = self._probe_resolution(source_video)

        # 2. 裁切到目标比例
        if src_w > 0 and src_h > 0:
            target_ratio = out_w / out_h
            src_ratio = src_w / src_h

            if abs(target_ratio - src_ratio) > 0.01:
                if target_ratio > src_ratio:
                    # 目标更宽 → 裁切上下
                    new_h = int(src_w / target_ratio)
                    crop_y = (src_h - new_h) // 2
                    filters.append(f"crop={src_w}:{new_h}:0:{crop_y}")
                else:
                    # 目标更高 → 裁切左右
                    new_w = int(src_h * target_ratio)
                    crop_x = (src_w - new_w) // 2
                    filters.append(f"crop={new_w}:{src_h}:{crop_x}:0")

        # 3. 缩放到输出分辨率
        filters.append(f"scale={out_w}:{out_h}:flags=lanczos")

        # 4. 画质增强（轻度调色）
        filters.append("eq=contrast=1.08:brightness=0.02:saturation=1.05")

        # 5. 进度条
        if layout.get("progress_bar", {}).get("enabled"):
            filters.append(self._filter_progress_bar(template, out_w, out_h))

        # 6. ASS 字幕烧录
        ass_path_escaped = ass_path.replace("\\", "/").replace(":", "\\:")
        filters.append(f"ass='{ass_path_escaped}'")

        # 7. 格式转换
        filters.append("format=yuv420p")

        return filters

    def _probe_resolution(self, video_path: str) -> tuple:
        """探测视频分辨率"""
        try:
            ffprobe = os.environ.get("FFPROBE", "ffprobe")
            result = subprocess.run(
                [ffprobe, "-v", "quiet", "-print_format", "json",
                 "-show_streams", video_path],
                capture_output=True, text=True, timeout=15
            )
            info = json.loads(result.stdout)
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    return stream.get("width", 0), stream.get("height", 0)
        except Exception:
            pass
        return 0, 0

    def _filter_progress_bar(self, template: dict, out_w: int, out_h: int) -> str:
        """生成进度条"""
        cfg = template["layout"]["progress_bar"]
        bar_h = cfg.get("height_px", 6)
        color = cfg.get("color", "#FF4444").lstrip("#")

        if len(color) == 6:
            r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
        else:
            r, g, b = 255, 68, 68

        y_bar = out_h - bar_h - 2

        return (
            f"drawbox=0:{out_h - bar_h - 2}:{out_w}:{bar_h + 2}:"
            f"black@0.3:t=fill,"
            f"drawbox=0:{y_bar}:{out_w}:{bar_h}:"
            f"0x{r:02X}{g:02X}{b:02X}@0.8:t=fill"
        )

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
            seg_start = segment["start"]

            # 抽取第一帧
            ffmpeg = os.environ.get("FFMPEG", "ffmpeg")
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_name = tmp.name

            subprocess.run([
                ffmpeg, "-ss", str(seg_start), "-i", source_video,
                "-vframes", "1", "-q:v", "2", "-y", tmp_name,
            ], capture_output=True, check=True, timeout=30)

            # 用 Pillow 叠加标题
            from PIL import Image, ImageDraw, ImageFont

            img = Image.open(tmp_name)
            # 裁切 1:1
            w, h = img.size
            crop_size = min(w, h)
            left = (w - crop_size) // 2
            top = (h - crop_size) // 2
            img = img.crop((left, top, left + crop_size, top + crop_size))
            img = img.resize((out_w, out_h), Image.LANCZOS)

            # 半透明黑色层
            overlay = Image.new("RGBA", img.size, (0, 0, 0, 100))
            img = img.convert("RGBA")
            img = Image.alpha_composite(img, overlay)

            draw = ImageDraw.Draw(img)
            font_size = int(out_h * cfg.get("cover_text_font_size_ratio", 0.06))
            try:
                font = ImageFont.truetype(self.font, font_size)
            except Exception:
                font = ImageFont.load_default()

            topic = segment.get("topic", "")
            bbox = draw.textbbox((0, 0), topic, font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            text_x = (out_w - text_w) // 2
            text_y = (out_h - text_h) // 2

            stroke_w = cfg.get("cover_text_stroke_width", 3)
            stroke_color = cfg.get("cover_text_stroke", "#000000")
            text_color = cfg.get("cover_text_color", "#FFFFFF")

            # 描边
            for dx in range(-stroke_w, stroke_w + 1):
                for dy in range(-stroke_w, stroke_w + 1):
                    if dx == 0 and dy == 0:
                        continue
                    draw.text((text_x + dx, text_y + dy), topic,
                              font=font, fill=stroke_color)
            draw.text((text_x, text_y), topic, font=font, fill=text_color)

            img = img.convert("RGB")
            img.save(cover_path, "JPEG", quality=90)

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
        """生成各平台发布文案"""
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
        """用知识库模板生成标题"""
        topic = segment.get("topic", "")
        transcript = segment.get("transcript", "")

        knowledge = self._get_knowledge()
        templates = knowledge.get("platform_copy_templates", {}).get(platform, {}).get("title_patterns", [])

        if templates:
            tpl = templates[0]
            title = tpl.replace("{topic}", topic)
            num_points = len(re.split(r'[，,。！!？?；;]', transcript))
            title = title.replace("{num_points}", str(max(1, min(num_points, 5))))

            max_len = knowledge.get("platform_copy_templates", {}).get(platform, {}).get("copy_config", {}).get("max_title_length", 50)
            if len(title) > max_len:
                title = title[:max_len - 1] + "…"
            return title

        return topic if topic else "驾考教学视频"

    def _generate_description(self, segment: dict, platform: str) -> str:
        """生成简介/描述"""
        topic = segment.get("topic", "")
        transcript = segment.get("transcript", "")

        if platform == "xiaohongshu":
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
        safe = re.sub(r'[<>:"/\\|?*]', '', name)
        safe = safe.strip().replace(" ", "_") or "segment"
        return safe

    def _make_seg_dirname(self, segment: dict) -> str:
        """为片段生成唯一目录名，格式: {编号}_{话题}
        确保同名话题的多个片段不会互相覆盖。
        """
        seg_id = segment.get("id", 0)
        topic = segment.get("topic", "segment")
        safe_topic = self._safe_filename(topic)
        return f"{seg_id:02d}_{safe_topic}"

    def _wrap_text(self, text: str, max_chars: int,
                   out_w: int = 0, font_size: int = 0) -> str:
        """文本自动换行（ASS 用 \\N）

        支持两种模式：
        1. 纯字符数模式（out_w=0 时）：按 max_chars 字符换行
        2. 像素宽度模式（out_w>0 时）：按实际渲染像素宽度换行
           - CJK 字符宽度 ≈ font_size × 1.0
           - ASCII/Latin 字符宽度 ≈ font_size × 0.55
        """
        if out_w <= 0 or font_size <= 0:
            # 降级：纯字符数模式
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
            return "\\N".join(lines)

        # 像素宽度模式
        max_width = int(out_w * 0.88)  # 留 12% 边距
        lines = []
        current = ""
        current_width = 0

        for char in text:
            # 估算每个字符的像素宽度
            if ord(char) > 0x2000:  # CJK 及全角字符
                char_w = font_size
            elif char in (' ', '\t'):
                char_w = font_size * 0.3
            else:  # ASCII/数字/半角标点
                char_w = int(font_size * 0.55)

            if current_width + char_w > max_width and current:
                lines.append(current)
                current = char
                current_width = char_w
            else:
                current += char
                current_width += char_w

        if current:
            lines.append(current)

        return "\\N".join(lines) if lines else text


# ------------------------------------------------------------------
# 快速测试
# ------------------------------------------------------------------
if __name__ == "__main__":
    print(f"检测到中文字体: {_detect_chinese_font()}")

    encoder, params = _detect_encoder()
    print(f"编码器: {encoder} | 参数: {params}")

    for p in ["douyin", "bilibili", "xiaohongshu"]:
        tpl = _load_template(p)
        print(f"[{p}] {tpl['name']} → {tpl['video']['output_resolution']}")
