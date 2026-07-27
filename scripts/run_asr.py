"""ASR 语音识别 - 分段处理"""
import json, os, subprocess

AUDIO = "work/ref_audio.wav"
OUTPUT = "work/asr_result.json"

print("[1/3] 加载 FunASR 模型...")
from funasr import AutoModel
import soundfile as sf
import numpy as np

model = AutoModel(model="paraformer-zh", model_revision="v2.0.4")

print("[2/3] 读取音频...")
audio_data, sr = sf.read(AUDIO)
if len(audio_data.shape) > 1:
    audio_data = audio_data.mean(axis=1)
duration_sec = len(audio_data) / sr
print(f"  时长: {duration_sec:.1f}秒")

# 分段 (每60秒)
CHUNK_SEC = 60
chunk_samples = CHUNK_SEC * sr
total_chunks = (len(audio_data) + chunk_samples - 1) // chunk_samples
print(f"[3/3] 分段转写 ({total_chunks} 段)...")

all_segments = []
time_offset = 0.0

for i in range(total_chunks):
    start_idx = i * chunk_samples
    end_idx = min(start_idx + chunk_samples, len(audio_data))
    chunk = audio_data[start_idx:end_idx]
    chunk_dur = len(chunk) / sr

    # 跳过静音段 (RMS < 0.01)
    rms = np.sqrt(np.mean(chunk ** 2))
    if rms < 0.01:
        print(f"  段{i+1}/{total_chunks}: {time_offset:.0f}s-{time_offset+chunk_dur:.0f}s 静音跳过 (RMS={rms:.4f})")
        time_offset += chunk_dur
        continue

    print(f"  段{i+1}/{total_chunks}: {time_offset:.0f}s-{time_offset+chunk_dur:.0f}s RMS={rms:.4f}...", end=" ")

    temp_file = f"work/_chunk_{i}.wav"
    sf.write(temp_file, chunk.astype(np.float32), sr)

    try:
        result = model.generate(input=temp_file)
        if result and len(result) > 0:
            r = result[0]
            text = r.get("text", "")
            timestamps = r.get("timestamp", [])
            if text and timestamps:
                # 将 timestamp 对按 text 字符切分
                # Paraformer 输出 text 是空格分隔的字符序列
                # timestamp 是每个字/词的 [start_ms, end_ms]
                # 我们按每5个timestamp合并为一句话
                words = text.split()
                seg_texts = []
                seg_times = []
                buf = []
                buf_start = None
                buf_end = None
                for wi, ts in enumerate(timestamps):
                    if wi < len(words):
                        w = words[wi]
                    else:
                        continue
                    ts_start = ts[0] / 1000.0  # ms -> s
                    ts_end = ts[1] / 1000.0

                    if buf_start is None:
                        buf_start = ts_start
                    buf.append(w)
                    buf_end = ts_end

                    # 遇到标点或超过20个字，切一句
                    if len(buf) >= 20 or w in ("啊", "呢", "吧", "吗", "的", "了"):
                        seg_texts.append("".join(buf))
                        seg_times.append((buf_start, buf_end))
                        buf = []
                        buf_start = None

                # 剩余
                if buf:
                    seg_texts.append("".join(buf))
                    seg_times.append((buf_start, buf_end))

                for si, (seg_text, (st, et)) in enumerate(zip(seg_texts, seg_times)):
                    all_segments.append({
                        "start": round(time_offset + st, 2),
                        "end": round(time_offset + et, 2),
                        "text": seg_text
                    })
                print(f"{len(seg_texts)} 句")
            else:
                print("空结果")
        else:
            print("无结果")
    except Exception as e:
        print(f"失败: {type(e).__name__}")
    finally:
        if os.path.exists(temp_file):
            os.remove(temp_file)

    time_offset += chunk_dur

# 保存
with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump({"segments": all_segments, "total": len(all_segments)}, f, ensure_ascii=False, indent=2)

print(f"\nASR 完成! 共 {len(all_segments)} 句")
for s in all_segments[:15]:
    print(f"  [{s['start']:.1f}s-{s['end']:.1f}s] {s['text']}")
