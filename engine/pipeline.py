"""
核心管线：音频提取 → ASR → 场景检测 → VLM关键帧描述 → 智能分段 → 评分

用法:
    from engine.pipeline import Pipeline

    p = Pipeline("input/video.mp4")
    segments = p.run()              # 全流程
    segments = p.run(skip_asr=True) # 跳过 ASR（使用缓存）
    p.print_segments(segments)      # 打印分段预览
"""

import base64
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

# Fix Unicode emoji output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv

# 在导入其他模块前加载 .env
load_dotenv()

from .scorer import SegmentScorer

# ------------------------------------------------------------------
# 配置
# ------------------------------------------------------------------
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
MODEL = os.environ.get("MODEL", "qwen3.7-plus")

# DashScope OpenAI-compatible endpoint
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class Pipeline:
    """视频智能切片管线"""

    def __init__(self, video_path: str,
                 output_dir: str = "output",
                 work_dir: str = "work"):
        """
        Args:
            video_path:  源视频路径
            output_dir:  最终输出目录
            work_dir:    中间产物目录
        """
        self.video_path = Path(video_path)
        if not self.video_path.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        self.output_dir = Path(output_dir)
        self.work_dir = Path(work_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # 中间产物路径
        self.audio_path = self.work_dir / "audio.wav"
        self.asr_result_path = self.work_dir / "asr_result.json"
        self.scenes_path = self.work_dir / "scenes.json"
        self.frames_dir = self.work_dir / "frames"
        self.descriptions_path = self.work_dir / "frame_descriptions.json"
        self.segments_path = self.work_dir / "segments.json"
        self.analysis_path = self.work_dir / "content_analysis.json"

        # 状态
        self.video_duration: float = 0.0
        self.asr_segments: list = []
        self.scenes: list = []
        self.frame_descriptions: list = []
        self.merged_segments: list = []
        self.content_analysis: dict = {}

        # 子模块
        self._scorer: Optional[SegmentScorer] = None
        self._openai_client = None

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def run(self, *,
            skip_audio: bool = False,
            skip_asr: bool = False,
            skip_scenes: bool = False,
            skip_vlm: bool = False,
            skip_llm: bool = False,
            ) -> list:
        """执行完整管线

        Args:
            skip_audio:  跳过音频提取（使用已有 work/audio.wav）
            skip_asr:    跳过 ASR（使用已有 work/asr_result.json）
            skip_scenes: 跳过场景检测（使用已有 work/scenes.json + frames/）
            skip_vlm:    跳过 VLM 描述（使用已有 work/frame_descriptions.json）
            skip_llm:    跳过 LLM 内容分析（使用已有 work/content_analysis.json）

        Returns:
            合并后的片段列表，每个片段含评分
        """
        print(f"\n{'='*60}")
        print(f"  智能切片管线启动")
        print(f"  视频: {self.video_path}")
        print(f"  工作目录: {self.work_dir}")
        print(f"  输出目录: {self.output_dir}")
        print(f"{'='*60}")

        t0 = time.time()

        # Step 1: 获取视频信息
        self._probe_video()

        # Step 2: 音频提取
        if not skip_audio:
            self._extract_audio()
        else:
            print("\n[Step 2] ⏭ 跳过音频提取（使用缓存）")

        # Step 3: ASR
        if not skip_asr:
            self._run_asr()
        else:
            print("\n[Step 3] ⏭ 跳过 ASR（使用缓存）")
            self._load_asr()

        # Step 4: 场景检测 + 抽帧
        if not skip_scenes:
            self._detect_scenes()
        else:
            print("\n[Step 4] ⏭ 跳过场景检测（使用缓存）")
            self._load_scenes()

        # Step 5: VLM 描述关键帧
        if not skip_vlm:
            self._describe_frames()
        else:
            print("\n[Step 5] ⏭ 跳过 VLM 描述（使用缓存）")
            self._load_descriptions()

        # Step 5.5: LLM 内容分析
        if not skip_llm:
            self._analyze_content()
        else:
            print("\n[Step 5.5] ⏭ 跳过 LLM 内容分析（使用缓存）")
            self._load_analysis()

        # Step 6: 智能合并分段
        print("\n" + "=" * 60)
        print("  [Step 6] 智能分段合并...")
        print("=" * 60)
        self._merge_segments()

        # Step 7: 评分
        print("\n" + "=" * 60)
        print("  [Step 7] 片段评分...")
        print("=" * 60)
        self._score_segments()

        elapsed = time.time() - t0
        print(f"\n{'='*60}")
        print(f"  管线完成! 耗时 {elapsed:.1f}s, 共 {len(self.merged_segments)} 个片段")
        print(f"{'='*60}")

        self._save_segments()
        return self.merged_segments

    def extract_transcript(self) -> list:
        """公开：音频提取 + ASR 转录，返回 ASR 段列表 [{start, end, text}, ...]"""
        self._extract_audio()
        self._run_asr()
        return self.asr_segments

    def extract_visuals(self) -> list:
        """公开：场景检测 + 关键帧抽取 + VLM 描述，返回帧描述列表"""
        self._detect_scenes()
        self._describe_frames()
        return self.frame_descriptions

    # ------------------------------------------------------------------
    # Step 1: 视频探测
    # ------------------------------------------------------------------

    def _probe_video(self):
        """获取视频元信息"""
        print("\n[Step 1] 获取视频信息...")
        try:
            result = subprocess.run(
                [FFPROBE, "-v", "quiet", "-print_format", "json",
                 "-show_format", "-show_streams", str(self.video_path)],
                capture_output=True, text=True, check=True
            )
            info = json.loads(result.stdout)
            fmt = info.get("format", {})
            self.video_duration = float(fmt.get("duration", 0))

            # 找到视频流
            for stream in info.get("streams", []):
                if stream.get("codec_type") == "video":
                    self.video_width = stream.get("width", 0)
                    self.video_height = stream.get("height", 0)
                    self.video_fps = eval(str(stream.get("r_frame_rate", "30/1")))
                    break

            mins = int(self.video_duration // 60)
            secs = int(self.video_duration % 60)
            size_mb = os.path.getsize(self.video_path) / 1024 / 1024
            print(f"  时长: {mins}分{secs}秒 ({self.video_duration:.1f}s)")
            print(f"  分辨率: {self.video_width}x{self.video_height}")
            print(f"  大小: {size_mb:.1f} MB")
        except Exception as e:
            print(f"  ⚠ 视频探测失败: {e}")
            self.video_duration = 0

    # ------------------------------------------------------------------
    # Step 2: 音频提取
    # ------------------------------------------------------------------

    def _extract_audio(self):
        """用 ffmpeg 提取音频"""
        print(f"\n[Step 2] 提取音频 → {self.audio_path}")
        if self.audio_path.exists():
            print(f"  音频文件已存在，跳过")
            return

        subprocess.run([
            FFMPEG, "-i", str(self.video_path),
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000",
            "-ac", "1", "-y", str(self.audio_path),
        ], capture_output=True, check=True)
        print(f"  音频提取完成")

    # ------------------------------------------------------------------
    # Step 3: ASR 语音识别
    # ------------------------------------------------------------------

    def _run_asr(self):
        """SenseVoice 抗噪语音识别（engine.asr.SenseVoiceASR）"""
        print(f"\n[Step 3] ASR 语音识别...")

        if self.asr_result_path.exists():
            print(f"  加载已有 ASR 结果")
            self._load_asr()
            return

        from engine.asr import SenseVoiceASR
        asr = SenseVoiceASR()
        self.asr_segments = asr.transcribe(str(self.audio_path))

        # 轻量后处理
        self.asr_segments = self._postprocess_asr(self.asr_segments)

        with open(self.asr_result_path, "w", encoding="utf-8") as f:
            json.dump({"segments": self.asr_segments, "total": len(self.asr_segments)},
                      f, ensure_ascii=False, indent=2)

        print(f"  ASR 完成! 共 {len(self.asr_segments)} 句（后处理后）")

    def _postprocess_asr(self, segments: list) -> list:
        """ASR 后处理：轻量清理（SenseVoice+VAD 已按语音段出句）

        1. 过滤空文本 / 超短孤立词（< 0.3s 且 ≤2 字，如"啊""嗯"）
        2. 合并时间重叠且文本高度相似的相邻句
        """
        if not segments:
            return segments

        # 第 1 步：过滤空文本与超短孤立词
        filtered = []
        for seg in segments:
            text = (seg.get("text") or "").strip()
            if not text:
                continue
            dur = seg["end"] - seg["start"]
            if dur < 0.3 and len(text) <= 2:
                continue
            filtered.append({**seg, "text": text})

        # 第 2 步：合并时间重叠且文本高度相似的相邻句
        if len(filtered) <= 1:
            return filtered

        merged = [filtered[0]]
        for seg in filtered[1:]:
            prev = merged[-1]
            time_overlap = seg["start"] <= prev["end"]
            text_similar = (
                seg["text"] in prev["text"] or prev["text"] in seg["text"]
            )
            if time_overlap and text_similar:
                # 保留更长文本、更宽时间范围
                merged[-1]["end"] = max(prev["end"], seg["end"])
                if len(seg["text"]) > len(prev["text"]):
                    merged[-1]["text"] = seg["text"]
                continue
            merged.append(seg)

        return merged

    def _load_asr(self):
        """加载缓存的 ASR 结果"""
        if self.asr_result_path.exists():
            with open(self.asr_result_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.asr_segments = data.get("segments", [])
            print(f"  加载 {len(self.asr_segments)} 句 ASR 结果")

    # ------------------------------------------------------------------
    # Step 4: 场景检测 + 关键帧抽取
    # ------------------------------------------------------------------

    def _detect_scenes(self):
        """PySceneDetect 场景检测 + ffmpeg 抽帧"""
        print(f"\n[Step 4] 场景检测 + 关键帧抽取...")

        if self.scenes_path.exists():
            self._load_scenes()
            # 仍然检查是否需要抽帧
            if list(self.frames_dir.glob("*.jpg")):
                return
        else:
            # 场景检测
            print("  PySceneDetect 检测中...")
            from scenedetect import open_video as sd_open, SceneManager, ContentDetector

            video = sd_open(str(self.video_path))
            sm = SceneManager()
            sm.add_detector(ContentDetector(threshold=30))
            sm.detect_scenes(video)

            raw_scenes = sm.get_scene_list()
            self.scenes = []
            for i, (start, end) in enumerate(raw_scenes):
                s = start.get_seconds()
                e = end.get_seconds()
                self.scenes.append({
                    "id": i,
                    "start": round(s, 2),
                    "end": round(e, 2),
                    "duration": round(e - s, 2),
                })

            if not self.scenes and self.video_duration > 0:
                # 单镜头/无场景切换视频（如教练手机随手拍）：按时长等分合成伪场景，
                # 保证 VLM 描述与帧点评都有关键帧可分析
                self.scenes = self._synthesize_scenes()
                print(f"  ⚠ 未检测到场景切换，合成 {len(self.scenes)} 段伪场景保底关键帧")

            with open(self.scenes_path, "w", encoding="utf-8") as f:
                json.dump({"scenes": self.scenes, "total": len(self.scenes)},
                          f, ensure_ascii=False, indent=2)

            print(f"  检测到 {len(self.scenes)} 个场景")

        # 抽关键帧
        print(f"  抽取关键帧 → {self.frames_dir}")
        self.frames_dir.mkdir(parents=True, exist_ok=True)

        for seg in self.scenes:
            # 每场景取中间帧
            mid = (seg["start"] + seg["end"]) / 2
            frame_name = f"seg{seg['id']:03d}_mid.jpg"
            frame_path = self.frames_dir / frame_name

            if frame_path.exists():
                continue  # 已存在，跳过

            subprocess.run([
                FFMPEG, "-ss", str(mid), "-i", str(self.video_path),
                "-vframes", "1", "-q:v", "2", "-y", str(frame_path),
            ], capture_output=True)

        frame_count = len(list(self.frames_dir.glob("*.jpg")))
        print(f"  关键帧: {frame_count} 张")

    def _synthesize_scenes(self) -> list:
        """单镜头/无场景切换视频保底：按时长等分合成伪场景，保证有关键帧可分析

        最多 4 段；时长不足 20s 也至少 1 段。
        """
        n = min(4, max(1, int(self.video_duration // 20) or 1))
        step = self.video_duration / n
        scenes = []
        for i in range(n):
            s = round(i * step, 2)
            e = round((i + 1) * step, 2)
            scenes.append({"id": i, "start": s, "end": e, "duration": round(e - s, 2)})
        return scenes

    def _load_scenes(self):
        """加载缓存的场景数据"""
        if self.scenes_path.exists():
            with open(self.scenes_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.scenes = data.get("scenes", [])
            # 按开始时间排序（旧数据可能有多 track，时间戳不连续）
            self.scenes.sort(key=lambda s: s.get("start", 0))
            print(f"  加载 {len(self.scenes)} 个场景")

    # ------------------------------------------------------------------
    # Step 5: VLM 关键帧描述
    # ------------------------------------------------------------------

    def _describe_frames(self):
        """用 qwen3.7-plus 多模态描述关键帧（采样模式）"""
        print(f"\n[Step 5] VLM 关键帧描述 (qwen3.7-plus)...")

        if self.descriptions_path.exists():
            self._load_descriptions()
            return

        # 收集所有关键帧
        all_frame_files = sorted(self.frames_dir.glob("*.jpg"))
        if not all_frame_files:
            print("  ⚠ 没有关键帧文件，跳过 VLM 描述")
            return

        # 采样：最多每 3 帧取 1 帧，保底首尾，减少 API 调用
        MAX_VLM_CALLS = 6
        if len(all_frame_files) <= MAX_VLM_CALLS:
            frame_files = all_frame_files
        else:
            step = max(2, len(all_frame_files) // MAX_VLM_CALLS)
            frame_files = all_frame_files[::step]
            # 确保首尾包含
            if all_frame_files[0] not in frame_files:
                frame_files.insert(0, all_frame_files[0])
            if all_frame_files[-1] not in frame_files:
                frame_files.append(all_frame_files[-1])
            frame_files = list(dict.fromkeys(frame_files))  # 去重保序

        print(f"  待描述: {len(frame_files)} 帧 (从 {len(all_frame_files)} 帧中采样)")

        client = self._get_openai_client()
        self.frame_descriptions = []

        for i, frame_path in enumerate(frame_files):
            # 解析场景 ID
            seg_id = None
            m = re.search(r'seg(\d+)', frame_path.stem)
            if m:
                seg_id = int(m.group(1))

            print(f"  [{i+1}/{len(frame_files)}] {frame_path.name} ...", end=" ", flush=True)

            try:
                # 读取图片并 base64 编码
                with open(frame_path, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode("utf-8")

                result = self._call_vlm(client, img_b64)

                desc = json.loads(result) if isinstance(result, str) else result
                desc["scene_id"] = seg_id
                desc["frame_file"] = frame_path.name
                self.frame_descriptions.append(desc)
                print(f"✓ {desc.get('topic', 'N/A')}")
            except Exception as e:
                print(f"✗ {e}")
                # 失败时给一个占位描述
                self.frame_descriptions.append({
                    "scene_id": seg_id,
                    "frame_file": frame_path.name,
                    "topic": "",
                    "location": "未知",
                    "activity": "未知",
                    "visible_elements": [],
                    "has_text_overlay": False,
                    "is_title_card": False,
                    "_error": str(e),
                })

        # 保存
        with open(self.descriptions_path, "w", encoding="utf-8") as f:
            json.dump(self.frame_descriptions, f, ensure_ascii=False, indent=2)

        print(f"  VLM 描述完成: {len(self.frame_descriptions)} 帧")

    def _call_vlm(self, client, img_b64: str) -> dict:
        """调用 VLM 描述单帧"""
        prompt = """你是一个驾考教学视频分析助手。请仔细观察这张视频关键帧截图，用 JSON 格式返回以下信息：

{
  "topic": "教学主题（如：夜间灯光操作/倒车入库/侧方停车/直角转弯/曲线行驶/坡道定点停车/靠边停车/加减档操作/通过路口/上车准备/超车变道/直线行驶/掉头/模拟灯光/会车/其他）",
  "location": "场景位置（车内驾驶座视角/车外/训练场/考试中心/道路/其他）",
  "activity": "画面活动（教练讲解/学员操作/路况展示/仪表盘特写/步骤演示/其他）",
  "visible_elements": ["可见的关键元素列表，如：文字叠加/路线图/特写镜头/仪表盘/手势示意/图表标注/红圈标记/其他"],
  "has_text_overlay": true或false,
  "is_title_card": true或false,
  "detail": "一句话描述画面内容"
}

只返回 JSON，不要加任何解释文字。"""

        response = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
            max_tokens=500,
            temperature=0.3,
        )

        content = response.choices[0].message.content
        # 尝试提取 JSON（有时模型会加 ```json``` 包裹）
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())

        return {"topic": "", "raw_response": content}

    def _load_descriptions(self):
        """加载缓存的 VLM 结果"""
        if self.descriptions_path.exists():
            with open(self.descriptions_path, "r", encoding="utf-8") as f:
                self.frame_descriptions = json.load(f)
            print(f"  加载 {len(self.frame_descriptions)} 条帧描述")

    # ------------------------------------------------------------------
    # Step 5.5: LLM 内容分析
    # ------------------------------------------------------------------

    def _analyze_content(self):
        """LLM 分析 ASR transcript + VLM 摘要，提取知识点和结构"""
        print(f"\n[Step 5.5] LLM 内容分析 (qwen3.7-plus 文本模式)...")

        if self.analysis_path.exists():
            self._load_analysis()
            return

        from engine.analyzer import ContentAnalyzer

        # 构建 VLM 摘要
        topics = list(set(
            fd.get("topic", "") for fd in self.frame_descriptions
            if fd.get("topic")
        ))
        vlm_summary = {"topics": topics}

        # 获取完整 transcript
        full_transcript = " ".join(
            s.get("text", "") for s in self.asr_segments
        )
        if not full_transcript:
            print("  ⚠ 没有 transcript，跳过 LLM 分析")
            self.content_analysis = {"knowledge_points": [], "teaching_style": {}}
            return

        analyzer = ContentAnalyzer()
        try:
            self.content_analysis = analyzer.analyze(
                asr_transcript=full_transcript,
                vlm_summary=vlm_summary,
                video_duration=self.video_duration,
            )
            print(f"  提取到 {len(self.content_analysis.get('knowledge_points', []))} 个知识点")

            # 缓存
            with open(self.analysis_path, "w", encoding="utf-8") as f:
                json.dump(self.content_analysis, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  ⚠ LLM 分析失败: {e}，使用规则评分")
            self.content_analysis = {"knowledge_points": [], "teaching_style": {}}

    def _load_analysis(self):
        """加载缓存的 LLM 分析结果"""
        if self.analysis_path.exists():
            with open(self.analysis_path, "r", encoding="utf-8") as f:
                self.content_analysis = json.load(f)
            kp_count = len(self.content_analysis.get("knowledge_points", []))
            print(f"  加载 {kp_count} 个知识点")

    # ------------------------------------------------------------------
    # Step 6: 智能分段合并
    # ------------------------------------------------------------------

    def _merge_segments(self):
        """合并相邻同主题场景为有意义的片段"""
        if not self.scenes:
            print("  ⚠ 没有场景数据，使用整段视频")
            self.merged_segments = [{
                "id": 0,
                "topic": "完整视频",
                "start": 0,
                "end": self.video_duration,
                "duration": self.video_duration,
                "scenes": [],
                "transcript": " ".join(s.get("text", "") for s in self.asr_segments),
                "frame_descriptions": [],
                "score_result": {},
            }]
            return

        # 为每个场景分配 topic（从 VLM 描述中获取）
        for scene in self.scenes:
            scene["topic"] = self._get_scene_topic(scene["id"])
            scene["description"] = self._get_scene_description(scene["id"])

        # 合并策略:
        # 1. 相邻场景 topic 相同 → 合并
        # 2. 短场景 (< 8s) → 合并到相邻更长的场景
        # 3. 目标: 5-8 个片段

        merged = []
        current = None

        for scene in self.scenes:
            if current is None:
                current = self._init_segment(scene)
                continue

            same_topic = (
                current["topic"] == scene["topic"]
                and current["topic"] != ""
                and current["topic"] != "其他"
            )
            scene_is_short = scene["duration"] < 8

            if same_topic or scene_is_short:
                # 合并
                current["end"] = scene["end"]
                current["duration"] = round(current["end"] - current["start"], 2)
                current["scenes"].append(scene["id"])
                if current["topic"] == "" or current["topic"] == "其他":
                    # 尝试从新场景获取更好的 topic
                    if scene.get("topic") and scene["topic"] != "其他":
                        current["topic"] = scene["topic"]
            else:
                # 结束当前段，开始新段
                merged.append(current)
                current = self._init_segment(scene)

        # 最后一个
        if current is not None:
            merged.append(current)

        # 后处理：合并太短的段到相邻段
        merged = self._postprocess_merge(merged)

        print(f"  合并结果: {len(self.scenes)} 场景 → {len(merged)} 片段")
        for m in merged:
            print(f"    [{m['id']}] {m['topic']:12s}  {m['start']:6.1f}s - {m['end']:6.1f}s  ({m['duration']:.1f}s)")

        self.merged_segments = merged

    def _init_segment(self, scene: dict) -> dict:
        """从场景初始化一个片段"""
        seg_id = len(self.merged_segments)  # 基于已合并的计数
        return {
            "id": seg_id,
            "topic": scene.get("topic", ""),
            "start": scene["start"],
            "end": scene["end"],
            "duration": scene["duration"],
            "scenes": [scene["id"]],
            "transcript": self._get_time_range_transcript(scene["start"], scene["end"]),
            "frame_descriptions": [scene.get("description", {})],
        }

    def _get_scene_topic(self, scene_id: int) -> str:
        """从 VLM 描述中获取场景 topic"""
        for desc in self.frame_descriptions:
            if desc.get("scene_id") == scene_id:
                return desc.get("topic", "")
        return ""

    def _get_scene_description(self, scene_id: int) -> dict:
        """获取场景的 VLM 完整描述"""
        for desc in self.frame_descriptions:
            if desc.get("scene_id") == scene_id:
                return desc
        return {}

    def _get_time_range_transcript(self, t_start: float, t_end: float) -> str:
        """获取指定时间范围内的 ASR transcript"""
        texts = []
        for s in self.asr_segments:
            if s["start"] >= t_start and s["end"] <= t_end:
                texts.append(s["text"])
            elif s["start"] <= t_end and s["end"] >= t_start:
                texts.append(s["text"])
        return " ".join(texts)

    def _postprocess_merge(self, segments: list) -> list:
        """后处理：合并过短片段，重新编号"""
        if len(segments) <= 1:
            return segments

        MIN_DURATION = 10  # 最小时长（秒）

        result = []
        i = 0
        while i < len(segments):
            seg = segments[i]
            if seg["duration"] < MIN_DURATION and len(result) > 0:
                # 合并到前一个段
                prev = result[-1]
                prev["end"] = seg["end"]
                prev["duration"] = round(prev["end"] - prev["start"], 2)
                prev["scenes"].extend(seg["scenes"])
                prev["transcript"] += " " + seg["transcript"]
                prev["frame_descriptions"].extend(seg.get("frame_descriptions", []))
                # 保留更明确的 topic
                if prev["topic"] == "" or prev["topic"] == "其他":
                    prev["topic"] = seg["topic"]
            elif seg["duration"] < MIN_DURATION and i + 1 < len(segments):
                # 合并到下一个段
                next_seg = segments[i + 1]
                seg["end"] = next_seg["end"]
                seg["duration"] = round(seg["end"] - seg["start"], 2)
                seg["scenes"].extend(next_seg["scenes"])
                seg["transcript"] += " " + next_seg["transcript"]
                seg["frame_descriptions"].extend(next_seg.get("frame_descriptions", []))
                if seg["topic"] == "" or seg["topic"] == "其他":
                    seg["topic"] = next_seg["topic"]
                result.append(seg)
                i += 2
                continue
            else:
                result.append(seg)
            i += 1

        # 重新编号
        for idx, seg in enumerate(result):
            seg["id"] = idx

        return result

    # ------------------------------------------------------------------
    # Step 7: 评分
    # ------------------------------------------------------------------

    def _score_segments(self):
        """对所有片段评分"""
        if not self.merged_segments:
            return

        scorer = SegmentScorer()
        topics = [s.get("topic", "") for s in self.merged_segments]

        for seg in self.merged_segments:
            score_result = scorer.score(seg, self.video_duration, topics)
            seg["score_result"] = score_result
            print(f"  [{seg['id']}] {seg['topic']:12s}  "
                  f"得分: {score_result['score']:.2f}  "
                  f"{score_result['recommendation']}  "
                  f"抖:{score_result['platform_suitability']['douyin']} "
                  f"B:{score_result['platform_suitability']['bilibili']} "
                  f"红:{score_result['platform_suitability']['xiaohongshu']}")

    # ------------------------------------------------------------------
    # 保存 & 打印
    # ------------------------------------------------------------------

    def _save_segments(self):
        """保存分段结果"""
        output = {
            "video_path": str(self.video_path),
            "video_duration": self.video_duration,
            "segments": self.merged_segments,
            "total": len(self.merged_segments),
        }
        with open(self.segments_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n  分段结果已保存: {self.segments_path}")

    def print_segments(self, segments: Optional[list] = None):
        """打印分段预览（供用户确认）"""
        segs = segments or self.merged_segments
        if not segs:
            print("没有分段数据")
            return

        print(f"\n{'='*70}")
        print(f"  智能切片预览 — 共 {len(segs)} 段")
        print(f"{'='*70}")

        for seg in segs:
            score = seg.get("score_result", {})
            print(f"\n  ┌─ 片段 {seg['id']} ─────────────────────────────────┐")
            print(f"  │ 主题: {seg.get('topic', '未识别')}")
            print(f"  │ 时间: {seg['start']:.1f}s - {seg['end']:.1f}s ({seg['duration']:.1f}s)")
            print(f"  │ 评分: {score.get('score', 0):.2f} — {score.get('recommendation', '')}")
            if score.get("scores_detail"):
                d = score["scores_detail"]
                print(f"  │   关键词:{d['keywords']:.2f} 知识库:{d['knowledge_match']:.2f} "
                      f"时长:{d['duration_ratio']:.2f} 画面:{d['visual_emphasis']:.2f} "
                      f"重复:{d['repetition']:.2f}")
            suit = score.get("platform_suitability", {})
            if suit:
                print(f"  │ 平台: 抖音={suit.get('douyin','')} B站={suit.get('bilibili','')} 小红书={suit.get('xiaohongshu','')}")
            # 显示前 80 字 transcript
            ts = seg.get("transcript", "")[:80]
            if ts:
                print(f"  │ 内容: {ts}...")
            print(f"  └{'─'*50}┘")

        print(f"\n  💡 请确认分段结果，然后运行导出: pipeline.export_all()")

    # ------------------------------------------------------------------
    # 辅助
    # ------------------------------------------------------------------

    def _get_openai_client(self):
        """懒加载 OpenAI 客户端（DashScope 兼容模式）"""
        if self._openai_client is None:
            if not DASHSCOPE_API_KEY:
                raise RuntimeError(
                    "未设置 DASHSCOPE_API_KEY。请在 .env 文件中配置或设置环境变量。"
                )
            from openai import OpenAI
            self._openai_client = OpenAI(
                api_key=DASHSCOPE_API_KEY,
                base_url=DASHSCOPE_BASE_URL,
            )
        return self._openai_client

    def export_all(self, platforms: Optional[list] = None,
                   asr_segments: Optional[list] = None):
        """一键导出所有片段到多平台"""
        from .exporter import VideoExporter

        if not self.merged_segments:
            raise RuntimeError("还没有分段数据，请先运行 run()")

        exporter = VideoExporter(output_dir=str(self.output_dir))
        results = exporter.export_all(
            self.merged_segments,
            source_video=str(self.video_path),
            platforms=platforms,
            asr_segments=asr_segments or self.asr_segments,
        )
        return results


# ------------------------------------------------------------------
# 快速测试（不调真实 API 的干跑）
# ------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="智能切片管线")
    ap.add_argument("video", nargs="?", help="视频路径")
    ap.add_argument("--skip-audio", action="store_true")
    ap.add_argument("--skip-asr", action="store_true")
    ap.add_argument("--skip-scenes", action="store_true")
    ap.add_argument("--skip-vlm", action="store_true")
    ap.add_argument("--output-dir", default="output")
    ap.add_argument("--work-dir", default="work")
    args = ap.parse_args()

    if not args.video:
        print("用法: python -m engine.pipeline <video_path> [--skip-asr] [--skip-scenes] ...")
        print("示例: python -m engine.pipeline input/video.mp4")
        sys.exit(1)

    p = Pipeline(args.video, output_dir=args.output_dir, work_dir=args.work_dir)
    segments = p.run(
        skip_audio=args.skip_audio,
        skip_asr=args.skip_asr,
        skip_scenes=args.skip_scenes,
        skip_vlm=args.skip_vlm,
    )
    p.print_segments(segments)
