"""探索剪映 draft_content.json 的结构"""
import json, os, sys

DRAFT_PATH = "ref/draft_content.json.dec.json"
MATERIALS_DIR = "ref/materials"

with open(DRAFT_PATH, encoding="utf-8") as f:
    draft = json.load(f)

print("=" * 60)
print("1. 顶层结构")
print("=" * 60)
for k, v in draft.items():
    if isinstance(v, (list, dict)):
        print(f"  {k}: {type(v).__name__}, len={len(v)}")
    elif isinstance(v, str) and len(v) > 80:
        print(f"  {k}: str[{len(v)}]")
    else:
        print(f"  {k}: {repr(v)}")

# 轨道
if "tracks" in draft:
    print(f"\n{'='*60}")
    print(f"2. 轨道分析 ({len(draft['tracks'])} 条)")
    print("=" * 60)
    for i, t in enumerate(draft["tracks"]):
        ttype = t.get("type", "?")
        clips = t.get("clips", t.get("segments", []))
        print(f"\n  轨道{i} [{ttype}]: {len(clips)} clips")
        if not clips:
            continue
        c0 = clips[0]
        print(f"    首个clip的keys: {list(c0.keys())[:15]}")
        # 看关键信息
        for key in ["start", "end", "duration", "source", "type", "channel", "material_type"]:
            if key in c0:
                print(f"    {key} = {c0[key]}")

# 素材
if "materials" in draft:
    print(f"\n{'='*60}")
    print(f"3. 素材引用 ({len(draft['materials'])} 个)")
    print("=" * 60)
    mats = draft["materials"]
    if isinstance(mats, dict):
        for mid, m in list(mats.items())[:5]:
            print(f"  {mid}: {json.dumps(m, ensure_ascii=False)[:120]}")
    elif isinstance(mats, list):
        for m in mats[:5]:
            print(f"  {json.dumps(m, ensure_ascii=False)[:120]}")

# PNG 素材
print(f"\n{'='*60}")
print("4. 本地素材文件")
print("=" * 60)
from PIL import Image
for f in sorted(os.listdir(MATERIALS_DIR)):
    if f.endswith((".png", ".jpg", ".jpeg")):
        img = Image.open(os.path.join(MATERIALS_DIR, f))
        alpha_info = ""
        if img.mode == "RGBA":
            a = img.split()[-1]
            alpha_info = f", alpha({a.getextrema()[0]}~{a.getextrema()[1]})"
        print(f"  {f}")
        print(f"    size={img.size}, mode={img.mode}{alpha_info}")

print(f"\n{'='*60}")
print("5. 视频信息")
print("=" * 60)
video_file = "ref/SGOI6715.MOV"
if os.path.exists(video_file):
    size_gb = os.path.getsize(video_file) / 1024 / 1024 / 1024
    print(f"  文件: {video_file}")
    print(f"  大小: {size_gb:.2f} GB")
    # ffprobe 获取时长
    import subprocess
    ffprobe = r"D:\tools\ffmpeg\ffmpeg-8.1.2-full_build\bin\ffprobe.exe"
    cmd = [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", video_file]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        info = json.loads(result.stdout)
        fmt = info.get("format", {})
        duration = float(fmt.get("duration", 0))
        mins = int(duration // 60)
        secs = int(duration % 60)
        print(f"  时长: {mins}分{secs}秒")
        print(f"  格式: {fmt.get('format_name', '?')}")
    except Exception as e:
        print(f"  ffprobe 失败: {e}")
