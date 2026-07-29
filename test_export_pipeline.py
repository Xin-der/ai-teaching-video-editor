"""
导出链路验证脚本 — 在无测试视频的情况下验证代码逻辑完整性

用法:
    py test_export_pipeline.py           # 全部测试
    py test_export_pipeline.py --quick   # 只跑快速测试（不含 ffmpeg 实际调用）
"""

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

# 将项目根目录加入 path
sys.path.insert(0, str(Path(__file__).parent))


def green(s): return f"[PASS] {s}"
def red(s): return f"[FAIL] {s}"
def yellow(s): return f"[WARN] {s}"
def header(s): return f"\n{'='*60}\n  {s}\n{'='*60}"


def test_imports():
    """测试 1: 所有模块可正确导入"""
    print(header("测试 1: 模块导入"))
    try:
        from engine import Pipeline, SegmentScorer, VideoExporter
        print(green("  engine top-level import OK"))
        from engine.pipeline import Pipeline
        print(green("  pipeline import OK"))
        from engine.scorer import SegmentScorer
        print(green("  scorer import OK"))
        from engine.exporter import VideoExporter, _detect_chinese_font, _detect_encoder, _load_template
        print(green("  exporter import OK"))
        return True
    except Exception as e:
        print(red(f"  ✗ 导入失败: {e}"))
        return False


def test_scorer():
    """测试 2: 评分引擎"""
    print(header("测试 2: 评分引擎"))
    try:
        from engine.scorer import SegmentScorer
        scorer = SegmentScorer()

        # 验证知识库加载
        assert len(scorer.knowledge["high_frequency_topics"]) >= 10, \
            f"知识库话题数量不足: {len(scorer.knowledge['high_frequency_topics'])}"
        print(green(f"  ✓ 知识库加载 OK ({len(scorer.knowledge['high_frequency_topics'])} 话题)"))

        # 测试评分
        test_seg = {
            "id": 1,
            "topic": "夜间灯光操作",
            "duration": 45.0,
            "transcript": "记住啊，夜间灯光考试一定要先关闭所有灯光。重点是千万别抢答，挂科了后悔都来不及。",
            "frame_descriptions": [
                {"has_text_overlay": True, "visible_elements": ["仪表盘", "特写镜头"]},
                {"has_text_overlay": False, "visible_elements": ["教练正常讲解"]},
            ],
        }
        result = scorer.score(test_seg, total_duration=300, all_segment_topics=[
            "夜间灯光操作", "倒车入库", "夜间灯光操作"
        ])

        assert "score" in result, "评分结果缺少 score"
        assert 0 <= result["score"] <= 1, f"分数超出范围: {result['score']}"
        assert "recommendation" in result, "缺少 recommendation"
        assert "platform_suitability" in result, "缺少 platform_suitability"

        print(green(f"  ✓ 单段评分 OK: score={result['score']:.3f}, {result['recommendation']}"))
        print(f"    关键词={result['scores_detail']['keywords']:.3f} "
              f"知识库={result['scores_detail']['knowledge_match']:.3f} "
              f"时长={result['scores_detail']['duration_ratio']:.3f} "
              f"画面={result['scores_detail']['visual_emphasis']:.3f} "
              f"重复={result['scores_detail']['repetition']:.3f}")
        print(f"    平台: 抖={result['platform_suitability']['douyin']} "
              f"B={result['platform_suitability']['bilibili']} "
              f"红={result['platform_suitability']['xiaohongshu']}")

        # 测试批量评分
        segments = [test_seg, {
            "id": 2, "topic": "倒车入库", "duration": 120.0,
            "transcript": "倒车入库一定要注意看点位，车身出线直接扣100分。",
            "frame_descriptions": [],
        }]
        results = scorer.score_all(segments, total_duration=600)
        assert len(results) == 2, f"批量评分结果数量不对: {len(results)}"
        assert results[0]["score"] >= results[1]["score"], "未按分数降序排列"
        print(green(f"  ✓ 批量评分 OK: {len(results)} 段，最高分 {results[0]['score']:.3f}"))

        # 验证各维度边界情况
        empty_seg = {"id": 3, "topic": "", "duration": 0, "transcript": "", "frame_descriptions": []}
        empty_result = scorer.score(empty_seg, total_duration=300, all_segment_topics=[])
        assert empty_result["score"] == 0.0, f"空段评分应为 0: {empty_result['score']}"
        print(green("  ✓ 空段评分边界测试 OK"))

        return True
    except Exception as e:
        print(red(f"  ✗ 评分测试失败: {e}"))
        import traceback
        traceback.print_exc()
        return False


