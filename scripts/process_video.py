"""处理新视频：读 input/ → ASR + VLM + 匹配 + 渲染 → output/成片.mp4

和第一段"学风格"完全不同:
  - 不需要 draft_content.json（用 PySceneDetect 自动分镜）
  - 不需要 style_params_raw.json（风格规则已经有了）
  - 不需要翻译风格（style_labels.json 已就绪）
  - 视频源 = input/video.mp4，绝不 fallback 到 ref/
"""
import json, os, sys, time, base64, subprocess, argparse, hashlib

import numpy as np

FFMPEG = r"D:\tools\ffmpeg\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
FFPROBE = r"D:\tools\ffmpeg\ffmpeg-8.1.2-full_build\bin\ffprobe.exe"

# ── 参数 ──
parser = argparse.ArgumentParser(description="AI 教学视频剪辑 - 处理新视频")
parser.add_argument("--input", default="input/video.mp4", help="输入视频路径")
parser.add_argument("--route-map", default=None, help="路线图路径（可选）")
parser.add_argument("--style", default="style_labels.json", help="风格规则文件")
parser.add_argument("--output", default="output/成片.mp4", help="输出路径")
parser.add_argument("--skip-asr", action="store_true", help="跳过 ASR")
parser.add_argument("--skip-vlm", action="store_true", help="跳过 VLM")
parser.add_argument("--max-segments", type=int, default=30, help="最多分段数")
parser.add_argument("--resolution", default="1080p", help="渲染分辨率 (1080p/720p)")
args = parser.parse_args()

INPUT_VIDEO = args.input
ROUTE_MAP = args.route_map or "input/route_map.png"
STYLE_FILE = args.style
OUTPUT_VIDEO = args.output

# 为每个视频生成唯一的工作目录标识
VIDEO_HASH = hashlib.md5(open(INPUT_VIDEO, "rb").read(1024*1024)).hexdigest()[:8]
WORK_DIR = f"work/run_{VIDEO_HASH}"
os.makedirs(WORK_DIR, exist_ok=True)
os.makedirs("output", exist_ok=True)

AUDIO_FILE = os.path.join(WORK_DIR, "audio.wav")
ASR_FILE = os.path.join(WORK_DIR, "asr_result.json")
SCENES_FILE = os.path.join(WORK_DIR, "scenes.json")
FRAMES_DIR = os.path.join(WORK_DIR, "frames")
FRAME_DESC_FILE = os.path.join(WORK_DIR, "frame_descriptions.json")
CONTENT_MAP_FILE = os.path.join(WORK_DIR, "content_map.json")
EDIT_OPS_FILE = os.path.join(WORK_DIR, "edit_ops.json")

# ── API 配置 ──
from dotenv import load_dotenv
load_dotenv()
import dashscope
API_KEY = os.getenv("DASHSCOPE_API_KEY")
MODEL = os.getenv("MODEL", "qwen3.7-plus")

print("=" * 55)
print("  AI 教学视频剪辑 · 处理新视频")
print("=" * 55)
print(f"  输入: {INPUT_VIDEO}")
print(f"  路线图: {ROUTE_MAP if os.path.exists(ROUTE_MAP) else '(无)'}")
print(f"  风格: {STYLE_FILE}")
print(f"  输出: {OUTPUT_VIDEO}")
print(f"  工作目录: {WORK_DIR}")
print()


# ═══════════════════════════════════════════════
# Step 1: 提取音频
# ═══════════════════════════════════════════════
def step1_extract_audio():
    if os.path.exists(AUDIO_FILE):
        size_mb = os.path.getsize(AUDIO_FILE) / 1024 / 1024
        print(f"[Step 1] 音频已存在 ({size_mb:.1f}MB)，跳过")
        return True

    print("[Step 1] 提取音频...")
    result = subprocess.run(
        [FFMPEG, "-i", INPUT_VIDEO, "-vn", "-acodec", "pcm_s16le",
         "-ar", "16000", "-ac", "1", "-y", AUDIO_FILE],
        capture_output=True
    )
    if result.returncode != 0:
        print(f"  失败: {result.stderr.decode('gbk', errors='ignore')[:200]}")
        return False
    size_mb = os.path.getsize(AUDIO_FILE) / 1024 / 1024
    print(f"  完成 ({size_mb:.1f}MB, 16kHz mono)")
    return True


