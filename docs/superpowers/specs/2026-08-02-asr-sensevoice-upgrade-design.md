# ASR 抗噪升级（SenseVoice）· 设计文档

> 日期: 2026-08-02 | 状态: 已评审

---

## 一、背景与目标

### 为什么做

v3/v3.1 的核心链路「视频 → ASR 转录 → LLM 生成《内容优化方案》」中，**ASR 是当前最弱的一环**：

- 素材是**车内噪音 + 考试播报**叠加的音频（教练边开车边教，车载考试系统同时在播报），信噪比很差。
- 现有引擎 `paraformer-zh`（funasr 解析到 `iic/speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404` v2.0.4，已是语音增强版）依旧碎片化严重。真实样例 `work/asr_result.json`：

  > 「监管对边这个红色点跟防线线切好好好不错撤」
  > 「现在出去招护到了排线的」
  > 「外置个好好现在出去招护到了排线的」

  而同一段音频里考试播报「侧方停车请准备好」「曲线行驶」「直角转弯」反而被识别出来——说明问题出在**教练人声被噪声/播报压住**。

- 目标：把转录从「碎片化、不可读」提升到「教练/老板能直接看懂，LLM 能据此产出靠谱方案」。

### 部署上下文（影响选型）

本工具最终是**网站，部署在普通云服务器（如阿里云 ECS，无 GPU）给教练/驾校用**，不是个人电脑工具。因此 ASR 必须：

1. 无 GPU 也能跑（CPU 够快）；
2. 多用户场景下模型进程级复用（不能每单重载模型）；
3. 为将来多用户规模升级预留路径（但不本期实现）。

### 方案决策

**选定：SenseVoice-Small（本地）+ fsmn-vad + 驾考热词。** 依据：

| 维度 | paraformer-large（现在） | SenseVoice-Small（选定） |
|------|------------------------|------------------------|
| 体积 | ~1GB | ~300MB |
| 无 GPU 速度 | ~0.3~1× 实时 | ~15~30× 实时 |
| 抗噪 | 已增强，仍碎片化 | 专为强噪场景设计，更强 |
| 时间戳 | 字级自带 | 无字级，需配 fsmn-vad 拿句子级 |
| 领域纠错 | 支持热词 | 支持文本级热词纠错 |

- **明确不做回退**：SenseVoice 是唯一 ASR 引擎，失败就明确报错（不保留 paraformer 回退，避免维护两套）。
- **明确不做云端 ASR（本期）**：DashScope 录音文件识别留作将来规模化路径，本期不加抽象层，不写死任何 env 开关。
- **不做音频降噪预处理**：先信任 SenseVoice 自身抗噪；若实测仍不够再单独评估（不本期实现）。

---

## 二、技术架构

### 组件

```
engine/
  ├── asr.py       ← 新增：SenseVoice ASR 模块（模型单例 + 转录 + 热词加载）
  └── pipeline.py  ← 改造：_run_asr() 改为调用 asr 模块；精简后处理；删除 chunk 循环旧逻辑
knowledge/driving_exam.json  ← 复用：high_frequency_topics 的 topic+aliases 生成热词表
```

### `engine/asr.py` 接口

```python
def load_hotwords() -> list[str]
    # 从 knowledge/driving_exam.json 提取 high_frequency_topics[].topic + aliases
    # 去重后返回（如 "倒车入库"、"侧方停车"、"夜间灯光"、"曲线行驶" ...）

class SenseVoiceASR:
    _model = None  # 进程级惰性单例（多请求复用，避免每单重载）

    def transcribe(self, audio_path: str) -> list[dict]
        # 返回 [{start, end, text}]，秒为单位（与现有 asr_result.json schema 一致）
```

**模型单例**：`AutoModel(model="iic/SenseVoiceSmall", vad_model="fsmn-vad", trust_remote_code=True)` 放在模块级 `_MODEL` 全局缓存。Web 每请求新建 `Pipeline` 不会触发重载——这是为多用户场景的硬要求。

### 数据流

