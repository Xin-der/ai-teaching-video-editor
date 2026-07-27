"""场景检测 + 抽关键帧"""
import json, os, subprocess

VIDEO = "ref/SGOI6715.MOV"
FFMPEG = r"D:\tools\ffmpeg\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
FFPROBE = r"D:\tools\ffmpeg\ffmpeg-8.1.2-full_build\bin\ffprobe.exe"
os.makedirs("work/frames", exist_ok=True)

# Step 1: 场景检测
print("[1/3] 场景检测...")
from scenedetect import open_video, SceneManager, ContentDetector

video = open_video(VIDEO)
sm = SceneManager()
sm.add_detector(ContentDetector(threshold=30))
sm.detect_scenes(video)
scenes = sm.get_scene_list()

segments = []
for i, (start, end) in enumerate(scenes):
    s = start.get_seconds()
    e = end.get_seconds()
    segments.append({"id": i, "start": round(s, 2), "end": round(e, 2), "duration": round(e - s, 2)})

print(f"  检测到 {len(segments)} 个场景")
with open("work/scenes.json", "w", encoding="utf-8") as f:
    json.dump({"scenes": segments, "total": len(segments)}, f, ensure_ascii=False, indent=2)

# Step 2: 抽关键帧(每段起止双帧)
print("[2/3] 抽关键帧...")
for seg in segments:
    mid = (seg["start"] + seg["end"]) / 2
    # 起始帧
    subprocess.run([FFMPEG, "-ss", str(seg["start"]), "-i", VIDEO, "-vframes", "1",
                    "-q:v", "2", "-y", f"work/frames/seg{seg['id']:03d}_start.jpg"],
                   capture_output=True)
    # 中间帧
    subprocess.run([FFMPEG, "-ss", str(mid), "-i", VIDEO, "-vframes", "1",
                    "-q:v", "2", "-y", f"work/frames/seg{seg['id']:03d}_mid.jpg"],
                   capture_output=True)
    # 结束帧
    subprocess.run([FFMPEG, "-ss", str(seg["end"] - 1), "-i", VIDEO, "-vframes", "1",
                    "-q:v", "2", "-y", f"work/frames/seg{seg['id']:03d}_end.jpg"],
                   capture_output=True)

frame_count = len(os.listdir("work/frames"))
print(f"  抽取 {frame_count} 张关键帧 -> work/frames/")

# Step 3: 视频信息
print("[3/3] 视频信息...")
result = subprocess.run([FFPROBE, "-v", "quiet", "-print_format", "json", "-show_format", VIDEO],
                        capture_output=True, text=True)
info = json.loads(result.stdout)
fmt = info.get("format", {})
duration = float(fmt.get("duration", 0))
total_mins = int(duration // 60)
total_secs = int(duration % 60)
print(f"  时长: {total_mins}分{total_secs}秒")
print(f"  大小: {os.path.getsize(VIDEO) / 1024 / 1024 / 1024:.2f} GB")
print(f"\n场景检测+抽帧完成!")