# ═══════════════════════════════════════════════
# Step 2: ASR 语音识别
# ═══════════════════════════════════════════════
def step2_asr():
    if args.skip_asr:
        print("[Step 2] ASR 已跳过 (--skip-asr)")
        return os.path.exists(ASR_FILE)
    if os.path.exists(ASR_FILE):
        with open(ASR_FILE, encoding="utf-8") as f:
            data = json.load(f)
        print(f"[Step 2] ASR 已存在 ({data.get('total', 0)} 句)，跳过")
        return True

    print("[Step 2] ASR 语音识别（FunASR Paraformer）...")
    from funasr import AutoModel
    import soundfile as sf

    model = AutoModel(model="paraformer-zh", model_revision="v2.0.4")
    audio, sr = sf.read(AUDIO_FILE)
    if len(audio.shape) > 1:
        audio = audio.mean(axis=1)

    duration = len(audio) / sr
    print(f"  时长: {duration:.0f}s, 模型加载完成")

    # 60秒分块处理
    CHUNK = 60 * sr
    all_segs = []
    offset = 0.0

    for i in range(0, len(audio), CHUNK):
        chunk = audio[i:i+CHUNK]
        chunk_dur = len(chunk) / sr
        rms = np.sqrt(np.mean(chunk**2))

        if rms < 0.01:
            offset += chunk_dur
            continue

        temp = os.path.join(WORK_DIR, f"_chunk_{i}.wav")
        sf.write(temp, chunk.astype(np.float32), sr)

        try:
            result = model.generate(input=temp)
            if result and result[0].get("text"):
                text = result[0]["text"]
                ts = result[0].get("timestamp", [])
                words = text.split()
                # 按自然停顿分组
                buf, buf_start, buf_end = [], None, None
                for wi, t in enumerate(ts):
                    if wi >= len(words):
                        break
                    w = words[wi]
                    ts_s = t[0] / 1000.0
                    ts_e = t[1] / 1000.0
                    if buf_start is None:
                        buf_start = ts_s
                    buf.append(w)
                    buf_end = ts_e
                    if len(buf) >= 15 or w in "啊呢吧吗的了":
                        all_segs.append({
                            "start": round(offset + buf_start, 2),
                            "end": round(offset + buf_end, 2),
                            "text": "".join(buf)
                        })
                        buf, buf_start = [], None
                if buf:
                    all_segs.append({
                        "start": round(offset + buf_start, 2),
                        "end": round(offset + buf_end, 2),
                        "text": "".join(buf)
                    })
        except Exception as e:
            print(f"  chunk {i} 失败: {e}")
        finally:
            if os.path.exists(temp):
                os.remove(temp)
        offset += chunk_dur

    with open(ASR_FILE, "w", encoding="utf-8") as f:
        json.dump({"segments": all_segs, "total": len(all_segs)}, f, ensure_ascii=False, indent=2)
    print(f"  完成: {len(all_segs)} 句")
    return True


