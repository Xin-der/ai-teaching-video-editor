"""深入提取关键帧数值、贴纸参数、文本样式"""
import json

with open("ref/draft_content.json.dec.json", encoding="utf-8") as f:
    draft = json.load(f)

tracks = draft['tracks']

# 按类型分类轨道
video_tracks = [(i, t) for i, t in enumerate(tracks) if t['type'] == 'video']
sticker_tracks = [(i, t) for i, t in enumerate(tracks) if t['type'] == 'sticker']
audio_tracks = [(i, t) for i, t in enumerate(tracks) if t['type'] == 'audio']

print(f"轨道分类: {len(video_tracks)}条视频轨, {len(audio_tracks)}条音频轨, {len(sticker_tracks)}条贴纸轨")

# === 所有有关键帧的 segments ===
print(f"\n{'='*60}")
print("关键帧详情")
print(f"{'='*60}")

for ti, track in enumerate(tracks):
    for si, seg in enumerate(track.get('segments', [])):
        kfs = seg.get('common_keyframes', [])
        if not kfs:
            continue
        tr = seg.get('target_timerange', {})
        start = tr.get('start', 0) / 1_000_000
        dur = tr.get('duration', 0) / 1_000_000
        end = start + dur
        print(f"\n轨道{ti} [{track['type']}] seg{si}: {start:.1f}s-{end:.1f}s ({len(kfs)}个关键帧组)")

        for kf in kfs[:3]:
            pt = kf.get('property_type', '?')
            kl = kf.get('keyframe_list', [])
            print(f"  property_type={pt}")
            for k in kl[:4]:
                val = k.get('value', '?')
                t = k.get('time_offset', 0) / 1_000_000
                # 截断太长的值
                val_str = str(val)
                if len(val_str) > 80:
                    val_str = val_str[:80] + "..."
                print(f"    @{t:.2f}s -> {val_str}")

# === 贴纸轨道的时间分布 ===
print(f"\n{'='*60}")
print("贴纸时间分布 (前20个)")
print(f"{'='*60}")

sticker_count = 0
for ti, track in enumerate(tracks):
    if track['type'] != 'sticker':
        continue
    for si, seg in enumerate(track.get('segments', [])):
        if sticker_count >= 20:
            break
        tr = seg.get('target_timerange', {})
        start = tr.get('start', 0) / 1_000_000
        dur = tr.get('duration', 0) / 1_000_000
        print(f"  轨道{ti} seg{si}: {start:.1f}s-{start+dur:.1f}s ({dur:.1f}s)")
        sticker_count += 1
    if sticker_count >= 20:
        break

# === 文字样式 ===
print(f"\n{'='*60}")
print("文字/字幕样式")
print(f"{'='*60}")

texts = draft.get('materials', {}).get('texts', [])
if texts:
    t0 = texts[0]
    content = t0.get('content', '')
    try:
        ct = json.loads(content)
        styles = ct.get('styles', [])
        if styles:
            s0 = styles[0]
            print(f"  字体: {s0.get('font_family','?')}")
            print(f"  字号: {s0.get('font_size','?')}")
            fill = s0.get('fill', {}).get('content', {}).get('solid_color', {})
            if fill:
                print(f"  颜色: rgba({fill.get('r','?')},{fill.get('g','?')},{fill.get('b','?')},{fill.get('a','?')})")
            stroke = s0.get('stroke', {})
            if stroke:
                sc = stroke.get('content', {}).get('solid_color', {})
                print(f"  描边: {stroke.get('width','?')}px rgba({sc.get('r','?')},{sc.get('g','?')},{sc.get('b','?')},{sc.get('a','?')})")
            # 看所有样式属性
            print(f"  所有属性: {list(s0.keys())}")
    except Exception as e:
        print(f"  解析失败: {e}")
        print(f"  原始: {str(content)[:200]}")

# === 贴纸素材信息 ===
print(f"\n{'='*60}")
print("贴纸素材")
print(f"{'='*60}")
stickers = draft.get('materials', {}).get('stickers', [])
for s in stickers[:5]:
    print(f"  id={s.get('id','?')[:30]}... name={s.get('name','?')}")

print(f"\n分析完成")