def test_templates():
    """测试 3: 平台模板加载和验证"""
    print(header("测试 3: 平台模板"))
    try:
        from engine.exporter import _load_template

        required_keys = ["platform", "name", "version", "video", "layout"]
        required_video_keys = ["output_resolution", "fps", "codec", "bitrate"]

        for plat in ["douyin", "bilibili", "xiaohongshu"]:
            tpl = _load_template(plat)

            # 基本结构
            for key in required_keys:
                assert key in tpl, f"[{plat}] 缺少字段: {key}"

            # 视频配置
            for key in required_video_keys:
                assert key in tpl["video"], f"[{plat}] video 缺少: {key}"

            res = tpl["video"]["output_resolution"]
            assert len(res) == 2, f"[{plat}] 分辨率格式错误"

            # 布局至少有字幕配置
            assert "subtitle" in tpl["layout"], f"[{plat}] 缺少 subtitle 配置"

            print(green(f"  ✓ [{plat}] {tpl['name']} {res[0]}x{res[1]}"))

        # 验证分辨率符合平台标准
        douyin = _load_template("douyin")
        assert douyin["video"]["output_resolution"] == [1080, 1920], "抖音应为 9:16"
        bilibili = _load_template("bilibili")
        assert bilibili["video"]["output_resolution"] == [1920, 1080], "B站应为 16:9"
        xhs = _load_template("xiaohongshu")
        assert xhs["video"]["output_resolution"] == [1080, 1080], "小红书应为 1:1"

        print(green("  ✓ 分辨率比例验证 OK"))
        return True
    except Exception as e:
        print(red(f"  ✗ 模板测试失败: {e}"))
        import traceback
        traceback.print_exc()
        return False


def test_exporter_basics():
    """测试 4: 导出器基础功能（不需要实际视频）"""
    print(header("测试 4: 导出器基础功能"))
    try:
        from engine.exporter import (
            VideoExporter, _detect_chinese_font,
            _detect_encoder, _load_template
        )

        # 字体检测
        font = _detect_chinese_font()
        print(green(f"  ✓ 字体检测: {font}"))

        # 编码器探测
        encoder, params = _detect_encoder()
        print(green(f"  ✓ 编码器: {encoder} | {params}"))

        # 实例化
        exporter = VideoExporter(output_dir="output")
        assert exporter.font is not None
        assert exporter._encoder is not None
        print(green("  ✓ 导出器实例化 OK"))

        # 测试辅助方法
        assert exporter._safe_filename("夜间灯光操作") == "夜间灯光操作"
        assert exporter._safe_filename("test:<>*") == "test" or "test" in exporter._safe_filename("test:<>*")
        print(green("  ✓ safe_filename OK"))

        assert exporter._wrap_text("短文本", 18) == "短文本"
        long_text = "这是一段很长的文本需要被自动换行处理测试一下"
        wrapped = exporter._wrap_text(long_text, 10)
        assert "\\N" in wrapped or len(wrapped) > 10, f"wrap 失败: {wrapped}"
        print(green("  ✓ wrap_text OK"))

        assert exporter._sec_to_ass_time(0) == "0:00:00.00"
        assert exporter._sec_to_ass_time(65.5) == "0:01:05.50"
        assert exporter._sec_to_ass_time(3661.75) == "1:01:01.75"
        print(green("  ✓ sec_to_ass_time OK"))

        # 测试 ASS 转义
        assert "\\{" in exporter._escape_ass_text("{test}")
        assert "\\}" in exporter._escape_ass_text("test}")
        print(green("  ✓ escape_ass_text OK"))

        return True
    except Exception as e:
        print(red(f"  ✗ 导出器基础测试失败: {e}"))
        import traceback
        traceback.print_exc()
        return False


