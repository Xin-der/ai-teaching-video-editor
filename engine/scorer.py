"""
片段评分引擎 — 确定性规则打分，不调用 LLM

5 个评分维度:
  1. 关键词密度     30%  — ASR transcript 中强调词出现频率
  2. 知识库匹配     25%  — 片段主题匹配驾考高频扣分点
  3. 时长占比       20%  — 片段时长占总视频比例
  4. 画面强调信号   15%  — VLM 检测到文字叠加/特写/路线图
  5. 重复讲解       10%  — 同一主题在视频中多次出现
"""

import json
import re
from pathlib import Path
from typing import Optional


class SegmentScorer:
    """对单个片段进行多维度评分"""

    def __init__(self, knowledge_path: Optional[str] = None):
        """
        Args:
            knowledge_path: 知识库 JSON 路径，默认使用 knowledge/driving_exam.json
        """
        if knowledge_path is None:
            knowledge_path = str(Path(__file__).parent.parent / "knowledge" / "driving_exam.json")

        with open(knowledge_path, "r", encoding="utf-8") as f:
            self.knowledge = json.load(f)

        # 权重配置（可从模板覆盖）
        self.weights = {
            "keywords": 0.30,
            "knowledge_match": 0.25,
            "duration_ratio": 0.20,
            "visual_emphasis": 0.15,
            "repetition": 0.10,
        }

    # ------------------------------------------------------------------
    # 公开入口
    # ------------------------------------------------------------------

    def score(self, segment: dict, total_duration: float,
              all_segment_topics: Optional[list] = None) -> dict:
        """对单个片段打分

        Args:
            segment: 片段数据，包含 transcript, topic, duration, frame_descriptions
            total_duration: 视频总时长（秒）
            all_segment_topics: 所有片段的话题列表，用于计算重复分

        Returns:
            评分结果 dict，含 score, scores_detail, recommendation, platform_suitability
        """
        transcript = segment.get("transcript", "")
        topic = segment.get("topic", "")
        duration = segment.get("duration", 0)
        frame_descriptions = segment.get("frame_descriptions", [])

        kw_score = self._keyword_density(transcript)
        km_score = self._knowledge_match(topic)
        dr_score = self._duration_ratio(duration, total_duration)
        ve_score = self._visual_emphasis(frame_descriptions)
        rp_score = self._repetition_score(topic, all_segment_topics or [])

        total = (
            kw_score * self.weights["keywords"]
            + km_score * self.weights["knowledge_match"]
            + dr_score * self.weights["duration_ratio"]
            + ve_score * self.weights["visual_emphasis"]
            + rp_score * self.weights["repetition"]
        )

        recommendation = self._recommendation(total)
        platform_suit = self._platform_suitability(total, duration, topic)

        return {
            "segment_id": segment.get("id", -1),
            "topic": topic,
            "score": round(total, 4),
            "scores_detail": {
                "keywords": round(kw_score, 4),
                "knowledge_match": round(km_score, 4),
                "duration_ratio": round(dr_score, 4),
                "visual_emphasis": round(ve_score, 4),
                "repetition": round(rp_score, 4),
            },
            "recommendation": recommendation,
            "platform_suitability": platform_suit,
        }

    def score_all(self, segments: list, total_duration: float) -> list:
        """批量评分"""
        topics = [s.get("topic", "") for s in segments]
        results = []
        for seg in segments:
            results.append(self.score(seg, total_duration, topics))
        # 按分数降序排列
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    # ------------------------------------------------------------------
    # 维度 1: 关键词密度 (30%)
    # ------------------------------------------------------------------

    def _keyword_density(self, transcript: str) -> float:
        """计算 transcript 中强调关键词的加权密度"""
        if not transcript:
            return 0.0

        high_kw = self.knowledge["emphasis_keywords"]["high_priority"]
        med_kw = self.knowledge["emphasis_keywords"]["medium_priority"]

        total_weight = 0.0
        # 按字符数归一化
        char_count = max(len(transcript), 1)

        for kw_info in high_kw + med_kw:
            kw = kw_info["keyword"]
            weight = kw_info["weight"]
            count = len(re.findall(re.escape(kw), transcript))
            total_weight += count * weight

        # 归一化: 密度 = 加权命中数 / 字符数, 然后缩放到 [0, 1]
        density = total_weight / char_count
        # 经验值: density=0.02 算非常密集, 映射到 1.0
        normalized = min(density / 0.02, 1.0)
        return normalized

    # ------------------------------------------------------------------
    # 维度 2: 知识库匹配 (25%)
    # ------------------------------------------------------------------

    def _knowledge_match(self, topic: str) -> float:
        """匹配驾考知识库中的高频话题"""
        if not topic:
            return 0.0

        topic_lower = topic.lower()
        best_score = 0.0

        for entry in self.knowledge["high_frequency_topics"]:
            # 精确匹配主话题
            if entry["topic"] in topic or topic in entry["topic"]:
                best_score = max(best_score, entry["weight"])
                continue

            # 模糊匹配别名
            for alias in entry["aliases"]:
                if alias in topic_lower or topic_lower in alias:
                    # 别名匹配略低于精确匹配
                    best_score = max(best_score, entry["weight"] * 0.85)
                    break

        return best_score

    # ------------------------------------------------------------------
    # 维度 3: 时长占比 (20%)
    # ------------------------------------------------------------------

    def _duration_ratio(self, segment_duration: float, total_duration: float) -> float:
        """片段时长占总视频比例 → 教练花时间讲的就是重点"""
        if total_duration <= 0:
            return 0.0

        ratio = segment_duration / total_duration

        if ratio >= 0.20:
            return 1.0
        elif ratio >= 0.15:
            return 0.85
        elif ratio >= 0.10:
            return 0.6
        elif ratio >= 0.05:
            return 0.35
        else:
            return ratio / 0.05 * 0.35  # 线性插值

    # ------------------------------------------------------------------
    # 维度 4: 画面强调信号 (15%)
    # ------------------------------------------------------------------

    def _visual_emphasis(self, frame_descriptions: list) -> float:
        """VLM 检测到的视觉强调信号"""
        if not frame_descriptions:
            return 0.0

        signals = self.knowledge.get("visual_emphasis_signals", {})
        high_signals = set(signals.get("high_value", []))
        medium_signals = set(signals.get("medium_value", []))

        total_signal = 0.0
        max_possible = len(frame_descriptions) * 1.0  # 每帧最高 1.0 分

        for fd in frame_descriptions:
            frame_signal = 0.0

            # 检查 VLM 输出的各字段
            has_text = fd.get("has_text_overlay", False)
            elements = fd.get("visible_elements", [])
            if isinstance(elements, str):
                elements = [elements]

            # 高价值信号
            if has_text:
                frame_signal += 0.6
            for elem in elements:
                if elem in high_signals:
                    frame_signal += 0.8
                elif elem in medium_signals:
                    frame_signal += 0.4

            frame_signal = min(frame_signal, 1.0)
            total_signal += frame_signal

        if max_possible == 0:
            return 0.0

        return min(total_signal / max_possible, 1.0)

    # ------------------------------------------------------------------
    # 维度 5: 重复讲解 (10%)
    # ------------------------------------------------------------------

    def _repetition_score(self, topic: str, all_topics: list) -> float:
        """同一主题出现多次 → 教练在反复强调"""
        if not topic or not all_topics:
            return 0.0

        # 统计相似 topic 出现的次数
        count = 0
        topic_lower = topic.lower()
        for t in all_topics:
            if not t:
                continue
            t_lower = t.lower()
            # 完全相同或包含关系
            if topic_lower == t_lower or topic_lower in t_lower or t_lower in topic_lower:
                count += 1

        if count >= 4:
            return 1.0
        elif count >= 3:
            return 0.8
        elif count >= 2:
            return 0.5
        else:
            return 0.0

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _recommendation(self, score: float) -> str:
        """根据总分给出推荐等级"""
        if score >= 0.75:
            return "强烈推荐"
        elif score >= 0.55:
            return "推荐"
        elif score >= 0.35:
            return "可选"
        else:
            return "不推荐"

    def _platform_suitability(self, score: float, duration: float, topic: str) -> dict:
        """判断片段适合哪些平台"""
        suit = {}

        # 抖音: 偏好短小精悍 (15-90s) + 高信息密度
        if duration <= 90 and score >= 0.4:
            suit["douyin"] = "高" if score >= 0.6 else "中"
        elif duration <= 120 and score >= 0.5:
            suit["douyin"] = "中"
        else:
            suit["douyin"] = "低"

        # B站: 适合中等长度 + 知识点丰富
        if 30 <= duration <= 180 and score >= 0.35:
            suit["bilibili"] = "高" if score >= 0.55 else "中"
        elif duration > 180:
            suit["bilibili"] = "中"
        else:
            suit["bilibili"] = "低"

        # 小红书: 偏好短 + 步骤清晰
        if duration <= 60 and score >= 0.4:
            suit["xiaohongshu"] = "高" if score >= 0.55 else "中"
        elif duration <= 90 and score >= 0.5:
            suit["xiaohongshu"] = "中"
        else:
            suit["xiaohongshu"] = "低"

        return suit


# ------------------------------------------------------------------
# 快速测试
# ------------------------------------------------------------------
if __name__ == "__main__":
    scorer = SegmentScorer()

    # 模拟一个片段
    test_seg = {
        "id": 1,
        "topic": "夜间灯光操作",
        "duration": 45.0,
        "transcript": "记住啊，夜间灯光考试一定要先关闭所有灯光。重点是千万别抢答，考试的时候每次语音播报完再操作。",
        "frame_descriptions": [
            {"has_text_overlay": True, "visible_elements": ["仪表盘", "特写镜头"]},
            {"has_text_overlay": False, "visible_elements": ["教练正常讲解"]},
        ],
    }

    result = scorer.score(test_seg, total_duration=300, all_segment_topics=["夜间灯光操作", "倒车入库", "夜间灯光操作"])
    print(json.dumps(result, ensure_ascii=False, indent=2))
