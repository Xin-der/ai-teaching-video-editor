"""合并 ASR + VLM 标签 → content_map.json"""
import json
import os

SCENES_FILE = "work/scenes.json"
ASR_FILE = "work/asr_result.json"
FRAME_DESC_FILE = "work/frame_descriptions.json"
OUTPUT = "work/content_map.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def merge():
    scenes = load_json(SCENES_FILE)["scenes"]
    asr_data = load_json(ASR_FILE)
    asr_segments = asr_data.get("segments", [])

    # 加载 VLM 描述（如果存在）
    vlm_map = {}
    if os.path.exists(FRAME_DESC_FILE):
        vlm_data = load_json(FRAME_DESC_FILE)
        for s in vlm_data.get("segments", []):
            if "error" not in s:
                vlm_map[s["segment_id"]] = s

    # 构建 content_map
    content_map = []

    for seg in scenes:
        seg_id = seg["id"]
        t_start = seg["start"]
        t_end = seg["end"]

        # 找到时间段内的所有 ASR 句子
        transcript_parts = []
        for asr_s in asr_segments:
            asr_start = asr_s["start"]
            asr_end = asr_s["end"]
            # 检查是否有重叠
            if asr_end > t_start and asr_start < t_end:
                transcript_parts.append(asr_s)

        # 合并文本
        transcript = " ".join([p["text"] for p in transcript_parts]) if transcript_parts else ""

        # 推断说话人（简单规则：驾考教学视频默认教练讲解）
        speaker = "教练"
        # 注：当前 FunASR 只用了 paraformer-zh，未做说话人分离
        # 后续可通过 CAM++ 模型添加说话人标签

        # 从 VLM 获取标签
        vlm = vlm_map.get(seg_id, {})
        labels = vlm.get("visible_elements", [])
        # 将 location/activity 也加入 labels
        location = vlm.get("location", "")
        activity = vlm.get("activity", "")
        who = vlm.get("who_visible", [])

        # 构建统一的 labels 列表
        all_labels = []
        if location:
            all_labels.append(f"location:{location}")
        if activity:
            all_labels.append(f"activity:{activity}")
        for w in who:
            all_labels.append(f"who:{w}")
        for elem in labels:
            all_labels.append(f"element:{elem}")

        entry = {
            "segment_id": seg_id,
            "track": seg["track"],
            "t_start": t_start,
            "t_end": t_end,
            "duration": round(t_end - t_start, 2),
            "speaker": speaker,
            "labels": all_labels,
            "transcript": transcript,
            "asr_sentence_count": len(transcript_parts),
            "summary": vlm.get("summary", ""),
            "location": location,
            "activity": activity,
            "who_visible": who,
            "lighting": vlm.get("lighting", ""),
            "camera_angle": vlm.get("camera_angle", "")
        }
        content_map.append(entry)

    # 保存
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(content_map, f, ensure_ascii=False, indent=2)

    # 统计
    total_asr = sum(e["asr_sentence_count"] for e in content_map)
    vlm_segments = sum(1 for e in content_map if e["summary"])
    print(f"=== content_map 合并完成 ===")
    print(f"视频分段: {len(content_map)} 段")
    print(f"ASR 句子: {total_asr} 句（总 {len(asr_segments)} 句）")
    print(f"VLM 标签: {vlm_segments}/{len(content_map)} 段有描述")
    print(f"输出: {OUTPUT}")

    # 打印预览
    print(f"\n--- 预览 ---")
    for e in content_map[:5]:
        ts = e["transcript"][:60] + "..." if len(e["transcript"]) > 60 else e["transcript"]
        print(f"  seg{e['segment_id']:03d} [{e['t_start']:.0f}s-{e['t_end']:.0f}s] "
              f"speaker={e['speaker']} labels={len(e['labels'])} "
              f"asr={e['asr_sentence_count']}句")
        print(f"    activity={e['activity']} | {e['summary'][:60]}")
        if ts:
            print(f"    text: {ts}")


if __name__ == "__main__":
    merge()