```
_extract_audio (不变，ffmpeg 提取 16kHz mono)
  → SenseVoiceASR.transcribe(完整 audio.wav)   ← 不再手动 60s chunk
      model.generate(input, sentence_timestamp=True, use_itn=True,
                     postprocess_hotwords=load_hotwords())
      → 解析 result["sentence_info"]（毫秒时间戳 + 文本）
      → 毫秒→秒
  → _postprocess_asr 精简版（轻清理）
  → asr_result.json（schema 不变：{"segments":[{start,end,text}], "total"}）
  → analyzer/advisor/Web 下游零改动
```

**不再需要旧机制**：
- 删除 60s chunk + 5s 重叠 + RMS 静音跳过（VAD 接管切段）；
- 删除 `_parse_asr_timestamps`（字级时间戳解析，SenseVoice 不走这条路）；
- `_postprocess_asr` 精简为：富标签兜底清理 / 超短填充句过滤 / 相邻近似句合并。

### 关键参数

| 参数 | 值 | 说明 |
|------|-----|------|
| ASR 模型 | `iic/SenseVoiceSmall` | 需 `trust_remote_code=True` |
| VAD 模型 | `fsmn-vad` | 提供句子级时间戳，替代 60s chunk |
| `sentence_timestamp` | `True` | 输出 `sentence_info` 带毫秒时间戳 |
| `use_itn` | `True` | 数字归一化（"十二点"→"12点"，对方向盘点位表述友好） |
| `postprocess_hotwords` | 知识库热词表 | 文本级纠错，模糊匹配（如"到车入库"→"倒车入库"） |
| 输出 schema | `{start,end,text}` 秒 | 与现状完全一致 |

---

## 三、错误处理

| 场景 | 处理 |
|------|------|
| SenseVoice 模型下载/加载失败（网络、缺依赖） | 抛出带指引的明确错误（提示检查网络/模型），不静默降级 |
| 推理异常 | 同上，明确报错 |
| 空转录 / 纯噪声 | `transcribe` 返回空列表；`advisor.build_plan` 已有「没有听到说话内容，请换一个视频或粘贴文字」 |
| 时间戳缺失（极端情况） | funasr 内置用 VAD 段边界兜底 |

> 原则：ASR 是链路第一步，失败必须明确、可解释，让用户走「粘贴文字」兜底路径，而不是拿到一份坏方案。

---

## 四、测试

### 单元测试（mock funasr，不下载模型）

1. `load_hotwords()`：从知识库生成，断言包含 topic + aliases、无重复。
2. `transcribe()` 毫秒→秒 转换 + `sentence_info` 解析 + schema 输出正确。
3. `transcribe()` 对空结果返回空列表。
4. 模型加载/推理抛异常时，错误信息明确、不含敏感栈。
5. 现有 `tests/test_advisor.py` 10/10 保持通过。

### 真实集成验证（手动，验证后才算完成）

1. 跑真实 SenseVoice 于 `work/audio.wav`（车内+考试播报真实样本），与坏基线 `work/asr_result.json` **逐句对比**，确认可读性提升（教练人声成句、考试播报成句、热词纠错生效）。
2. 用 `run.py --optimize input/PNIK4383.MOV` 跑通完整链路，确认 5 块方案质量。
3. Web 全流程回归（上传 → 生成 → 复制）不回归。
4. 记录 CPU 耗时（5 分钟音频应 < 1 分钟）与模型首次加载耗时（之后单例复用）。

---

## 五、范围（明确不做）

- ❌ 云端 DashScope ASR（将来规模化路径，本期不加抽象）
- ❌ paraformer 回退 / `ASR_BACKEND` 开关
- ❌ 音频降噪预处理（noisereduce 等），实测不足再议
- ❌ 模型级热词（仅用 funasr 文本级 `postprocess_hotwords`）
- ❌ 更新 funasr 版本（保持 1.3.30，已验证支持所需能力）

---

## 六、验证标准（做到什么算成功）

1. `work/audio.wav` 转录从「碎片化不可读」变为「教练人声 + 考试播报都是可读整句」，热词纠错把领域词识别对。
2. 完整 `run.py --optimize` 与 Web 流程出的 5 块方案质量不下降、可读性明显提升。
3. `tests/test_advisor.py` 10/10 + 新增单测全绿。
4. 5 分钟音频 ASR 在本机 CPU 上 < 1 分钟；Web 多请求不重复加载模型（单例生效）。
