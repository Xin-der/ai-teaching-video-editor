"""
多平台智能切片工具 · 入口

用法:
  python run.py <视频路径>                    完整管线：分段 + 评分 + 预览
  python run.py <视频路径> --export           分段后直接导出所有平台
  python run.py <视频路径> --platforms douyin  只导出抖音
  python run.py <视频路径> --skip-asr          跳过 ASR（使用缓存）
  python run.py <视频路径> --skip-vlm          跳过 VLM（使用缓存）
  python run.py <视频路径> --skip-all          全跳过（只用缓存分段结果导出）

示例:
  python run.py input/video.mp4
  python run.py input/video.mp4 --export --platforms douyin,bilibili
  python run.py input/video.mp4 --skip-asr --skip-scenes --export
"""

import argparse
import os
import sys

from dotenv import load_dotenv
load_dotenv()

from engine import Pipeline


def main():
    parser = argparse.ArgumentParser(
        description="多平台智能切片工具 — 长教学视频 → 智能切片 → 多平台导出 + 文案",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py input/video.mp4                    分段预览
  python run.py input/video.mp4 --export            分段 + 全平台导出
  python run.py input/video.mp4 --platforms douyin  只看抖音导出
  python run.py input/video.mp4 --skip-asr          跳过 ASR 用缓存
        """,
    )

    parser.add_argument("video", help="输入视频路径")
    parser.add_argument("--output-dir", default="output", help="输出目录 (默认: output)")
    parser.add_argument("--work-dir", default="work", help="工作目录 (默认: work)")

    # 步骤跳过
    parser.add_argument("--skip-audio", action="store_true", help="跳过音频提取")
    parser.add_argument("--skip-asr", action="store_true", help="跳过 ASR 语音识别")
    parser.add_argument("--skip-scenes", action="store_true", help="跳过场景检测")
    parser.add_argument("--skip-vlm", action="store_true", help="跳过 VLM 关键帧描述")
    parser.add_argument("--skip-all", action="store_true", help="跳过所有分析步骤")

    # 导出
    parser.add_argument("--export", action="store_true", help="分段后自动导出")
    parser.add_argument("--platforms", default="douyin,bilibili,xiaohongshu",
                        help="导出平台，逗号分隔 (默认: douyin,bilibili,xiaohongshu)")

    # 其他
    parser.add_argument("--interactive", action="store_true",
                        help="交互模式：分段后等待确认再导出")
    parser.add_argument("--only-export", action="store_true",
                        help="仅导出（不运行管线，使用已有分段结果）")

    args = parser.parse_args()

    # 检查视频文件
    if not os.path.exists(args.video):
        print(f"❌ 找不到视频文件: {args.video}")
        print(f"\n💡 请将视频放入 input/ 目录，然后运行:")
        print(f"   python run.py input/你的视频.mp4")
        sys.exit(1)

    # 检查 API Key
    if not os.environ.get("DASHSCOPE_API_KEY"):
        print("❌ 未设置 DASHSCOPE_API_KEY")
        print("   请在 .env 文件中配置 API Key")
        sys.exit(1)

    # --- 仅导出模式 ---
    if args.only_export:
        print("📦 仅导出模式 — 加载已有分段结果...")
        segments_path = os.path.join(args.work_dir, "segments.json")
        if not os.path.exists(segments_path):
            print(f"❌ 找不到分段结果: {segments_path}")
            print("   请先运行管线: python run.py <视频路径>")
            sys.exit(1)

        import json
        with open(segments_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        p = Pipeline(args.video, output_dir=args.output_dir, work_dir=args.work_dir)
        p.merged_segments = data["segments"]
        p.video_duration = data.get("video_duration", 0)

        platforms = [p.strip() for p in args.platforms.split(",")]
        _do_export(p, platforms)
        return

    # --- 全流程 ---
    skip_all = args.skip_all
    p = Pipeline(args.video, output_dir=args.output_dir, work_dir=args.work_dir)

    segments = p.run(
        skip_audio=skip_all or args.skip_audio,
        skip_asr=skip_all or args.skip_asr,
        skip_scenes=skip_all or args.skip_scenes,
        skip_vlm=skip_all or args.skip_vlm,
    )

    if not segments:
        print("\n⚠ 没有生成任何片段")
        sys.exit(1)

    p.print_segments(segments)

    # --- 导出 ---
    if args.interactive:
        print("\n" + "=" * 60)
        resp = input("确认导出? [Y/n/输入逗号分隔的平台名]: ").strip()
        if resp.lower() in ("n", "no", "q", "quit"):
            print("已取消导出")
            sys.exit(0)
        elif resp and not resp.lower().startswith("y"):
            platforms = [p.strip() for p in resp.split(",")]
        else:
            platforms = [p.strip() for p in args.platforms.split(",")]
    elif args.export:
        platforms = [p.strip() for p in args.platforms.split(",")]
    else:
        # 默认只预览
        print(f"\n💡 运行 'python run.py {args.video} --export' 一键导出所有平台")
        return

    _do_export(p, platforms)


def _do_export(pipeline: Pipeline, platforms: list):
    """执行导出"""
    print(f"\n{'='*60}")
    print(f"  开始导出 → {', '.join(platforms)}")
    print(f"{'='*60}")

    results = pipeline.export_all(platforms=platforms)

    if results:
        print(f"\n{'='*60}")
        print(f"  导出完成! 共 {len(results)} 个视频")
        print(f"{'='*60}")
        for r in results:
            print(f"  ✓ [{r['platform']}] {r['output_path']}")
            if r.get("copy_path"):
                print(f"    📝 文案: {r['copy_path']}")
    else:
        print("\n⚠ 没有生成任何导出视频")


if __name__ == "__main__":
    main()
