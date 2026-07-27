"""AI 教学视频剪辑 · 一键出片入口"""
import subprocess, sys, os

STEPS = [
    ("ASR 语音识别", "scripts/run_asr.py"),
    ("VLM 关键帧描述", "scripts/describe_frames.py"),
    ("合并 content_map", "scripts/merge_content_map.py"),
    ("标签匹配", "scripts/match_style.py"),
    ("渲染出片", "scripts/render.py"),
]

def main():
    print("=" * 50)
    print("  AI 教学视频剪辑 · 一键出片")
    print("=" * 50)
    print()

    python = sys.executable

    for step_name, script in STEPS:
        if not os.path.exists(script):
            print(f"[跳过] {step_name}: 脚本不存在 ({script})")
            continue

        print(f"[运行] {step_name}...")
        result = subprocess.run([python, script], capture_output=False)

        if result.returncode != 0:
            print(f"\n[失败] {step_name} 返回错误码 {result.returncode}")
            choice = input("继续下一步? (y/n): ")
            if choice.lower() != 'y':
                print("已中止")
                sys.exit(1)

        print()

    print("=" * 50)
    print("  完成! 成品在 output/成片.mp4")
    print("=" * 50)


if __name__ == "__main__":
    main()
