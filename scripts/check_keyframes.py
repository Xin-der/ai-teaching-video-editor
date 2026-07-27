import json

with open("ref/draft_content.json.dec.json", encoding="utf-8") as f:
    draft = json.load(f)

# 轨道7 sticker关键帧实际值
t7 = draft['tracks'][7]
seg1 = t7['segments'][1]
print("=== 轨道7 seg1 贴纸关键帧 ===")
for kf in seg1['common_keyframes']:
    pt = kf['property_type']
    kl = kf['keyframe_list']
    print(f"\n{pt} ({len(kl)} keyframes)")
    for k in kl[:2]:
        to = k.get('time_offset')
        v = k.get('value')
        print(f"  time_offset={to}")
        print(f"  value type={type(v).__name__}")
        if isinstance(v, dict):
            for vk, vv in v.items():
                print(f"    {vk} = {vv}")
        else:
            print(f"  value = {v}")

# 文字样式深入
print("\n\n=== 文字样式深入 ===")
texts = draft.get('materials', {}).get('texts', [])
if texts:
    t0 = texts[0]
    content = json.loads(t0.get('content', '{}'))
    styles = content.get('styles', [])
    if styles:
        s0 = styles[0]
        print(f"font = {s0.get('font')}")
        print(f"size = {s0.get('size')}")
        fill = s0.get('fill', {})
        print(f"fill = {json.dumps(fill, indent=2)[:300]}")

# 视频轨道0 seg2关键帧值
print("\n\n=== 轨道0 seg2 关键帧值 ===")
t0seg2 = draft['tracks'][0]['segments'][2]
for kf in t0seg2['common_keyframes'][:2]:
    pt = kf['property_type']
    kl = kf['keyframe_list']
    print(f"\n{pt} ({len(kl)} keyframes)")
    for k in kl[:2]:
        to = k.get('time_offset')
        v = k.get('value')
        print(f"  time={to}, value={v}")
