"""engine/asr.py 验证脚本（mock funasr，不下载模型）

用法:
    py -3.12 tests/test_asr.py
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent.parent))


def green(s): return f"[PASS] {s}"
def red(s): return f"[FAIL] {s}"
def header(s): return f"\n{'='*60}\n  {s}\n{'='*60}"


def _reset_model():
    """重置模块级模型单例，避免测试间污染。"""
    from engine import asr as asr_mod
    asr_mod._MODEL = None


def _sentence(start_ms: int, end_ms: int, text: str) -> dict:
    return {"start": start_ms, "end": end_ms, "text": text, "sentence": text}


def test_load_hotwords_contains_topics_and_aliases():
    from engine.asr import load_hotwords
    hotwords = load_hotwords()
    for w in ["倒车入库", "倒库", "侧方停车", "侧方位", "直角转弯",
              "曲线行驶", "S弯", "坡道定点停车与起步", "夜间灯光操作", "U型弯"]:
        assert w in hotwords, f"热词表缺少: {w}"
    return True


def test_load_hotwords_no_duplicates_and_no_short_words():
    from engine.asr import load_hotwords
    hotwords = load_hotwords()
    assert len(hotwords) == len(set(hotwords)), "热词表存在重复"
    assert all(len(w) >= 2 for w in hotwords), "热词表包含 <2 字的过短词"
    return True


def test_transcribe_parses_sentence_info_to_seconds():
    _reset_model()
    from engine.asr import SenseVoiceASR
    fake_model = mock.Mock()
    fake_model.generate.return_value = [{
        "sentence_info": [
            _sentence(16690, 24990, "对准第二个空格中间"),
            _sentence(61270, 64110, "像我刚才跟你说的那个位置"),
        ],
    }]
    asr = SenseVoiceASR()
    with mock.patch.object(asr, "_get_model", return_value=fake_model):
        segs = asr.transcribe("work/audio.wav")
    assert segs == [
        {"start": 16.69, "end": 24.99, "text": "对准第二个空格中间"},
        {"start": 61.27, "end": 64.11, "text": "像我刚才跟你说的那个位置"},
    ]
    return True


def test_transcribe_filters_empty_text_and_sorts():
    _reset_model()
    from engine.asr import SenseVoiceASR
    fake_model = mock.Mock()
    fake_model.generate.return_value = [{
        "sentence_info": [
            _sentence(1000, 2000, ""),
            _sentence(5000, 6000, "后来的一句话"),
            _sentence(3000, 4000, "前面的一句话"),
        ],
    }]
    asr = SenseVoiceASR()
    with mock.patch.object(asr, "_get_model", return_value=fake_model):
        segs = asr.transcribe("work/audio.wav")
    assert [s["text"] for s in segs] == ["前面的一句话", "后来的一句话"]
    return True


def test_transcribe_passes_hotwords_and_itn_flags():
    _reset_model()
    from engine.asr import SenseVoiceASR
    fake_model = mock.Mock()
    fake_model.generate.return_value = [{"sentence_info": [_sentence(0, 1000, "侧方停车请准备好")]}]
    asr = SenseVoiceASR()
    with mock.patch.object(asr, "_get_model", return_value=fake_model):
        asr.transcribe("work/audio.wav")
    _, kwargs = fake_model.generate.call_args
    assert kwargs["sentence_timestamp"] is True
    assert kwargs["use_itn"] is True
    assert "倒车入库" in kwargs["postprocess_hotwords"]
    return True


def test_model_is_singleton():
    _reset_model()
    from engine.asr import SenseVoiceASR
    fake_model = mock.Mock()
    asr = SenseVoiceASR()
    with mock.patch("funasr.AutoModel", return_value=fake_model) as AM:
        m1 = asr._get_model()
        m2 = asr._get_model()
    assert m1 is m2 is fake_model
    assert AM.call_count == 1
    return True


def test_model_load_failure_raises_clear_error():
    _reset_model()
    from engine.asr import SenseVoiceASR
    asr = SenseVoiceASR()
    try:
        with mock.patch("funasr.AutoModel", side_effect=OSError("conn refused")):
            asr._get_model()
    except RuntimeError as e:
        assert "ASR 模型加载失败" in str(e)
        return True
    raise AssertionError("预期抛出 RuntimeError（ASR 模型加载失败）")


def test_transcribe_raises_clear_error_on_generate_failure():
    _reset_model()
    from engine.asr import SenseVoiceASR
    fake_model = mock.Mock()
    fake_model.generate.side_effect = Exception("infer failed")
    asr = SenseVoiceASR()
    try:
        with mock.patch.object(asr, "_get_model", return_value=fake_model):
            asr.transcribe("work/audio.wav")
    except RuntimeError as e:
        assert "ASR 识别失败" in str(e)
        return True
    raise AssertionError("预期抛出 RuntimeError（ASR 识别失败）")


def test_run_asr_uses_sensevoice_and_writes_schema():
    _reset_model()
    from engine.pipeline import Pipeline
    with tempfile.TemporaryDirectory() as td:
        p = Pipeline("input/PNIK4383.MOV", output_dir=td, work_dir=td)
        (Path(td) / "audio.wav").write_bytes(b"fake")
        fake = mock.Mock()
        fake.transcribe.return_value = [{"start": 0.0, "end": 1.2, "text": "侧方停车请准备好"}]
        with mock.patch("engine.asr.SenseVoiceASR", return_value=fake):
            p._run_asr()
        data = json.loads((Path(td) / "asr_result.json").read_text(encoding="utf-8"))
        assert data["segments"] == [{"start": 0.0, "end": 1.2, "text": "侧方停车请准备好"}]
        assert data["total"] == 1
        fake.transcribe.assert_called_once()
    return True


def test_postprocess_asr_filters_filler_and_merges_dupes():
    from engine.pipeline import Pipeline
    with tempfile.TemporaryDirectory() as td:
        p = Pipeline("input/PNIK4383.MOV", output_dir=td, work_dir=td)
        segs = [
            {"start": 0.0, "end": 0.2, "text": "啊"},
            {"start": 1.0, "end": 2.0, "text": "侧方停车请准备好"},
            {"start": 1.5, "end": 2.5, "text": "侧方停车请准备好"},
            {"start": 3.0, "end": 3.1, "text": "嗯"},
            {"start": 5.0, "end": 6.0, "text": ""},
        ]
        out = p._postprocess_asr(segs)
        assert len(out) == 1
        assert out[0]["text"] == "侧方停车请准备好"
        assert out[0]["end"] == 2.5
    return True


def main():
    tests = [(name, fn) for name, fn in globals().items()
             if name.startswith("test_") and callable(fn)]
    results = {}
    for name, fn in tests:
        print(header(name))
        try:
            results[name] = bool(fn())
        except Exception:
            import traceback
            traceback.print_exc()
            results[name] = False
    passed = sum(1 for v in results.values() if v)
    print(f"\n{'='*60}\n  验证结果: {passed}/{len(results)} 通过\n{'='*60}")
    for name, ok in results.items():
        print(f"  {green('✓') if ok else red('✗')} {name}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
