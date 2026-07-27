"""
深度解析剪映工程文件 (decrypted draft_content.json)
提取所有可复用的编辑参数：关键帧、字幕样式、贴纸、转场
"""
import json, os, sys
from pathlib import Path
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

with open("ref/draft_content.json.dec.json", encoding="utf-8") as f:
    draft = json.load(f)

print("=" * 70)
print("剪映工程文件深度解析")
print(f"工程名: {draft.get('name', '?')}")
duration_us = draft.get("duration", 0)
print(f"总时长: {duration_us / 1_000_000:.1f} 秒 ({duration_us / 60_000_000:.1f} 分钟)")
print()

# ========== 材料映射 ==========
print("=" * 70)
print("1. 素材清单")
print("=" * 70)

materials = draft.get("materials", {})
for mtype in ["videos", "audios", "texts", "stickers", "effects"]:
    items = materials.get(mtype, [])
    if items:
        print(f"\n  [{mtype}] ({len(items)} 个)")
        for item in items[:3]:
            print(f"    id={item.get('id','?')[:20]}... type={item.get('type','?')} name={item.get('name','?')}")

# ========== 轨道分析 ==========
print(f"\n{'='*70}")
print("2. 轨道详细分析")
print("=" * 70)

tracks = draft.get("tracks", [])
style_params = {
    "keyframes": [],        # 关键帧动画
    "text_styles": [],      # 字幕/文字样式
    "stickers": [],         # 贴纸/叠加素材
    "transitions": [],      # 转场
    "video_segments": [],   # 视频分段
}

for i, track in enumerate(tracks):
    ttype = track.get("type", "?")
    clips = track.get("clips", track.get("segments", []))
    if not clips:
        continue

    print(f"\n--- 轨道{i} [{ttype}] {len(clips)} clips ---")

    for j, clip in enumerate(clips[:3]):  # 只看前3个
        tr = clip.get("target_timerange", {})
        start = tr.get("start", 0) / 1_000_000  # us -> seconds
        duration = tr.get("duration", 0) / 1_000_000
        end = start + duration

        print(f"  clip{j}: {start:.1f}s - {end:.1f}s (dur={duration:.1f}s)")

        # 检查关键帧
        ckf = clip.get("common_keyframes", [])
        if ckf:
            print(f"    ★ 有关键帧: {len(ckf)} 组")
            for kf in ckf[:2]:
                kft = kf.get("keyframe_type", "?")
                props = [k for k in kf.keys() if k not in ("keyframe_type", "id")]
                print(f"      类型={kft}, 属性={props}")
                style_params["keyframes"].append({
                    "track": i, "clip": j, "start": start, "end": end, "duration": duration,
                    "keyframe_type": kft, "params": {p: kf[p] for p in props}
                })

        # 检查动画
        anim = clip.get("animation", clip.get("animations", {}))
        if anim:
            print(f"    ★ 有动画: {list(anim.keys())[:5]}")

        # 文本样式
        if ttype == "text" or "text" in str(clip.get("source", "")):
            text_content = clip.get("content", clip.get("text", ""))
            print(f"    文本: {str(text_content)[:60]}")

# ========== 字幕轨道（405 clips 那个）==========
print(f"\n{'='*70}")
print("3. 字幕分析（轨道8，405 clips）")
print("=" * 70)

subtitle_track = tracks[8] if len(tracks) > 8 else None
if subtitle_track:
    clips = subtitle_track.get("clips", [])
    print(f"  总字幕数: {len(clips)}")
    if clips:
        c0 = clips[0]
        print(f"  首个字幕 keys: {list(c0.keys())}")
        tr = c0.get("target_timerange", {})
        print(f"  时间范围: {tr.get('start',0)/1_000_000:.1f}s - {(tr.get('start',0)+tr.get('duration',0))/1_000_000:.1f}s")
        # 检查字幕样式
        if "content" in c0:
            print(f"  content样例: {str(c0['content'])[:200]}")

# ========== 贴纸素材映射 ==========
print(f"\n{'='*70}")
print("4. 贴纸/叠加素材→本地文件映射")
print("=" * 70)

# 收集所有 material_id
all_material_ids = set()
for track in tracks:
    for clip in track.get("clips", []):
        mid = clip.get("material_id", "")
        if mid:
            all_material_ids.add(mid)

print(f"  工程中引用的 material_id: {len(all_material_ids)} 个")

# 和本地文件交叉匹配
local_pngs = {f.lower(): f for f in os.listdir("ref/materials") if f.endswith(".png")}
print(f"  本地 PNG 文件: {len(local_pngs)} 个")
for name in local_pngs.values():
    print(f"    {name}")

# 找 sticker materials 中的路径引用
stickers = materials.get("stickers", [])
for s in stickers:
    sid = s.get("id", "")
    spath = s.get("path", "")
    if spath:
        print(f"  sticker {sid[:20]}... → path={spath}")

print(f"\n{'='*70}")
print("5. 提取的风格参数摘要")
print("=" * 70)
print(f"  关键帧动画: {len(style_params['keyframes'])} 个")
print(f"  贴纸/叠加: {sum(1 for t in tracks if t.get('type')=='sticker')} 条轨道, 共 {sum(len(t.get('clips',[])) for t in tracks if t.get('type')=='sticker')} 个 clip")

# 保存
with open("work/style_params_raw.json", "w", encoding="utf-8") as f:
    json.dump(style_params, f, ensure_ascii=False, indent=2)

print(f"\n完整参数已保存到 work/style_params_raw.json")
print("=" * 70)
