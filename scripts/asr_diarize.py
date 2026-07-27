"""
替代 FunClip Stage 1：中文语音识别 + 说话人分离

FunClip 的核心功能是对 FunASR Paraformer + CAM++ 的封装。
由于 GitHub 在部分地区不可达，本脚本直接用 FunASR 实现相同功能。

用法:
    python scripts/asr_diarize.py --input "input/video.mp4" --output "work/asr_result.json"
"""

import os
import sys
import json
import argparse
import subprocess
import tempfile
from pathlib import Path


def extract_audio(video_path: str, audio_path: str) -> None:
    """用 ffmpeg 从视频提取音频（16kHz mono WAV，FunASR 需要）"""
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn",                      # 不要视频
        "-acodec", "pcm_s16le",     # PCM 16-bit
        "-ar", "16000",             # 16kHz 采样率
        "-ac", "1",                 # 单声道
        "-y",                       # 覆盖已有文件
        audio_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    print(f"  音频已提取: {audio_path}")


def run_asr(audio_path: str, output_path: str, model_name: str = "paraformer-zh") -> list[dict]:
    """
    运行 FunASR Paraformer 中文语音识别。
    返回: [{"start": float, "end": float, "text": str}, ...]
    """
    from funasr import AutoModel

    print(f"  正在加载 FunASR 模型: {model_name}...")
    model = AutoModel(
        model=model_name,
        vad_model="fsmn-vad",       # 语音活动检测（自动切句子）
        punc_model="ct-punc",       # 标点恢复
        model_revision="v2.0.4",
    )

    print(f"  正在转写音频...")
    result = model.generate(input=audio_path)

    segments = []
    if result and len(result) > 0:
        for item in result[0].get("sentence_info", []):
            segments.append({
                "start": round(item["start"] / 1000.0, 2),  # ms -> seconds
                "end": round(item["end"] / 1000.0, 2),
                "text": item["text"].strip()
            })

    print(f"  转写完成: {len(segments)} 个句子")
    return segments


def run_speaker_diarization(audio_path: str, segments: list[dict]) -> list[dict]:
    """
    运行 CAM++ 说话人分离，为每个语音段标注说话人。
    """
    from funasr import AutoModel

    print(f"  正在加载说话人分离模型: CAM++...")
    model = AutoModel(
        model="cam++",
        model_revision="v1.0.2",
    )

    print(f"  正在识别说话人...")
    result = model.generate(input=audio_path)

    if result and len(result) > 0:
        speaker_info = result[0].get("sentence_info", [])
        # 将说话人标签合并到 ASR 段
        for i, seg in enumerate(segments):
            seg["speaker"] = "speaker_0"  # 默认
            # 根据时间戳匹配说话人
            for spk in speaker_info:
                spk_start = spk["start"] / 1000.0
                spk_end = spk["end"] / 1000.0
                # 如果时间段重叠 > 50%，分配给该说话人
                overlap = min(seg["end"], spk_end) - max(seg["start"], spk_start)
                if overlap > 0 and overlap / (seg["end"] - seg["start"]) > 0.5:
                    seg["speaker"] = f"speaker_{spk.get('spk', 0)}"
                    break

    print(f"  说话人识别完成")
    return segments


def main():
    parser = argparse.ArgumentParser(description="FunASR 中文语音识别 + 说话人分离")
    parser.add_argument("--input", required=True, help="输入视频文件路径")
    parser.add_argument("--output", required=True, help="输出 JSON 文件路径")
    parser.add_argument("--skip-speaker", action="store_true", help="跳过说话人分离（更快）")
    args = parser.parse_args()

    video_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not video_path.exists():
        print(f"错误: 找不到文件 {video_path}")
        sys.exit(1)

    print(f"🎤 开始处理: {video_path.name}")
    print(f"   视频大小: {video_path.stat().st_size / 1024 / 1024:.1f} MB")

    # 1. 提取音频
    audio_path = output_path.parent / f"{video_path.stem}_audio.wav"
    print("\n[1/3] 提取音频...")
    extract_audio(str(video_path), str(audio_path))

    # 2. ASR 转写
    print("\n[2/3] 中文语音识别...")
    segments = run_asr(str(audio_path), str(output_path))

    # 3. 说话人分离（可选）
    if not args.skip_speaker:
        print("\n[3/3] 说话人分离...")
        segments = run_speaker_diarization(str(audio_path), segments)

    # 保存结果
    result = {
        "source": str(video_path.absolute()),
        "duration_segments": len(segments),
        "segments": segments
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！结果已保存到: {output_path}")
    print(f"   共 {len(segments)} 个语音段")

    # 清理临时音频
    if audio_path.exists():
        audio_path.unlink()


if __name__ == "__main__":
    main()
