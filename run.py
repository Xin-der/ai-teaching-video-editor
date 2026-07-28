"""AI 教学视频剪辑 · 入口

用法:
  python run.py                       处理 input/video.mp4（完整管线）
  python run.py --input 我的视频.mp4   处理指定视频
  python run.py --skip-vlm            跳过 VLM（已有描述结果时）
  python run.py --learn-style         第一段：学风格（从参考视频生成规则）
"""
import sys, os, argparse

parser = argparse.ArgumentParser(description="AI 教学视频剪辑")
parser.add_argument("--input", default="input/video.mp4", help="输入视频路径")
parser.add_argument("--route-map", default=None, help="路线图路径")
parser.add_argument("--output", default="output/成片.mp4", help="输出路径")
parser.add_argument("--skip-asr", action="store_true", help="跳过 ASR")
parser.add_argument("--skip-vlm", action="store_true", help="跳过 VLM")
parser.add_argument("--resolution", default="1080p", help="渲染分辨率")
parser.add_argument("--learn-style", action="store_true", help="学风格模式")
args = parser.parse_args()


def run_new_video():
    """处理新视频：input/ → output/"""
    cmd = [sys.executable, "scripts/process_video.py",
           "--input", args.input,
           "--output", args.output,
           "--resolution", args.resolution]
    if args.route_map:
        cmd += ["--route-map", args.route_map]
    if args.skip_asr:
        cmd.append("--skip-asr")
    if args.skip_vlm:
        cmd.append("--skip-vlm")

    print(f"运行: {' '.join(cmd)}")
    os.execv(sys.executable, cmd)


def run_learn_style():
    """第一段：分析参考视频，生成风格规则"""
    print("=" * 50)
    print("  第一段：学风格")
    print("=" * 50)
    print()
    print("这个模式需要:")
    print("  1. ref/ 下有参考成品视频 + draft_content.json")
    print("  2. 运行后生成 style_labels.json + skill_style.md")
    print()
    print("如果你已经运行过了，style_labels.json 已存在，")
    print("直接用 'python run.py' 处理新视频即可。")
    print()
    print("如需重新学风格，请手动运行:")
    print("  python scripts/run_asr.py")
    print("  python scripts/describe_frames.py")
    print("  python scripts/merge_content_map.py")
    print("  python scripts/translate_style.py")


if __name__ == "__main__":
    if args.learn_style:
        run_learn_style()
    else:
        if not os.path.exists(args.input):
            print(f"❌ 找不到视频: {args.input}")
            print()
            print("用法:")
            print("  python run.py                         处理 input/video.mp4")
            print("  python run.py --input 我的视频.mp4     处理指定视频")
            print("  python run.py --learn-style            学风格模式")
            sys.exit(1)
        run_new_video()