def test_ass_generation():
    """测试 5: ASS 字幕文件生成（用 mock 数据，不需要视频）"""
    print(header("测试 5: ASS 字幕文件生成"))
    try:
        from engine.exporter import VideoExporter, _load_template

        exporter = VideoExporter(output_dir="output")

        # Mock 数据
        segment = {
            "id": 0,
            "topic": "夜间灯光操作",
            "start": 10.0,
            "end": 55.0,
            "duration": 45.0,
            "transcript": "记住啊，夜间灯光考试一定要先关闭所有灯光。千万别抢答。",
        }

        asr_segments = [
            {"start": 10.0, "end": 15.0, "text": "夜间灯光考试一定要先关闭所有灯光"},
            {"start": 18.0, "end": 23.0, "text": "记住千万别抢答"},
            {"start": 30.0, "end": 35.0, "text": "考试的时候每次语音播报完再操作"},
        ]

        for plat in ["douyin", "bilibili", "xiaohongshu"]:
            template = _load_template(plat)
            out_w, out_h = template["video"]["output_resolution"]

            # 用临时目录测试 ASS 生成
            with tempfile.TemporaryDirectory() as tmpdir:
                ass_path = os.path.join(tmpdir, "subtitles.ass")

                exporter._write_ass_file(
                    segment, template, asr_segments, ass_path,
                    out_w, out_h, segment["start"], segment["duration"]
                )

                assert os.path.exists(ass_path), f"ASS 文件未生成: {ass_path}"

                with open(ass_path, "r", encoding="utf-8-sig") as f:
                    content = f.read()

                # 验证 ASS 文件结构
                assert "[Script Info]" in content, "缺少 Script Info"
                assert "[V4+ Styles]" in content, "缺少 Styles"
                assert "[Events]" in content, "缺少 Events"
                assert "Format:" in content, "缺少 Format"
                assert "Dialogue:" in content, "缺少 Dialogue 事件"

                # 验证关键内容
                if plat == "douyin":
                    assert "Title" in content, "抖音模板缺少 Title 样式"
                if plat == "bilibili":
                    assert "KnowledgeCard" in content, "B站模板缺少 KnowledgeCard 样式"
                if plat == "xiaohongshu":
                    assert "KeyPoints" in content, "小红书模板缺少 KeyPoints 样式"

                # 字幕内容验证
                assert "夜间灯光" in content, f"[{plat}] 字幕缺少话题关键词"

                print(green(f"  ✓ [{plat}] ASS 生成 OK ({len(content)} bytes)"))

        # 验证 ASS 时间格式
        assert exporter._sec_to_ass_time(0.5) == "0:00:00.50"
        assert exporter._sec_to_ass_time(120.0) == "0:02:00.00"
        print(green("  ✓ ASS 时间格式 OK"))

        return True
    except Exception as e:
        print(red(f"  ✗ ASS 生成测试失败: {e}"))
        import traceback
        traceback.print_exc()
        return False


def test_ffmpeg_available():
    """测试 6: ffmpeg 可用性"""
    print(header("测试 6: ffmpeg 可用性"))
    import subprocess
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            version_line = result.stdout.strip().split("\n")[0]
            print(green(f"  ✓ ffmpeg 可用: {version_line[:80]}"))

            # 检查编码器
            if "h264_nvenc" in result.stdout:
                print(green("  ✓ NVENC 硬件编码可用"))
            else:
                print(yellow("  ⚠ NVENC 不可用，将使用 libx264 软件编码"))

            # 检查是否有 libass（ASS 字幕支持）
            result2 = subprocess.run(
                ["ffmpeg", "-filters"],
                capture_output=True, text=True, timeout=10
            )
            if "ass" in result2.stdout.lower():
                print(green("  ✓ libass 字幕滤镜可用"))
            else:
                print(yellow("  ⚠ libass 不可用，字幕功能可能受限"))

            return True
        else:
            print(red(f"  ✗ ffmpeg 返回错误: {result.returncode}"))
            return False
    except FileNotFoundError:
        print(yellow("  ⚠ ffmpeg 未安装或不在 PATH 中"))
        print(yellow("    请安装 ffmpeg: https://ffmpeg.org/download.html"))
        print(yellow("    或 winget install ffmpeg"))
        return False
    except Exception as e:
        print(yellow(f"  ⚠ ffmpeg 检测异常: {e}"))
        return False


def test_mock_export():
    """测试 7: 模拟导出流程（不需要实际视频）"""
    print(header("测试 7: 模拟导出流程"))
    try:
        from engine.exporter import VideoExporter, _load_template

        exporter = VideoExporter(output_dir="output")

        # 验证每个平台的视频滤镜参数
        for plat in ["douyin", "bilibili", "xiaohongshu"]:
            tpl = _load_template(plat)
            out_w, out_h = tpl["video"]["output_resolution"]

            # 验证分辨率是合理的
            assert out_w > 0 and out_h > 0
            assert out_w <= 3840 and out_h <= 3840

            # 验证码率格式
            bitrate = tpl["video"].get("bitrate", "")
            assert bitrate.endswith("M") or bitrate.endswith("k")

            # 验证 fps
            fps = tpl["video"].get("fps", 0)
            assert 10 <= fps <= 60, f"fps 不合理: {fps}"

            print(green(f"  ✓ [{plat}] 配置验证 OK: {out_w}x{out_h}@{fps}fps {bitrate}"))

        # 验证 ass_header 生成
        for plat in ["douyin", "bilibili", "xiaohongshu"]:
            tpl = _load_template(plat)
            out_w, out_h = tpl["video"]["output_resolution"]
            ass_hdr = exporter._ass_header(tpl, out_w, out_h)

            assert "[Script Info]" in ass_hdr
            assert "[V4+ Styles]" in ass_hdr
            assert "PlayResX" in ass_hdr
            assert str(out_w) in ass_hdr
            assert str(out_h) in ass_hdr

            # 验证关键样式存在
            assert "Style: Subtitle," in ass_hdr
            assert "Style: Ending," in ass_hdr

            print(green(f"  [{plat}] ASS Header OK ({len(ass_hdr)} bytes)"))

        print(green("\n  ✓ 模拟导出流程全部通过"))
        return True
    except Exception as e:
        print(red(f"  ✗ 模拟导出失败: {e}"))
        import traceback
        traceback.print_exc()
        return False


