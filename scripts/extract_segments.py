"""从工程文件提取分段 + 抽关键帧"""
import json, os, subprocess

FFMPEG = r"D:\tools\ffmpeg\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
VIDEO = "ref/SGOI6715.MOV"
os.makedirs("work/frames", exist_ok=True)

# 1. 从工程文件提取分段
with open("ref/draft_content.json.dec.json", encoding="utf-8") as f:
    draft = json.load(f)

# 主视频轨
video_tracks = [t for t in draft["tracks"] if t["type"] == "video"]
all_segments = []
seg_id = 0

for ti, track in enumerate(video_tracks):
    for si, seg in enumerate(track.get("segments", [])):
        tr = seg.get("target_timerange", {})
        s = tr.get("start", 0) / 1_000_000
        d = tr.get("duration", 0) / 1_000_000
        all_segments.append({
            "id": seg_id,
            "track": ti,
            "start": round(s, 2),
            "end": round(s + d, 2),
            "duration": round(d, 2)
        })
        seg_id += 1

print(f"主视频轨: {len(video_tracks)} 条, 共 {len(all_segments)} 个分段")
for seg in all_segments:
    print(f"  seg{seg['id']} [track{seg['track']}]: {seg['start']:.1f}s - {seg['end']:.1f}s ({seg['duration']:.1f}s)")

with open("work/scenes.json", "w", encoding="utf-8") as f:
    json.dump({"scenes": all_segments, "total": len(all_segments),
               "source": "draft_content.json"}, f, ensure_ascii=False, indent=2)

# 2. 抽关键帧 (每段起止双帧)
print(f"\n抽关键帧 ({len(all_segments)} 段)...")
for seg in all_segments:
    mid = (seg["start"] + seg["end"]) / 2
    for label, t in [("start", seg["start"]), ("mid", mid),
                      ("end", max(seg["end"] - 1, seg["start"] + 0.5))]:
        out = f"work/frames/seg{seg['id']:03d}_{label}.jpg"
        if not os.path.exists(out):
            subprocess.run([FFMPEG, "-ss", str(t), "-i", VIDEO, "-vframes", "1",
                           "-q:v", "3", "-y", out], capture_output=True)

frame_count = len(os.listdir("work/frames"))
print(f"抽取完成: {frame_count} 张 -> work/frames/")
