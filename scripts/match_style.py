"""标签匹配引擎 — 确定性匹配（不调 LLM），content_map → edit_ops"""
import json, os, sys

CONTENT_MAP = "work/content_map.json"
STYLE_LABELS = "style_labels.json"
OUTPUT = "work/edit_ops.json"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def check_condition(condition, segment_labels, has_route_map, has_speech):
    """检查一个规则的条件是否满足"""
    required = condition.get("required", [])
    any_of = condition.get("any_of", [])
    required_absent = condition.get("required_absent", [])
    optional = condition.get("optional", [])

    # 检查 required: 所有必需标签都必须存在（AND 逻辑）
    for req in required:
        if req == "has_text_overlay:true":
            if "element:文字叠加" not in segment_labels:
                return False
        elif req == "has_valid_speech:true":
            if not has_speech:
                return False
        elif req == "has_route_map_in_frame:true":
            if not has_route_map:
                return False
        elif req not in segment_labels:
            return False

    # 检查 any_of: 至少一个标签存在（OR 逻辑）
    if any_of:
        matched_any = False
        for a in any_of:
            if a == "has_text_overlay:true":
                if "element:文字叠加" in segment_labels:
                    matched_any = True
                    break
            elif a == "has_valid_speech:true":
                if has_speech:
                    matched_any = True
                    break
            elif a in segment_labels:
                matched_any = True
                break
        if not matched_any:
            return False

    # 检查 required_absent: 这些标签必须不存在
    for absent in required_absent:
        if absent == "has_text_overlay:true":
            if "element:文字叠加" in segment_labels:
                return False
        elif absent == "has_valid_speech:true":
            if has_speech:
                return False
        elif absent == "has_route_map_in_frame:true":
            if has_route_map:
                return False
        elif absent in segment_labels:
            return False

    return True


def match_segment(seg, style_rules, has_route_map):
    """为一个分段匹配风格规则。分支规则互斥（同一段只走一条分支）"""
    labels = seg.get("labels", [])
    has_speech = seg.get("asr_sentence_count", 0) > 0
    has_text = "element:文字叠加" in labels

    matched_ops = []
    applied_branches = []

    # --- 第一步：选分支（互斥，按优先级） ---
    branch_rules = [r for r in style_rules if r.get("rule_id", "").startswith("BRANCH_")]
    branch_rules.sort(key=lambda r: r.get("priority", 99))  # 数字越小优先级越高

    selected_branch = None
    for rule in branch_rules:
        condition = rule.get("condition", {})
        if condition and check_condition(condition, labels, has_route_map, has_speech):
            selected_branch = rule
            break  # 互斥：匹配到第一条就停止

    if selected_branch:
        applied_branches.append(selected_branch["rule_id"])
        for action in selected_branch.get("actions", []):
            action["_triggered_by"] = selected_branch["rule_id"]
            action["_priority"] = selected_branch.get("priority", 99)
            matched_ops.append(action)

    # --- 第二步：通用规则（所有段都检查，与分支独立） ---
    universal_rules = [r for r in style_rules
                       if not r.get("rule_id", "").startswith("BRANCH_")
                       and r.get("rule_id", "") != "DETECT_001"
                       and "condition" not in r]  # 只取有 trigger 的通用规则

    for rule in universal_rules:
        trigger = rule.get("trigger", {})
        if trigger and check_condition(trigger, labels, has_route_map, has_speech):
            for action in rule.get("actions", []):
                action["_triggered_by"] = rule["rule_id"]
                action["_priority"] = rule.get("priority", 99)
                matched_ops.append(action)

    return matched_ops, applied_branches, has_text, has_speech


def main():
    content_map = load_json(CONTENT_MAP)
    style_rules = load_json(STYLE_LABELS)

    # 检测是否有路线图素材
    route_map_path = "input/route_map.png"
    has_route_map = os.path.exists(route_map_path)

    # 检测是否有特写素材
    has_foot_closeup = os.path.exists("input/foot_closeup.mp4") or os.path.exists("input/foot_closeup.jpg")
    has_dash_closeup = os.path.exists("input/dashboard_closeup.mp4") or os.path.exists("input/dashboard_closeup.jpg")

    print(f"=== 标签匹配引擎 ===\n")
    print(f"路线图: {'有' if has_route_map else '无'} ({route_map_path})")
    print(f"脚部特写: {'有' if has_foot_closeup else '无'}")
    print(f"仪表盘特写: {'有' if has_dash_closeup else '无'}")
    print(f"分段数: {len(content_map)}\n")

    edit_ops = []
    stats = {"BRANCH_A": 0, "BRANCH_B": 0, "BRANCH_C": 0, "BRANCH_D": 0,
             "RULE_ZOOM": 0, "RULE_PIP": 0, "RULE_TEXT_OVERLAY": 0}

    for seg in content_map:
        seg_id = seg["segment_id"]
        ops, branches, has_text, has_speech = match_segment(seg, style_rules, has_route_map)

        # 统计
        for b in branches:
            if b in stats:
                stats[b] += 1
        for op in ops:
            rid = op.get("_triggered_by", "")
            if rid in stats:
                stats[rid] += 1

        # 过滤掉 DETECT 和描述性字段，只保留实际操作
        clean_ops = []
        for op in ops:
            clean_op = {
                "op": op["op"],
                "params": {k: v for k, v in op.get("params", {}).items()},
                "description": op.get("description", "")
            }
            clean_ops.append(clean_op)

        if clean_ops:
            edit_ops.append({
                "segment_id": seg_id,
                "t_start": seg["t_start"],
                "t_end": seg["t_end"],
                "duration": seg.get("duration", 0),
                "track": seg.get("track", 0),
                "has_text_overlay": has_text,
                "has_speech": has_speech,
                "activity": seg.get("activity", ""),
                "location": seg.get("location", ""),
                "operations": clean_ops
            })

    # 保存
    output_data = {
        "video_source": "input/video.mp4",
        "route_map": route_map_path if has_route_map else None,
        "has_foot_closeup": has_foot_closeup,
        "has_dash_closeup": has_dash_closeup,
        "total_segments": len(edit_ops),
        "segments": edit_ops,
        "stats": stats
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"=== 匹配完成 ===")
    print(f"分支A (文字+地图): {stats.get('BRANCH_A', 0)} 段")
    print(f"分支B (语音+地图): {stats.get('BRANCH_B', 0)} 段")
    print(f"分支C (纯视觉):    {stats.get('BRANCH_C', 0)} 段")
    print(f"分支D (无地图):    {stats.get('BRANCH_D', 0)} 段")
    print(f"ZOOM 规则触发:    {stats.get('RULE_ZOOM', 0)} 段")
    print(f"PIP 规则触发:     {stats.get('RULE_PIP', 0)} 段")
    print(f"字幕规则触发:     {stats.get('RULE_TEXT_OVERLAY', 0)} 段")
    print(f"输出: {OUTPUT}")


if __name__ == "__main__":
    main()
