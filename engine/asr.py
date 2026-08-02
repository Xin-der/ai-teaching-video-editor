"""
SenseVoice ASR 模块 — 抗噪转录 + 驾考热词纠错

供 engine/pipeline.py 调用，输出与旧 paraformer 一致的 schema：[{start, end, text}] 秒。
模型为进程级单例，Web 多请求不重复加载。

用法:
    from engine.asr import SenseVoiceASR
    asr = SenseVoiceASR()
    segments = asr.transcribe("work/audio.wav")   # [{start, end, text}]
"""

import json
from pathlib import Path

# knowledge/ 相对本文件上一级
_KNOWLEDGE_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "driving_exam.json"

_MODEL = None  # 进程级单例


def load_hotwords() -> list:
    """从驾考知识库 high_frequency_topics 提取 topic + aliases 作为热词表。

    去重保序，过滤空串与 <2 字的过短词（过短热词易误纠）。
    """
    with open(_KNOWLEDGE_PATH, "r", encoding="utf-8") as f:
        kb = json.load(f)

    words = []
    for t in kb.get("high_frequency_topics", []):
        topic = (t.get("topic") or "").strip()
        if topic:
            words.append(topic)
        for alias in t.get("aliases", []) or []:
            alias = (alias or "").strip()
            if alias:
                words.append(alias)

    seen = set()
    result = []
    for w in words:
        if len(w) < 2 or w in seen:
            continue
        seen.add(w)
        result.append(w)
    return result


class SenseVoiceASR:
    """SenseVoice-Small + fsmn-vad 转录，返回秒级 [{start, end, text}]。"""

    def _get_model(self):
        """懒加载模型；进程内复用（模块级单例）。"""
        global _MODEL
        if _MODEL is None:
            print("  首次加载 SenseVoice 模型 (iic/SenseVoiceSmall + fsmn-vad)...")
            try:
                from funasr import AutoModel
                _MODEL = AutoModel(
                    model="iic/SenseVoiceSmall",
                    vad_model="fsmn-vad",
                    trust_remote_code=True,
                )
            except Exception as e:
                raise RuntimeError(
                    "ASR 模型加载失败（请检查网络可访问 modelscope 后重试）: "
                    f"{type(e).__name__}: {e}"
                ) from e
        return _MODEL

    def transcribe(self, audio_path: str) -> list:
        """对音频文件做 SenseVoice 转录，返回 [{start, end, text}]（秒）。

        时间戳来自 fsmn-vad 句子级分段（sentence_info，毫秒），转为秒。
        """
        model = self._get_model()
        hotwords = load_hotwords()

        try:
            results = model.generate(
                input=audio_path,
                sentence_timestamp=True,
                use_itn=True,
                postprocess_hotwords=hotwords,
            )
        except Exception as e:
            raise RuntimeError(f"ASR 识别失败: {type(e).__name__}: {e}") from e

        segments = []
        for r in results or []:
            for s in r.get("sentence_info", []) or []:
                text = (s.get("text") or s.get("sentence") or "").strip()
                if not text:
                    continue
                segments.append({
                    "start": round(s["start"] / 1000.0, 2),
                    "end": round(s["end"] / 1000.0, 2),
                    "text": text,
                })

        segments.sort(key=lambda x: x["start"])
        return segments