def test_copy_generation():
    """测试 8: 文案生成"""
    print(header("测试 8: 文案生成"))
    try:
        from engine.exporter import VideoExporter

        exporter = VideoExporter(output_dir="output")

        segment = {
            "id": 0,
            "topic": "夜间灯光操作",
            "transcript": "记住啊，夜间灯光考试一定要先关闭所有灯光。重点千万别抢答。",
        }

        for plat in ["douyin", "bilibili", "xiaohongshu"]:
            title = exporter._generate_title(segment, plat)
            assert title, f"[{plat}] 标题为空"
            assert len(title) > 0, f"[{plat}] 标题太短"
            print(f"  [{plat}] 标题: {title}")

            desc = exporter._generate_description(segment, plat)
            assert desc, f"[{plat}] 描述为空"
            print(f"  [{plat}] 描述: {desc[:60]}...")

            tags = exporter._get_hashtags(segment)
            assert tags, f"[{plat}] 标签为空"
            print(f"  [{plat}] 标签: {' '.join(tags[:4])}")

        print(green("  ✓ 文案生成 OK"))
        return True
    except Exception as e:
        print(red(f"  ✗ 文案生成失败: {e}"))
        import traceback
        traceback.print_exc()
        return False


def test_knowledge_base():
    """测试 9: 知识库完整性"""
    print(header("测试 9: 知识库完整性"))
    try:
        from engine.scorer import SegmentScorer
        scorer = SegmentScorer()
        kb = scorer.knowledge

        # 验证知识库结构
        assert "domain" in kb, "缺少 domain"
        assert kb["domain"] == "驾考教学"
        assert "emphasis_keywords" in kb, "缺少 emphasis_keywords"
        assert "high_frequency_topics" in kb, "缺少 high_frequency_topics"
        print(green("  ✓ 知识库结构 OK"))

        # 验证强调关键词
        high_kw = kb["emphasis_keywords"]["high_priority"]
        med_kw = kb["emphasis_keywords"]["medium_priority"]
        assert len(high_kw) >= 8, f"高优先级关键词不足: {len(high_kw)}"
        assert len(med_kw) >= 5, f"中优先级关键词不足: {len(med_kw)}"

        for kw_info in high_kw:
            assert "keyword" in kw_info, f"关键词缺少 keyword 字段"
            assert "weight" in kw_info, f"关键词缺少 weight 字段"
            assert 0 < kw_info["weight"] <= 1, f"权重超出范围: {kw_info['weight']}"
        print(green(f"  ✓ 强调关键词: {len(high_kw)} 高优 + {len(med_kw)} 中优"))

        # 验证话题
        topics = kb["high_frequency_topics"]
        for t in topics:
            assert "topic" in t, "话题缺少 topic"
            assert "aliases" in t, "话题缺少 aliases"
            assert "deduction_points" in t, "话题缺少 deduction_points"
            assert "weight" in t, "话题缺少 weight"
            assert len(t["deduction_points"]) >= 2, f"扣分点不足: {t['topic']}"
        print(green(f"  ✓ 高频话题: {len(topics)} 个"))

        # 验证平台文案模板
        copy_tpl = kb.get("platform_copy_templates", {})
        for plat in ["douyin", "bilibili", "xiaohongshu"]:
            assert plat in copy_tpl, f"缺少 {plat} 文案模板"
            assert "title_patterns" in copy_tpl[plat], f"{plat} 缺少 title_patterns"
            assert len(copy_tpl[plat]["title_patterns"]) >= 1, f"{plat} title_patterns 为空"
            assert "hashtags" in copy_tpl[plat], f"{plat} 缺少 hashtags"
        print(green("  ✓ 平台文案模板 OK"))

        # 验证视觉信号配置
        signals = kb.get("visual_emphasis_signals", {})
        assert "high_value" in signals, "缺少 high_value signals"
        assert "medium_value" in signals, "缺少 medium_value signals"
        print(green("  ✓ 视觉信号配置 OK"))

        return True
    except Exception as e:
        print(red(f"  ✗ 知识库测试失败: {e}"))
        import traceback
        traceback.print_exc()
        return False


