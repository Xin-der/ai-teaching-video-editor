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

# Fix Unicode emoji output on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from dotenv import load_dotenv
load_dotenv()

from engine import Pipeline


def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="多平台智能切片工具 — 长教学视频 → 智能切片 → 多平台导出 + 文案",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py input/video.mp4                    分段预览
  python run.py input/video.mp4 --export            分段 + 全平台导出
  python run.py input/video.mp4 --optimize          内容优化（出方案）
  python run.py --optimize --text "粘贴内容"        文字内容优化
        """,
    )
    parser.add_argument("video", nargs="?", help="输入视频路径（使用 --web 时可选）")
    parser.add_argument("--output-dir", default="output", help="输出目录 (默认: output)")
    parser.add_argument("--work-dir", default="work", help="工作目录 (默认: work)")

    # 步骤跳过
    parser.add_argument("--skip-audio", action="store_true", help="跳过音频提取")
    parser.add_argument("--skip-asr", action="store_true", help="跳过 ASR 语音识别")
    parser.add_argument("--skip-scenes", action="store_true", help="跳过场景检测")
    parser.add_argument("--skip-vlm", action="store_true", help="跳过 VLM 关键帧描述")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM 内容分析")
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
    parser.add_argument("--web", action="store_true",
                        help="启动 Web 预览界面（本地浏览器）")
    parser.add_argument("--web-port", type=int, default=5000,
                        help="Web 界面端口 (默认: 5000)")

    # 内容优化
    parser.add_argument("--optimize", action="store_true",
                        help="内容优化模式：视频/文字 → 《内容优化方案》")
    parser.add_argument("--city", default="", help="所在城市（用于同城关键词）")
    parser.add_argument("--text", default="", help="直接输入文字内容（代替视频）")
    return parser


def main():
    args = build_parser().parse_args()

    # --- Web 界面模式 ---
    if args.web:
        try:
            from web.app import app, OUTPUT_DIR
            import webbrowser
            print(f"\n🌐 启动 Web 界面 → http://127.0.0.1:{args.web_port}")
            print(f"   按 Ctrl+C 停止\n")
            # 自动打开浏览器
            webbrowser.open(f"http://127.0.0.1:{args.web_port}")
            app.run(host="127.0.0.1", port=args.web_port, debug=False)
        except ImportError as e:
            print(f"❌ 无法启动 Web 界面: {e}")
            print("   请先安装 Flask: py -3.12 -m pip install flask")
            sys.exit(1)
        return

    # 检查视频文件（--optimize --text 模式可无视频）
    if not args.video and not (args.optimize and args.text):
        print("❌ 请指定视频文件")
        print(f"\n用法:")
        print(f"   python run.py <视频路径>             运行管线")
        print(f"   python run.py <视频路径> --export     管线 + 导出")
        print(f"   python run.py --web                   启动 Web 预览界面")
        print(f"   python run.py --optimize --text \"...\"  文字内容优化")
        sys.exit(1)
    if args.video and not os.path.exists(args.video):
        print(f"❌ 找不到视频文件: {args.video}")
        print(f"\n💡 请将视频放入 input/ 目录，然后运行:")
        print(f"   python run.py input/你的视频.mp4")
        sys.exit(1)

    # 检查 API Key
    if not os.environ.get("DASHSCOPE_API_KEY"):
        print("❌ 未设置 DASHSCOPE_API_KEY")
        print("   请在 .env 文件中配置 API Key")
        sys.exit(1)

    # --- 内容优化模式 ---
    if args.optimize:
        import json as _json
        from engine.advisor import ContentAdvisor

        print("🚀 内容优化模式...")
        advisor = ContentAdvisor(work_dir=args.work_dir)
        plan = advisor.build_plan(
            video_path=args.video,
            text=args.text or None,
            city=args.city,
        )
        print(_json.dumps(plan, ensure_ascii=False, indent=2))
        if plan.get("error"):
            sys.exit(1)
        return

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
        skip_llm=skip_all or args.skip_llm,
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
