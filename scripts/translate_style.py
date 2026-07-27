"""LLM 风格翻译 — 把"工程参数 + 语义标签"对齐成风格规则"""
import json, os, time
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

API_KEY = os.getenv("DASHSCOPE_API_KEY")
MODEL = os.getenv("MODEL", "qwen3.7-plus")

# 使用 DashScope 的 OpenAI 兼容端点
client = OpenAI(
    api_key=API_KEY,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

STYLE_PARAMS_FILE = "work/style_params_raw.json"
CONTENT_MAP_FILE = "work/content_map.json"
OUTPUT_LABELS = "style_labels.json"
OUTPUT_SKILL = "skill_style.md"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_prompt():
    """构建风格翻译 prompt"""
    style_params = load_json(STYLE_PARAMS_FILE)
    content_map = load_json(CONTENT_MAP_FILE)

    # 简化 style_params: 只提取关键信息
    params_summary = []
    for kf in style_params.get("keyframes", []):
        prop = kf["params"]["property_type"]
        # 提取 values 列表
        values_list = []
        for kl in kf["params"]["keyframe_list"]:
            values_list.append({
                "time_offset_us": kl["time_offset"],
                "values": kl["values"]
            })
        params_summary.append({
            "track": kf["track"],
            "clip": kf["clip"],
            "property": prop,
            "time_range": f"{kf['start']:.1f}s - {kf['end']:.1f}s",
            "duration": f"{kf['duration']:.1f}s",
            "keyframes": values_list
        })

    # 简化 content_map: 去掉 transcript 全文，只保留摘要
    content_summary = []
    for seg in content_map:
        content_summary.append({
            "segment_id": seg["segment_id"],
            "track": seg["track"],
            "time_range": f"{seg['t_start']:.1f}s - {seg['t_end']:.1f}s",
            "speaker": seg["speaker"],
            "labels": seg["labels"],
            "location": seg.get("location", ""),
            "activity": seg.get("activity", ""),
            "who_visible": seg.get("who_visible", []),
            "summary": seg.get("summary", ""),
            "transcript_preview": seg.get("transcript", "")[:100]
        })

    prompt = f"""你是一名视频剪辑风格分析师。我有一段驾考教学视频（番禺科目三1号线，手动挡C1），现在有两份数据需要你对齐：

## A 部分：工程参数（从剪映 draft_content.json 提取的关键帧）
```json
{json.dumps(params_summary, ensure_ascii=False, indent=2)}
```

## B 部分：内容语义标签（VLM 视频分析结果）
```json
{json.dumps(content_summary, ensure_ascii=False, indent=2)}
```

## 任务

请分析 A 部分（工程参数）和 B 部分（语义标签），将它们对齐成**风格规则**。

### 工程参数解读指南：
- `KFTypeScaleY`: Y轴缩放关键帧 → 控制画面缩放（zoom in/out）
- `KFTypePositionY`: Y轴位置关键帧 → 控制垂直平移
- `KFTypeColorMatch`: 色彩匹配 → 画面调色
- `KFTypePrimaryColorWheelIntensity`: 主色轮强度 → 滤镜强度
- Track 0 = 主视频轨, Track 3/7 = 叠加素材轨（如路线图、标签）
- ScaleY 值从大到小 = zoom out（缩小），从小到大 = zoom in（放大）

### 输出要求

请输出两部分:

**1. 先输出 `style_labels.json`（JSON 格式，严格按以下结构）:**
```json
[
  {{
    "rule_id": "规则唯一ID",
    "name": "规则名称（中文）",
    "trigger": {{
      "required": ["标签1", "标签2"],
      "optional": ["标签3"]
    }},
    "actions": [
      {{"op": "操作名", "params": {{"key": "value"}}}}
    ],
    "description": "规则描述",
    "applies_to": "哪个 track 或 clip",
    "time_range": "适用的时间范围"
  }}
]
```

**2. 然后输出 `skill_style.md`（Markdown 格式）:**

一个给人看和给 AI 看都清晰的风格说明书，包含:
- 视频整体风格概览
- 每个风格规则的详细说明（触发条件 → 应用的视觉特效）
- 素材清单（需要哪些图片/贴纸素材）
- 未确定项（因为工程文件关键帧数据不完整，哪些参数需要人工确认）

注意：
1. 如果工程参数的 time_range 与某段语义标签的 time_range 重叠，说明这个特效是用在这个语义场景上的
2. 没有工程参数的场景，根据 VLM 描述推断可能的特效（标注为"推测"）
3. style_labels.json 中的 required 标签用英文（如 activity:讲解灯光），保持与 content_map 一致
"""

    return prompt


def call_llm(prompt):
    """调用 LLM 生成风格规则"""
    print("调用 LLM 进行风格翻译...")
    print(f"Prompt 长度: {len(prompt)} 字符")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=8000,
                temperature=0.3
            )
            text = resp.choices[0].message.content
            return text
        except Exception as e:
            print(f"  ⚠ 异常 (attempt {attempt+1}): {type(e).__name__}: {e}")
            if attempt < max_retries - 1:
                time.sleep(5)

    return None