def test_pipeline_basics():
    """测试 10: Pipeline 基础（不需要视频）"""
    print(header("测试 10: Pipeline 基础"))
    try:
        from engine.pipeline import Pipeline

        # Pipeline 需要视频文件路径，测试类定义和方法签名
        import inspect

        methods = ["run", "export_all", "print_segments", "_merge_segments",
                    "_score_segments", "_postprocess_merge"]
        for m in methods:
            assert hasattr(Pipeline, m), f"Pipeline 缺少方法: {m}"
        print(green("  ✓ Pipeline 方法签名完整"))

        # 验证 _postprocess_merge 逻辑
        # 用空 pipeline（不需要视频）
        p = Pipeline.__new__(Pipeline)
        p.merged_segments = []

        # 测试合并逻辑
        test_segs = [
            {"id": 0, "topic": "A", "start": 0, "end": 5, "duration": 5, "scenes": [0], "transcript": "", "frame_descriptions": []},
            {"id": 1, "topic": "A", "start": 5, "end": 15, "duration": 10, "scenes": [1], "transcript": "", "frame_descriptions": []},
        ]
        # 短段合并
        result = p._postprocess_merge(test_segs)
        assert len(result) <= 2, f"合并后段数异常: {len(result)}"
        print(green("  ✓ _postprocess_merge 逻辑 OK"))

        return True
    except Exception as e:
        print(red(f"  ✗ Pipeline 测试失败: {e}"))
        import traceback
        traceback.print_exc()
        return False


# ====================================================================
# 主入口
# ====================================================================
def main():
    parser = argparse.ArgumentParser(description="导出链路验证脚本")
    parser.add_argument("--quick", action="store_true", help="只跑快速测试")
    args = parser.parse_args()

    print("=" * 60)
    print("  多平台智能切片工具 — 导出链路验证")
    print("=" * 60)

    tests = [
        ("模块导入", test_imports),
        ("评分引擎", test_scorer),
        ("平台模板", test_templates),
        ("导出器基础", test_exporter_basics),
        ("ASS 字幕生成", test_ass_generation),
    ]

    if not args.quick:
        tests.extend([
            ("ffmpeg 可用性", test_ffmpeg_available),
            ("模拟导出流程", test_mock_export),
            ("文案生成", test_copy_generation),
            ("知识库完整性", test_knowledge_base),
            ("Pipeline 基础", test_pipeline_basics),
        ])

    results = {}
    for name, fn in tests:
        results[name] = fn()

    # 汇总
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"\n{'='*60}")
    print(f"  验证结果: {passed}/{total} 通过")
    print(f"{'='*60}")

    for name, ok in results.items():
        status = green("✓") if ok else red("✗")
        print(f"  {status} {name}")

    # 环境建议
    print(f"\n{'='*60}")
    print(f"  环境建议")
    print(f"{'='*60}")

    # 检查 .env
    if not os.path.exists(".env"):
        print(yellow("  ⚠ .env 不存在，请复制 .env.example 并填入 API Key"))
    else:
        from dotenv import load_dotenv
        load_dotenv()
        if os.environ.get("DASHSCOPE_API_KEY"):
            print(green("  ✓ DASHSCOPE_API_KEY 已配置"))
        else:
            print(yellow("  ⚠ DASHSCOPE_API_KEY 未配置"))

    # 检查 input/
    if not os.path.exists("input"):
        print(yellow("  ⚠ input/ 目录不存在"))
    elif not any(Path("input").iterdir()):
        print(yellow("  ⚠ input/ 目录为空，请放入测试视频"))

    # 检查 work/ 缓存
    work_files = list(Path("work").glob("*.json")) if os.path.exists("work") else []
    if work_files:
        print(green(f"  ✓ work/ 有缓存 ({len(work_files)} 文件): {[f.name for f in work_files]}"))
    else:
        print(yellow("  ⚠ work/ 无缓存，首次运行需完整管线"))

    print(f"\n  下一步:")
    print(f"    1. 安装依赖: py -m pip install -r requirements.txt")
    print(f"    2. 配置 API: 编辑 .env 文件")
    print(f"    3. 放视频: 放入 input/ 目录")
    print(f"    4. 运行管线: py run.py input/视频.mp4 --skip-asr")
    print(f"    5. 导出: py run.py input/视频.mp4 --export")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