# ═══════════════════════════════════════════════
# Step 3: 场景检测（PySceneDetect 自动分镜）
# ═══════════════════════════════════════════════
def step3_scene_detect():
    if os.path.exists(SCENES_FILE):
        with open(SCENES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        print(f"[Step 3] 场景已存在 ({data.get('total', 0)} 段)，跳过")
        return True

    print("[Step 3] 场景检测（PySceneDetect）...")
    try:
        from scenedetect import open_video, SceneManager, ContentDetector
        video = open_video(INPUT_VIDEO)
        sm = SceneManager()
        sm.add_detector(ContentDetector(threshold=27.0))
        sm.detect_scenes(video)
        scenes = sm.get_scene_list()
        if not scenes:
            raise ValueError("未检测到场景切换")
    except Exception as e:
        print(f"  PySceneDetect 失败 ({e})，使用固定间隔分段")
        # 回退: 用 ffprobe 获取时长，每 15 秒一段
        result = subprocess.run(
            [FFPROBE, "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", INPUT_VIDEO],
            capture_output=True
        )
        duration = float(result.stdout.decode().strip())
        interval = 15  # 15秒一段
        scenes = []
        t = 0
        seg_id = 0
        while t < duration and seg_id < args.max_segments:
            end = min(t + interval, duration)
            scenes.append((t, end))
            t = end
            seg_id += 1

    seg_list = []
    for i, (start, end) in enumerate(scenes):
        s = start.get_seconds() if hasattr(start, 'get_seconds') else start
        e = end.get_seconds() if hasattr(end, 'get_seconds') else end
        seg_list.append({
            "id": i, "track": 0,
            "start": round(s, 2), "end": round(e, 2),
            "duration": round(e - s, 2)
        })

    with open(SCENES_FILE, "w", encoding="utf-8") as f:
        json.dump({"scenes": seg_list, "total": len(seg_list), "source": "auto"}, f, ensure_ascii=False, indent=2)
    print(f"  完成: {len(seg_list)} 段")
    return True


# ═══════════════════════════════════════════════
# Step 4: 抽关键帧
# ═══════════════════════════════════════════════
def step4_extract_frames():
    os.makedirs(FRAMES_DIR, exist_ok=True)
    existing = len([f for f in os.listdir(FRAMES_DIR) if f.endswith(".jpg")]) if os.path.exists(FRAMES_DIR) else 0

    with open(SCENES_FILE, encoding="utf-8") as f:
        scenes = json.load(f)["scenes"]

    if existing >= len(scenes):
        print(f"[Step 4] 关键帧已存在 ({existing} 张)，跳过")
        return True

    print(f"[Step 4] 抽取关键帧 ({len(scenes)} 段)...")
    for seg in scenes:
        mid = (seg["start"] + seg["end"]) / 2
        for label, t in [("start", seg["start"]), ("mid", mid)]:
            out = os.path.join(FRAMES_DIR, f"seg{seg['id']:03d}_{label}.jpg")
            if not os.path.exists(out):
                subprocess.run(
                    [FFMPEG, "-ss", str(t), "-i", INPUT_VIDEO,
                     "-vframes", "1", "-q:v", "5", "-y", out],
                    capture_output=True
                )
    count = len([f for f in os.listdir(FRAMES_DIR) if f.endswith(".jpg")])
    print(f"  完成: {count} 张 -> {FRAMES_DIR}")
    return True


# ═══════════════════════════════════════════════
# Step 5: VLM 描述关键帧
# ═══════════════════════════════════════════════
PROMPT_VLM = """你是一名驾考教学视频分析员。请分析这张画面，严格输出 JSON:

{"location":"车内|车外道路|考场场地|驾校场地|其他","who_visible":["教练"|"学员"|"无人物"],"activity":"讲解灯光|讲解规则|实操演示|路线介绍|起步操作|停车操作|转向操作|考试模拟|其他","visible_elements":["仪表盘","方向盘","道路标线","文字叠加","图示标注","路线图","交通信号灯","其他"],"text_overlay_content":"画面上的文字内容，没有则为空","camera_angle":"车内前拍|车外前拍|侧面拍摄|其他","lighting":"白天|夜间|黄昏|室内","summary":"一句话描述"}

只输出 JSON，不要其他文字。"""


def describe_frame(img_path):
    """单帧 VLM 描述（只用文本模式，不用 reasoning 加速）"""
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    img_uri = f"data:image/jpeg;base64,{b64}"

    messages = [{"role": "user", "content": [
        {"image": img_uri},
        {"text": PROMPT_VLM}
    ]}]

    for attempt in range(2):
        try:
            resp = dashscope.MultiModalConversation.call(
                model=MODEL, messages=messages, api_key=API_KEY
            )
            if resp.status_code == 200:
                for item in resp.output["choices"][0]["message"]["content"]:
                    if isinstance(item, dict) and "text" in item:
                        text = item["text"].strip()
                        if text.startswith("```"):
                            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
                        return json.loads(text)
            time.sleep(2)
        except json.JSONDecodeError:
            time.sleep(2)
        except Exception as e:
            time.sleep(3)
    return None


def step5_vlm_describe():
    if args.skip_vlm:
        print("[Step 5] VLM 已跳过 (--skip-vlm)")
        return os.path.exists(FRAME_DESC_FILE)
    if os.path.exists(FRAME_DESC_FILE):
        with open(FRAME_DESC_FILE, encoding="utf-8") as f:
            data = json.load(f)
        print(f"[Step 5] VLM 描述已存在 ({data.get('total', 0)} 段)，跳过")
        return True

    with open(SCENES_FILE, encoding="utf-8") as f:
        scenes = json.load(f)["scenes"]

    print(f"[Step 5] VLM 描述关键帧 ({len(scenes)} 段)")
    print(f"  API: {MODEL}, 预估 ~{len(scenes) * 30}s")

    results = []
    for seg in scenes:
        mid_frame = os.path.join(FRAMES_DIR, f"seg{seg['id']:03d}_mid.jpg")
        if not os.path.exists(mid_frame):
            start_frame = os.path.join(FRAMES_DIR, f"seg{seg['id']:03d}_start.jpg")
            if os.path.exists(start_frame):
                mid_frame = start_frame
            else:
                results.append({"segment_id": seg["id"], "error": "no_frame"})
                continue

        t0 = time.time()
        desc = describe_frame(mid_frame)
        elapsed = time.time() - t0

        if desc:
            desc["segment_id"] = seg["id"]
            desc["t_start"] = seg["start"]
            desc["t_end"] = seg["end"]
            results.append(desc)
            print(f"  seg{seg['id']:03d} ({elapsed:.0f}s) {desc.get('summary', '')[:50]}")
        else:
            results.append({"segment_id": seg["id"], "error": "vlm_failed"})
            print(f"  seg{seg['id']:03d} ({elapsed:.0f}s) FAILED")

        # 每段保存
        with open(FRAME_DESC_FILE, "w", encoding="utf-8") as f:
            json.dump({"segments": results, "total": len(results), "model": MODEL}, f, ensure_ascii=False, indent=2)
        time.sleep(0.3)

    success = sum(1 for r in results if "error" not in r)
    print(f"  完成: {success}/{len(results)} 成功")
    return success > 0


# ═══════════════════════════════════════════════
# Step 6: 合并 content_map
# ═══════════════════════════════════════════════
def step6_merge():
    if os.path.exists(CONTENT_MAP_FILE):
        with open(CONTENT_MAP_FILE, encoding="utf-8") as f:
            data = json.load(f)
        print(f"[Step 6] content_map 已存在 ({len(data)} 段)，跳过")
        return True

    print("[Step 6] 合并 ASR + VLM → content_map...")

    scenes = json.load(open(SCENES_FILE, encoding="utf-8"))["scenes"]
    asr_data = json.load(open(ASR_FILE, encoding="utf-8"))
    asr_segs = asr_data.get("segments", [])

    vlm_map = {}
    if os.path.exists(FRAME_DESC_FILE):
        for s in json.load(open(FRAME_DESC_FILE, encoding="utf-8")).get("segments", []):
            if "error" not in s:
                vlm_map[s["segment_id"]] = s

    content_map = []
    for seg in scenes:
        # 找时间范围内的 ASR 句子
        parts = [s for s in asr_segs if s["end"] > seg["start"] and s["start"] < seg["end"]]
        transcript = " ".join([p["text"] for p in parts])

        vlm = vlm_map.get(seg["id"], {})
        labels = []
        loc = vlm.get("location", "")
        act = vlm.get("activity", "")
        if loc:
            labels.append(f"location:{loc}")
        if act:
            labels.append(f"activity:{act}")
        for w in vlm.get("who_visible", []):
            labels.append(f"who:{w}")
        for e in vlm.get("visible_elements", []):
            labels.append(f"element:{e}")

        content_map.append({
            "segment_id": seg["id"], "track": 0,
            "t_start": seg["start"], "t_end": seg["end"],
            "duration": seg["duration"],
            "speaker": "教练", "labels": labels,
            "transcript": transcript,
            "asr_sentence_count": len(parts),
            "summary": vlm.get("summary", ""),
            "location": loc, "activity": act,
            "who_visible": vlm.get("who_visible", []),
            "lighting": vlm.get("lighting", ""),
        })

    with open(CONTENT_MAP_FILE, "w", encoding="utf-8") as f:
        json.dump(content_map, f, ensure_ascii=False, indent=2)
    print(f"  完成: {len(content_map)} 段")
    return True


# ═══════════════════════════════════════════════
# Step 7: 标签匹配
# ═══════════════════════════════════════════════
def step7_match():
    print("[Step 7] 标签匹配...")
    # 直接复用 match_style.py 的核心逻辑
    sys.path.insert(0, "scripts")
    from match_style import load_json as m_load, check_condition

    content_map = json.load(open(CONTENT_MAP_FILE, encoding="utf-8"))
    style_rules = json.load(open(STYLE_FILE, encoding="utf-8"))

    has_route = os.path.exists(ROUTE_MAP)
    has_foot = os.path.exists("input/foot_closeup.mp4") or os.path.exists("input/foot_closeup.jpg")
    has_dash = os.path.exists("input/dashboard_closeup.mp4") or os.path.exists("input/dashboard_closeup.jpg")

    print(f"  路线图: {'有' if has_route else '无'}")
    print(f"  特写素材: 脚部{'有' if has_foot else '无'}, 仪表盘{'有' if has_dash else '无'}")

    edit_ops = []
    stats = {}

    for seg in content_map:
        labels = seg.get("labels", [])
        has_speech = seg.get("asr_sentence_count", 0) > 0

        # 分支选择（互斥）
        branch_rules = sorted(
            [r for r in style_rules if r.get("rule_id", "").startswith("BRANCH_")],
            key=lambda r: r.get("priority", 99)
        )

        ops = []
        for rule in branch_rules:
            cond = rule.get("condition", {})
            if cond and check_condition(cond, labels, has_route, has_speech):
                for a in rule.get("actions", []):
                    ops.append({"op": a["op"], "params": a.get("params", {}),
                                "desc": a.get("description", "")})
                stats[rule["rule_id"]] = stats.get(rule["rule_id"], 0) + 1
                break

        # 通用规则
        for rule in style_rules:
            if rule.get("rule_id", "").startswith("BRANCH_") or rule.get("rule_id") == "DETECT_001":
                continue
            trigger = rule.get("trigger", {})
            if trigger and check_condition(trigger, labels, has_route, has_speech):
                for a in rule.get("actions", []):
                    ops.append({"op": a["op"], "params": a.get("params", {}),
                                "desc": a.get("description", "")})
                stats[rule["rule_id"]] = stats.get(rule["rule_id"], 0) + 1

        if ops:
            edit_ops.append({
                "segment_id": seg["segment_id"], "t_start": seg["t_start"],
                "t_end": seg["t_end"], "duration": seg["duration"],
                "activity": seg.get("activity", ""), "operations": ops
            })

    output = {
        "video_source": INPUT_VIDEO, "route_map": ROUTE_MAP if has_route else None,
        "has_foot_closeup": has_foot, "has_dash_closeup": has_dash,
        "total_segments": len(edit_ops), "segments": edit_ops, "stats": stats
    }
    with open(EDIT_OPS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  完成: {len(edit_ops)} 段有操作")
    for k, v in stats.items():
        print(f"    {k}: {v}")
    return True


# ═══════════════════════════════════════════════
# Step 8: 渲染
# ═══════════════════════════════════════════════
def step8_render():
    print("[Step 8] MoviePy 渲染...")
    from moviepy import VideoFileClip, ImageClip, CompositeVideoClip, TextClip
    from moviepy import concatenate_videoclips
    import cv2

    with open(EDIT_OPS_FILE, encoding="utf-8") as f:
        edit_data = json.load(f)

    video_source = edit_data["video_source"]
    if not os.path.exists(video_source):
        print(f"  ❌ 视频不存在: {video_source}")
        return False

    video = VideoFileClip(video_source)
    print(f"  源: {video.w}x{video.h}, {video.duration:.0f}s")

    # 路线图加载
    route_clip = None
    route_path = edit_data.get("route_map")
    if route_path and os.path.exists(route_path):
        img = cv2.imread(route_path)
        if img is not None:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
            lower_blue = (100, 60, 60)
            upper_blue = (135, 255, 255)
            mask = cv2.inRange(hsv, lower_blue, upper_blue)
            mask_inv = cv2.bitwise_not(mask)
            rgba = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2RGBA)
            rgba[:, :, 3] = mask_inv
            # 缩放到合适大小
            h, w = rgba.shape[:2]
            scale = 350 / w
            rgba_small = cv2.resize(rgba, (int(w*scale), int(h*scale)))
            route_clip = ImageClip(rgba_small, duration=None)
            print(f"  路线图加载: {w}x{h} → {rgba_small.shape[1]}x{rgba_small.shape[0]}")

    # 红点
    dot_size = 12
    dot_img = np.zeros((dot_size, dot_size, 4), dtype=np.uint8)
    cv2.circle(dot_img, (dot_size//2, dot_size//2), dot_size//2-1, (255, 30, 30, 255), -1)

    # 逐段渲染
    rendered = []
    for seg in edit_data["segments"]:
        t_s, t_e = seg["t_start"], seg["t_end"]
        if t_e - t_s < 0.5:
            continue
        try:
            clip = video.subclipped(t_s, t_e)
        except Exception:
            continue

        overlays = [clip]

        for op in seg.get("operations", []):
            op_name = op["op"]
            params = op.get("params", {})

            if op_name == "overlay_route_map" and route_clip is not None:
                rm = route_clip.with_duration(clip.duration)
                rm = rm.with_position((clip.w - rm.w - 10, 10))
                rm = rm.with_opacity(0.9)
                overlays.append(rm)

            elif op_name == "zoom_keyframe":
                s_start = params.get("scale_start", 1.0)
                s_end = params.get("scale_end", 1.12)
                dur = clip.duration
                def zoom_eff(get_frame, t):
                    p = t / dur if dur > 0 else 0
                    eased = 1 - (1-p)**2
                    scale = s_start + (s_end - s_start) * eased
                    f = get_frame(t)
                    h, w = f.shape[:2]
                    nw, nh = int(w*scale), int(h*scale)
                    r = cv2.resize(f, (nw, nh))
                    x1, y1 = (nw-w)//2, (nh-h)//2
                    return r[y1:y1+h, x1:x1+w]
                clip = clip.transform(zoom_eff)
                overlays[0] = clip

            elif op_name == "add_pip_if_available":
                for src_key in ["foot_closeup", "dashboard_closeup"]:
                    src = params.get(src_key, {}).get("source", "")
                    pos_name = params.get(src_key, {}).get("position", "左上角")
                    if os.path.exists(src):
                        try:
                            pip = (VideoFileClip(src) if src.endswith(".mp4")
                                   else ImageClip(src, duration=clip.duration))
                            pip = pip.resized(width=int(clip.w * 0.25))
                            pip = pip.with_duration(clip.duration)
                            if pos_name == "左上角":
                                pip = pip.with_position((10, 10))
                            elif pos_name == "左下角":
                                pip = pip.with_position((10, clip.h - pip.h - 10))
                            pip = pip.with_opacity(0.9)
                            overlays.append(pip)
                        except Exception:
                            pass

            elif op_name == "burn_subtitles":
                transcript = seg.get("transcript", "")
                if transcript:
                    try:
                        txt = TextClip(
                            text=transcript[:80], font_size=28, color="white",
                            stroke_color="black", stroke_width=5, font="Arial",
                            duration=clip.duration
                        )
                        txt = txt.with_position(("center", clip.h - txt.h - 30))
                        overlays.append(txt)
                    except Exception:
                        pass

        if len(overlays) > 1:
            result = CompositeVideoClip(overlays, size=(clip.w, clip.h))
        else:
            result = clip
        rendered.append(result)

    if not rendered:
        print("  ❌ 无渲染段")
        video.close()
        return False

    print(f"  拼接 {len(rendered)} 段...")
    final = concatenate_videoclips(rendered)

    # 输出分辨率
    if args.resolution == "720p" and final.h > 720:
        final = final.resized(height=720)

    print(f"  输出: {OUTPUT_VIDEO} ({final.w}x{final.h})")
    final.write_videofile(
        OUTPUT_VIDEO, codec="libx264", audio_codec="aac",
        fps=min(video.fps, 30), preset="fast", threads=2,
        logger=None
    )

    final.close(); video.close()
    if route_clip: route_clip.close()
    for r in rendered: r.close()

    size_mb = os.path.getsize(OUTPUT_VIDEO) / 1024 / 1024
    print(f"  ✅ 完成: {size_mb:.1f}MB")
    return True


# ═══════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════
def main():
    if not os.path.exists(INPUT_VIDEO):
        print(f"❌ 视频不存在: {INPUT_VIDEO}")
        print("  请将视频放到 input/video.mp4")
        sys.exit(1)

    t_total = time.time()

    steps = [
        ("提取音频", step1_extract_audio),
        ("ASR 识别", step2_asr),
        ("场景检测", step3_scene_detect),
        ("抽关键帧", step4_extract_frames),
        ("VLM 描述", step5_vlm_describe),
        ("合并数据", step6_merge),
        ("标签匹配", step7_match),
        ("渲染出片", step8_render),
    ]

    for name, func in steps:
        t0 = time.time()
        ok = func()
        elapsed = time.time() - t0
        if not ok:
            print(f"\n❌ [{name}] 失败 ({elapsed:.0f}s)")
            sys.exit(1)
        print(f"    ⏱ {elapsed:.0f}s\n")

    total = time.time() - t_total
    print(f"✅ 全部完成! 总耗时 {total/60:.1f} 分钟")
    print(f"   成品: {OUTPUT_VIDEO}")


if __name__ == "__main__":
    main()
