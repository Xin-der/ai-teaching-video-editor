"""
Web 预览界面 — Flask 本地服务
提供片段预览、平台选择、一键导出、文案编辑功能
"""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

# Fix Unicode on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from flask import Flask, jsonify, render_template, request, send_file, url_for

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent
WORK_DIR = ROOT / "work"
OUTPUT_DIR = ROOT / "output"
INPUT_DIR = ROOT / "input"

# ffmpeg 路径
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")

app = Flask(__name__)

# 导出任务状态
_export_status = {"running": False, "progress": "", "results": [], "error": None}

# 内容优化任务状态
_optimize_status = {"running": False, "progress": "", "plan": None, "error": None, "markdown_path": None}

# 缓存视频信息
_video_info_cache = None


# ---------------------------------------------------------------------------
# 页面路由
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    """主页面：内容优化工具"""
    return render_template("optimize.html")


# ---------------------------------------------------------------------------
# API: 片段数据
# ---------------------------------------------------------------------------

@app.route("/api/segments")
def api_segments():
    """返回当前分段结果"""
    segments_path = WORK_DIR / "segments.json"
    if not segments_path.exists():
        return jsonify({"error": "没有分段数据，请先运行管线"}), 404

    with open(segments_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", [])
    # 为每个片段添加缩略图路径
    for seg in segments:
        seg["thumbnail"] = f"/api/thumbnail/{seg['id']}"
        seg["preview_url"] = f"/api/preview/{seg['id']}"

    return jsonify({
        "video_duration": data.get("video_duration", 0),
        "video_path": data.get("video_path", ""),
        "total": len(segments),
        "segments": segments,
    })


# ---------------------------------------------------------------------------
# API: 视频信息
# ---------------------------------------------------------------------------

@app.route("/api/video-info")
def api_video_info():
    """返回源视频信息"""
    global _video_info_cache
    if _video_info_cache:
        return jsonify(_video_info_cache)

    # 查找 segments.json 中的 video_path
    segments_path = WORK_DIR / "segments.json"
    video_path = None
    if segments_path.exists():
        with open(segments_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            video_path = data.get("video_path")

    if not video_path or not os.path.exists(video_path):
        # 尝试找 input/ 下的任意视频
        for ext in ("*.MOV", "*.mp4", "*.mkv", "*.avi"):
            for f in INPUT_DIR.glob(ext):
                video_path = str(f)
                break
            if video_path:
                break

    if not video_path:
        return jsonify({"error": "找不到源视频"}), 404

    # 探测视频信息
    try:
        result = subprocess.run(
            [FFPROBE, "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", video_path],
            capture_output=True, text=True, check=True
        )
        info = json.loads(result.stdout)
        fmt = info.get("format", {})
        duration = float(fmt.get("duration", 0))
        size_mb = os.path.getsize(video_path) / 1024 / 1024

        v_stream = None
        for s in info.get("streams", []):
            if s.get("codec_type") == "video":
                v_stream = s
                break

        _video_info_cache = {
            "path": video_path,
            "filename": Path(video_path).name,
            "duration": duration,
            "duration_str": f"{int(duration//60)}分{int(duration%60)}秒",
            "width": v_stream.get("width", 0) if v_stream else 0,
            "height": v_stream.get("height", 0) if v_stream else 0,
            "codec": v_stream.get("codec_name", "") if v_stream else "",
            "size_mb": round(size_mb, 1),
        }
        return jsonify(_video_info_cache)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# API: 缩略图（从源视频抽帧）
# ---------------------------------------------------------------------------

@app.route("/api/thumbnail/<int:seg_id>")
def api_thumbnail(seg_id: int):
    """为指定片段生成缩略图"""
    segments_path = WORK_DIR / "segments.json"
    if not segments_path.exists():
        return "", 404

    with open(segments_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", [])
    seg = next((s for s in segments if s["id"] == seg_id), None)
    if not seg:
        return "", 404

    video_path = data.get("video_path", "")
    if not video_path or not os.path.exists(video_path):
        return "", 404

    # 取片段中间帧
    mid = (seg["start"] + seg["end"]) / 2
    thumb_dir = WORK_DIR / "thumbnails"
    thumb_dir.mkdir(exist_ok=True)
    thumb_path = thumb_dir / f"seg_{seg_id:02d}.jpg"

    if not thumb_path.exists():
        try:
            subprocess.run([
                FFMPEG, "-ss", str(mid), "-i", video_path,
                "-vframes", "1", "-q:v", "3", "-y",
                str(thumb_path),
            ], capture_output=True, check=True, timeout=15)
        except Exception:
            return "", 500

    return send_file(str(thumb_path), mimetype="image/jpeg")


# ---------------------------------------------------------------------------
# API: HTML5 视频预览片段
# ---------------------------------------------------------------------------

@app.route("/api/preview/<int:seg_id>")
def api_preview(seg_id: int):
    """为指定片段生成预览视频（低分辨率 H.264）"""
    segments_path = WORK_DIR / "segments.json"
    if not segments_path.exists():
        return "", 404

    with open(segments_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    segments = data.get("segments", [])
    seg = next((s for s in segments if s["id"] == seg_id), None)
    if not seg:
        return "", 404

    video_path = data.get("video_path", "")
    if not video_path or not os.path.exists(video_path):
        return "", 404

    preview_dir = WORK_DIR / "previews"
    preview_dir.mkdir(exist_ok=True)
    preview_path = preview_dir / f"seg_{seg_id:02d}.mp4"

    if not preview_path.exists():
        try:
            subprocess.run([
                FFMPEG, "-ss", str(seg["start"]),
                "-t", str(seg["duration"]),
                "-i", video_path,
                "-vf", "scale=640:-1",
                "-c:v", "libx264", "-preset", "ultrafast",
                "-crf", "28", "-c:a", "aac", "-b:a", "64k",
                "-y", str(preview_path),
            ], capture_output=True, check=True, timeout=60)
        except Exception:
            return "", 500

    return send_file(str(preview_path), mimetype="video/mp4")


# ---------------------------------------------------------------------------
# API: 导出操作
# ---------------------------------------------------------------------------

@app.route("/api/export", methods=["POST"])
def api_export():
    """触发导出"""
    global _export_status
    if _export_status["running"]:
        return jsonify({"error": "导出正在进行中"}), 409

    req = request.get_json() or {}
    segment_ids = req.get("segment_ids")  # None = all
    platforms = req.get("platforms", ["douyin", "bilibili", "xiaohongshu"])

    _export_status = {
        "running": True,
        "progress": "准备导出...",
        "results": [],
        "error": None,
    }

    # 在后台线程运行导出
    thread = threading.Thread(
        target=_run_export,
        args=(segment_ids, platforms),
        daemon=True,
    )
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/export/status")
def api_export_status():
    """查询导出状态"""
    return jsonify(_export_status)


def _run_export(segment_ids, platforms):
    """后台导出线程"""
    global _export_status
    try:
        # 添加 engine 到 path
        engine_path = str(ROOT)
        if engine_path not in sys.path:
            sys.path.insert(0, engine_path)

        from engine.pipeline import Pipeline
        from engine.exporter import VideoExporter

        segments_path = WORK_DIR / "segments.json"
        with open(segments_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        all_segments = data.get("segments", [])
        video_path = data.get("video_path", "")

        # 过滤片段
        if segment_ids:
            segments = [s for s in all_segments if s["id"] in segment_ids]
        else:
            segments = all_segments

        if not segments:
            _export_status["error"] = "没有选中任何片段"
            _export_status["running"] = False
            return

        _export_status["progress"] = f"开始导出 {len(segments)} 个片段..."

        exporter = VideoExporter(output_dir=str(OUTPUT_DIR))
        results = []
        total = len(segments) * len(platforms)
        done = 0

        for seg in segments:
            for plat in platforms:
                _export_status["progress"] = (
                    f"导出 [{plat}] {seg.get('topic', '无主题')} "
                    f"({done+1}/{total})"
                )
                try:
                    result = exporter.export(
                        seg, video_path, plat,
                        asr_segments=[],
                    )
                    results.append(result)
                except Exception as e:
                    results.append({
                        "output_path": "",
                        "platform": plat,
                        "segment_id": seg["id"],
                        "error": str(e),
                    })
                done += 1

        _export_status["results"] = results
        _export_status["progress"] = f"导出完成! 共 {len(results)} 个视频"
        _export_status["running"] = False

    except Exception as e:
        _export_status["error"] = str(e)
        _export_status["running"] = False


# ---------------------------------------------------------------------------
# API: 内容优化
# ---------------------------------------------------------------------------

@app.route("/api/optimize", methods=["POST"])
def api_optimize():
    """触发内容优化：上传视频(multipart) 或 粘贴文字(JSON)"""
    global _optimize_status
    if _optimize_status["running"]:
        return jsonify({"error": "正在生成中，请稍候"}), 409

    payload = {}
    if "video" in request.files and request.files["video"].filename:
        f = request.files["video"]
        upload_dir = WORK_DIR / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        save_path = str(upload_dir / Path(f.filename).name)
        f.save(save_path)
        payload = {
            "video_path": save_path,
            "city": (request.form.get("city") or "").strip(),
            "platform": (request.form.get("platform") or "douyin").strip(),
        }
    else:
        data = request.get_json(silent=True) or {}
        payload = {
            "text": (data.get("text") or "").strip(),
            "city": (data.get("city") or "").strip(),
            "platform": (data.get("platform") or "douyin").strip(),
        }
        if not payload["text"]:
            return jsonify({"error": "请上传视频或粘贴文字"}), 400

    _optimize_status = {"running": True, "progress": "准备生成...", "plan": None, "error": None, "markdown_path": None}
    threading.Thread(target=_run_optimize, args=(payload,), daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/optimize/status")
def api_optimize_status():
    """查询内容优化状态"""
    return jsonify(_optimize_status)


def _run_optimize(payload):
    """后台线程：调用 advisor 生成方案 + 写 markdown"""
    global _optimize_status
    try:
        engine_path = str(ROOT)
        if engine_path not in sys.path:
            sys.path.insert(0, engine_path)

        from engine.advisor import ContentAdvisor, write_plan_markdown

        _optimize_status["progress"] = "分析内容中..."
        advisor = ContentAdvisor(work_dir=str(WORK_DIR))
        plan = advisor.build_plan(
            video_path=payload.get("video_path"),
            text=payload.get("text"),
            city=payload.get("city", ""),
            platform=payload.get("platform", "douyin"),
        )

        if plan.get("error"):
            _optimize_status["error"] = plan["error"]
            _optimize_status["running"] = False
            return

        _optimize_status["plan"] = plan
        out_dir = OUTPUT_DIR / "optimize"
        out_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        md_path = str(out_dir / f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
        _optimize_status["markdown_path"] = write_plan_markdown(plan, md_path)
        _optimize_status["progress"] = "完成"
        _optimize_status["running"] = False
    except Exception as e:
        _optimize_status["error"] = str(e)
        _optimize_status["running"] = False


# ---------------------------------------------------------------------------
# API: 文案
# ---------------------------------------------------------------------------

@app.route("/api/copy/<path:rel_path>")
def api_copy(rel_path: str):
    """获取生成的文案内容"""
    copy_path = OUTPUT_DIR / rel_path
    if not copy_path.exists():
        return jsonify({"error": "文案不存在"}), 404

    with open(copy_path, "r", encoding="utf-8") as f:
        content = f.read()

    return jsonify({"path": str(copy_path), "content": content})


@app.route("/api/copy", methods=["POST"])
def api_save_copy():
    """保存编辑后的文案"""
    req = request.get_json() or {}
    path_str = req.get("path", "")
    content = req.get("content", "")

    if not path_str:
        return jsonify({"error": "缺少路径"}), 400

    copy_path = Path(path_str)
    # 安全检查：确保在 output 目录下
    try:
        copy_path.resolve().relative_to(OUTPUT_DIR.resolve())
    except ValueError:
        return jsonify({"error": "路径不安全"}), 403

    copy_path.parent.mkdir(parents=True, exist_ok=True)
    with open(copy_path, "w", encoding="utf-8") as f:
        f.write(content)

    return jsonify({"status": "saved"})


# ---------------------------------------------------------------------------
# API: 列出已导出的文件
# ---------------------------------------------------------------------------

@app.route("/api/exports")
def api_exports():
    """列出已导出的视频和文案"""
    if not OUTPUT_DIR.exists():
        return jsonify({"exports": []})

    exports = []
    for seg_dir in sorted(OUTPUT_DIR.iterdir()):
        if not seg_dir.is_dir() or seg_dir.name.startswith("_"):
            continue

        seg_files = {}
        for f in seg_dir.iterdir():
            if f.suffix == ".mp4":
                platform = f.stem
                seg_files[platform] = {
                    "path": str(f.relative_to(OUTPUT_DIR)),
                    "size_mb": round(f.stat().st_size / 1024 / 1024, 1),
                    "url": f"/output/{f.relative_to(OUTPUT_DIR)}",
                }
            elif f.suffix == ".md":
                seg_files["copy"] = {
                    "path": str(f.relative_to(OUTPUT_DIR)),
                    "url": f"/api/copy/{f.relative_to(OUTPUT_DIR)}",
                }

        if seg_files:
            exports.append({
                "dir": seg_dir.name,
                "files": seg_files,
            })

    return jsonify({"exports": exports})


# ---------------------------------------------------------------------------
# 静态文件：导出的视频/图片
# ---------------------------------------------------------------------------

@app.route("/output/<path:rel_path>")
def serve_output(rel_path: str):
    """提供导出文件的静态服务"""
    file_path = OUTPUT_DIR / rel_path
    if not file_path.exists():
        return "", 404

    # 根据扩展名设置 MIME
    ext = file_path.suffix.lower()
    mimetypes = {
        ".mp4": "video/mp4",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".md": "text/markdown",
    }
    return send_file(str(file_path), mimetype=mimetypes.get(ext, "application/octet-stream"))


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------

def main():
    import argparse
    ap = argparse.ArgumentParser(description="启动 Web 预览界面")
    ap.add_argument("--host", default="127.0.0.1", help="监听地址 (默认: 127.0.0.1)")
    ap.add_argument("--port", type=int, default=5000, help="监听端口 (默认: 5000)")
    ap.add_argument("--debug", action="store_true", help="调试模式")
    args = ap.parse_args()

    print(f"""
╔══════════════════════════════════════════╗
║   🎬 多平台智能切片工具 — Web 预览界面  ║
║                                         ║
║   🌐 http://{args.host}:{args.port}             ║
║   📁 输出目录: {OUTPUT_DIR}
║   按 Ctrl+C 停止服务                     ║
╚══════════════════════════════════════════╝
""")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