def parse_output(text):
    """从 LLM 输出中解析 JSON 和 Markdown"""
    # 尝试提取 style_labels.json 部分
    json_start = text.find("```json")
    json_lines = []
    in_json = False
    style_labels = None

    if json_start >= 0:
        # 找到 JSON 代码块
        json_content_start = text.find("\n", json_start) + 1
        json_end = text.find("```", json_content_start)
        if json_end >= 0:
            json_str = text[json_content_start:json_end].strip()
            try:
                style_labels = json.loads(json_str)
            except json.JSONDecodeError:
                # 尝试修复: 找第一个 [ 到最后一个 ]
                arr_start = json_str.find("[")
                arr_end = json_str.rfind("]")
                if arr_start >= 0 and arr_end >= 0:
                    try:
                        style_labels = json.loads(json_str[arr_start:arr_end+1])
                    except json.JSONDecodeError:
                        pass

    # 提取 skill_style.md 部分（第二个 ```markdown 块或 JSON 后面的内容）
    md_start = text.find("skill_style.md")
    if md_start < 0:
        md_start = text.find("##")
    if md_start < 0:
        # 取 JSON 之后的所有内容
        md_start = text.find("```", json_start + 10) + 3 if json_start >= 0 else 0
        skill_md = text[md_start:].strip()
    else:
        skill_md = text[md_start:].strip()

    return style_labels, skill_md


def main():
    # 构建 prompt
    prompt = build_prompt()

    # 调用 LLM
    t0 = time.time()
    result = call_llm(prompt)
    elapsed = time.time() - t0

    if not result:
        print("LLM 调用失败!")
        return

    print(f"LLM 响应 ({elapsed:.0f}s), 长度: {len(result)} 字符")

    # 保存原始响应
    with open("work/_llm_style_raw.txt", "w", encoding="utf-8") as f:
        f.write(result)

    # 解析输出
    style_labels, skill_md = parse_output(result)

    # 保存 style_labels.json
    if style_labels:
        with open(OUTPUT_LABELS, "w", encoding="utf-8") as f:
            json.dump(style_labels, f, ensure_ascii=False, indent=2)
        print(f"\n✓ style_labels.json 已保存 ({len(style_labels)} 条规则)")
    else:
        print("\n⚠ 未能解析出 style_labels.json，请检查 work/_llm_style_raw.txt")

    # 保存 skill_style.md
    if skill_md:
        with open(OUTPUT_SKILL, "w", encoding="utf-8") as f:
            f.write(skill_md)
        print(f"✓ skill_style.md 已保存 ({len(skill_md)} 字符)")
    else:
        # 用全部输出作为 skill_style.md
        with open(OUTPUT_SKILL, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"⚠ skill_style.md 使用完整输出 ({len(result)} 字符)")

    print(f"\n=== Step 4 完成 ===")
    print(f"输出: {OUTPUT_LABELS}, {OUTPUT_SKILL}")
    print(f"预估费用: ¥0.01")


if __name__ == "__main__":
    main()
