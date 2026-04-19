# MLOps + Autonomous AI Agents 完整知识体系

> **整理时间**: 2026-04-16 21:40
> **来源**: Run #525 - 基于 hermes-agent 研究积累

---

## 整体架构图

```
AI Agent 系统分层架构
====================================================================

                         训练层 (Training)
  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────────────┐
  │ Axolotl │  │ Unsloth │  │  TRL   │  │     DSPy (Prompt)      │
  │ (生产级) │  │ (快速)  │  │ (GRPO) │  │   (Declarative LM)     │
  └─────────┘  └─────────┘  └─────────┘  └─────────────────────────┘
                              │
                              ▼
                         量化层 (Quantization)
  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────────────────────┐
  │  GGUF   │  │  AWQ   │  │  GPTQ   │  │        FP8             │
  │(CPU/边缘)│  │(70B生产)│  │(通用)  │  │      (H100)            │
  └─────────┘  └─────────┘  └─────────┘  └─────────────────────────┘
                              │
                              ▼
                         服务层 (Serving)
  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐
  │    vLLM      │  │  llama.cpp   │  │    HuggingFace (研究)    │
  │(GPU生产级)   │  │(CPU/边缘)    │  │     (原型)               │
  └──────────────┘  └──────────────┘  └───────────────────────────┘
                              │
                              ▼
                         评估层 (Evaluation)
  ┌──────────────────────────────────────────────────────────────────┐
  │              lm-evaluation-harness (60+ benchmarks)               │
  │  MMLU | GSM8K | HellaSwag | TruthfulQA | ARC | HumanEval         │
  └──────────────────────────────────────────────────────────────────┘


======================================================================
                     Agent 编排层 (Orchestration)

  hermes-agent (Nous Research) - Self-improving through skills

  delegate_task  ──────►  快速子任务 (分钟级，隔离对话)
  spawn hermes   ──────►  长期自主任务 (小时/天级，独立进程)
  tmux + hermes  ──────►  交互式多 agent 协调 (backend/frontend)
  profiles       ──────►  多实例隔离 (不同任务/角色)
```

---

## 1. 训练层详解 (Training)

### 1.1 Axolotl - 生产级训练框架

**定位**: 最全面的开源微调框架，支持 100+ 预置模型

**核心能力**:
- SFT (Supervised Fine-Tuning): 指令微调
- DPO (Direct Preference Optimization): 偏好对齐
- RLHF (Reinforcement Learning from Human Feedback): 人类反馈强化学习
- FSDP v2 + DeepSpeed: 分布式训练支持

**适用场景**:
- 生产级模型训练
- 需要多节点分布式训练
- 支持大量自定义配置

**来源**: Run #451 - mlops/training/axolotl 技能

---

### 1.2 Unsloth - 快速微调框架

**定位**: 2-5x 加速训练，50-80% 内存减少，适合个人开发者和快速实验

**核心优势**:
- 2-5x 训练速度提升
- 50-80% 显存减少
- 无精度损失（bit for bit）
- 支持 LoRA + QLoRA + DyLoRA

**配合工具**:
- **Dynamic GGUFs**: 比标准量化精度更高
- **GRPO**: 结合 Unsloth 训练推理模型（DeepSeek R1 类）

**关键代码**:
```python
from unsloth import FastLanguageModel
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="unsloth/mistral-7b",
    max_seq_length=2048,
    dtype=None,
    load_in_4bit=True,
)
```

**来源**: Run #450 - mlops/training/unsloth 技能

---

### 1.3 TRL - Transformer Reinforcement Learning

**定位**: HuggingFace 出品的 RL 训练库，支持 GRPO/PPO/SFT

#### GRPO (Group Relative Policy Optimization) - DeepSeek R1 核心方法

**原理**: 不需要单独训练 Reward Model，通过组内相对比较优化策略

**优势**:
- 不需要 Critic Model（PPO 需要）
- 训练 loss 从 0 开始随训练增加（衡量 KL divergence）
- 监控 reward 而非 loss

**关键配置**:
```python
from trl import GRPOConfig, GRPOTrainer

training_args = GRPOConfig(
    output_dir="./output",
    beta=0.001,  # KL 散度系数
    max_prompt_length=512,
    max_completion_length=512,  # 推理任务 512，短答案 256
)
```

**适用任务**:
- 推理能力提升（Math, Code, Reasoning）
- Chain-of-thought 强制格式（XML/JSON tags）
- 形式化验证任务（LLM-as-Judge）

**来源**: Run #449 - mlops/training/grpo-rl-training 技能

---

### 1.4 DSPy - 声明式 LM 编程

**定位**: Stanford NLP 出品，Prompt 编程框架（不是训练框架）

**核心理念**: 用 Signatures 定义输入输出，Modules 提供推理模式，Optimizers 自动优化

**Signatures 示例**:
```python
class GenerateAnswer(dspy.Signature):
    question = dspy.InputField()
    answer = dspy.OutputField()
```

**Modules**:
```python
cot = dspy.ChainOfThought(GenerateAnswer)
result = cot(question="What is 2+2?")
```

**Optimizers**:
- `BootstrapFewShot`: 从少样本中学习
- `MIPRO`: 贝叶斯优化多参数

**完整 Pipeline**: TRL -> AWQ/GGUF -> DSPy -> lm-eval

**来源**: Run #523 - mlops/research/dspy 技能

---

## 2. 量化层详解 (Quantization)

### 量化决策树

```
需要量化？
    │
目标硬件？
    │
    +--- CPU/边缘 ---> GGUF (llama.cpp)
    |
    +--- GPU
          │
          模型规模？
          │
          +--- 70B+ ---> AWQ (生产推荐)
          |
          +--- <70B ---> GPTQ
          |
          +--- H100 ---> FP8
```

### 2.1 GGUF - CPU/边缘推理标准

**定位**: llama.cpp 统一格式，CPU 和边缘设备推理首选

**核心概念**:
- **Q4_K_M**: 推荐默认选择（4.5bit，7B=4.1GB）
- **K-quants 变种**: Q5_K_S, Q6_K, Q8_0
- **imatrix**: 重要性矩阵提升低比特量化质量

**内存估算**:
| 模型规模 | FP16  | Q8_0  | Q6_K  | Q5_K_M | Q4_K_M | Q4_K_S |
|---------|-------|-------|-------|--------|--------|--------|
| 7B      | 14GB  | 7.1GB | 5.4GB | 4.8GB  | 4.1GB  | 3.8GB  |
| 13B     | 26GB  | 13.5GB| 10.2GB| 9.1GB  | 7.8GB  | 7.2GB  |
| 70B     | 140GB | 72GB  | 54GB  | 48GB   | 41GB   | 38GB   |

**适用场景**:
- CPU 推理
- Apple Silicon (Metal 加速)
- 边缘设备
- 内存受限环境

**来源**: Run #518/520 - mlops/inference/gguf 技能

---

### 2.2 AWQ - 70B 生产级量化

**定位**: Activation-Aware Weight Quantization，70B 模型生产部署首选

**原理**: 用校准数据识别对精度影响大的权重（activation 大的），保留这些权重为较高精度

**核心数据**:
- 4-bit 量化: 70B 模型 140GB -> 35GB
- 精度损失: <1%
- 速度提升: 配合 vLLM 可达 3-5x

**适用场景**:
- 70B+ 大模型 GPU 部署
- 生产环境
- 需要高精度的场景

**来源**: Run #521 - mlops/inference/awq 技能

---

### 2.3 GPTQ - 通用量化方案

**定位**: 通用 4-bit 量化，适合 70B 以下模型

**特点**:
- 成熟稳定
- 支持多种模型架构
- 与 vLLM 良好集成

---

### 2.4 FP8 - H100 专用

**定位**: 8-bit 浮点，H100 GPU 原生支持

**核心数据**:
- 速度提升: 1.8x vs BF16
- 精度损失: <0.5%
- 硬件要求: H100

---

## 3. 服务层详解 (Serving)

### 3.1 vLLM - GPU 生产级推理

**定位**: PagedAttention 技术，高吞吐量生产级推理

**核心特性**:
- **PagedAttention**: Block-based KV cache，避免 OOM
- **Continuous Batching**: 24x throughput 提升
- **AWQ/GPTQ/FP8**: 开箱即用量化支持
- **OpenAI 兼容 API**: 直接用 SDK 调用

**性能对比**:
| 后端        | 7B Throughput | 70B Throughput | 适用场景   |
|------------|--------------|----------------|-----------|
| vLLM       | 100+ req/s   | 10+ req/s      | GPU 生产级 |
| llama.cpp  | 10-20 req/s  | 1-2 req/s     | CPU/边缘   |
| HuggingFace| 5-10 req/s   | 0.5 req/s      | 研究原型   |

**启动命令**:
```bash
vllm serve meta-llama/Llama-2-70b-chat \
    --quantization awq \
    --tensor-parallel-size 4 \
    --max-model-len 8192
```

**来源**: Run #519 - mlops/inference/vllm 技能

---

### 3.2 llama.cpp - CPU/边缘推理

**定位**: 纯 CPU 高效推理，Apple Silicon 优化

**核心工具**:
- `llama-server`: 带 OpenAI 兼容 API 的服务器
- `llama-cli`: 命令行交互
- `llama-quantize`: 量化工具

**启动命令**:
```bash
llama-server \
    -m ./model-q4_k_m.gguf \
    -c 4096 \
    --host 0.0.0.0 \
    --port 8080
```

**来源**: Run #518 - mlops/inference/llama.cpp 技能

---

## 4. 评估层详解 (Evaluation)

### 4.1 lm-evaluation-harness

**定位**: EleutherAI 出品的行业标准 LLM 评估工具，支持 60+ 基准测试

**常用基准**:

| 基准      | 测试内容       | 评估时间 (GPU) | 重要性 |
|---------|--------------|--------------|--------|
| MMLU    | 57 学科选择题   | ~10min       | 5星    |
| GSM8K   | 小学数学应用题   | ~5min        | 5星    |
| HellaSwag| 常识推理     | ~10min       | 3星    |
| TruthfulQA| 真实性问答   | ~5min        | 4星    |
| ARC     | 科学问答       | ~15min       | 3星    |
| HumanEval| 代码生成     | ~20min       | 4星    |

**评估命令**:
```bash
lm_eval \
    --model vllm \
    --model_args pretrained=meta-llama/Llama-2-70b-chat,quantization=awq \
    --tasks mmlu,gsm8k,truthfulqa \
    --batch_size 8
```

**vLLM 加速**: 比 HuggingFace 后端快 5-10x

**硬件要求**:
- 7B 模型: 16GB VRAM (BF16) 或 8GB (8-bit)
- 70B 模型: 多卡 A100/H100

**来源**: Run #433/522 - mlops/evaluation/lm-evaluation-harness 技能

---

## 5. Agent 编排层 (Orchestration)

### 5.1 hermes-agent (Nous Research)

**定位**: 自我改进型 AI Agent 框架，通过 Skills 持久化学习

**差异化特性**:
- Self-improving through skills: 每次执行后保存学到的方法
- Multi-platform gateway: 支持 10+ 平台（Telegram/Discord/Slack等）
- Provider-agnostic: 支持 20+ 模型提供商
- Persistent memory: 跨会话记忆

**编排方式对比**:

| 方式           | 隔离级别         | 运行时长    | 工具访问 | 交互性 | 适用场景         |
|--------------|----------------|-----------|---------|-------|----------------|
| delegate_task | 隔离对话/共享进程 | 分钟级     | 受限     | 无    | 快速子任务       |
| spawn hermes  | 完全独立进程     | 小时/天级   | 完整     | 无    | 长期自主任务      |
| tmux + hermes | 完全独立进程     | 小时/天级   | 完整     | 有    | 交互式协调       |
| profiles     | 完全隔离         | 任意       | 完整     | 无    | 多实例隔离       |

**tmux + hermes PTY 模式**:
```bash
# 创建独立 agent session
tmux new-session -d -s agent1 -x 120 -y 40 'hermes'

# 发送任务指令
tmux send-keys -t agent1 'Build a FastAPI auth service with JWT' Enter

# 读取输出
tmux capture-pane -t agent1 -p
```

**Multi-agent 工作流**:
```
Backend Agent (tmux:1)  <--API-->  Frontend Agent (tmux:2)
         │                           │
         └───────────┬───────────────┘
                     ▼
              Hermes Orchestrator
```

**来源**: Run #524 - hermes-agent 技能

---

## 6. 完整 MLOps Pipeline

### 标准 Pipeline 流程

```
1. 预训练模型
      │
      ▼
2. SFT / GRPO 训练 (Axolotl / Unsloth / TRL)
      │
      ▼
3. 量化选择
    ├── CPU/边缘 ---> GGUF (Q4_K_M)
    ├── 70B GPU ---> AWQ 4-bit
    ├── H100 -----> FP8
    └── 其他 -----> GPTQ
      │
      ▼
4. 服务部署 (vLLM / llama.cpp / HF)
      │
      ▼
5. Prompt 优化 (DSPy - 可选)
      │
      ▼
6. 评估验证 (lm-evaluation-harness)
      │
      ▼
7. 部署上线
```

### Pipeline 决策表

| 场景          | 训练      | 量化       | 服务     | 评估     |
|-------------|---------|-----------|---------|---------|
| 个人快速实验    | Unsloth  | GGUF Q4_K_M | llama.cpp | lm-eval |
| 70B 生产部署   | Axolotl  | AWQ 4-bit  | vLLM    | lm-eval  |
| 推理能力提升    | TRL GRPO | AWQ        | vLLM    | GSM8K   |
| 研究原型      | HuggingFace | BF16   | HF      | lm-eval  |
| CPU 边缘     | -        | GGUF       | llama.cpp | 简化评估 |

---

## 7. 快速参考卡片

### 工具选择速查

```
需要训练模型？
  ├── 快速实验 ---> Unsloth
  ├── 生产级训练 ---> Axolotl
  └── 强化学习 ---> TRL GRPO

需要量化？
  ├── CPU/边缘 ---> GGUF Q4_K_M
  ├── 70B GPU ---> AWQ
  └── H100 -----> FP8

需要服务？
  ├── GPU 生产 ---> vLLM
  ├── CPU ------> llama.cpp
  └── 研究 ------> HuggingFace

需要评估？
  └── lm-evaluation-harness (60+ benchmarks)
```

### 关键参数速查

| 场景           | 推荐配置                           |
|--------------|----------------------------------|
| 7B 模型训练     | Unsloth + LoRA + QLoRA           |
| 70B 模型量化    | AWQ 4-bit                        |
| 推理任务        | GRPO + max_completion_length=512 |
| 短答案任务       | GRPO + max_completion_length=256 |
| MMLU 评估      | vLLM + lm_eval                   |
| 实时推理        | vLLM continuous batching          |

---

## 8. 相关 Run 记录索引

| Run #  | 主题              | 关键收获                                      |
|--------|-----------------|---------------------------------------------|
| #449   | GRPO 训练         | 奖励函数设计、loss 监控                         |
| #450   | Unsloth          | 2-5x 加速、50-80% 内存节省                      |
| #451   | Axolotl          | 100+ 预置模型、FSDP v2                        |
| #518   | llama.cpp        | K-quants、imatrix                            |
| #519   | vLLM             | PagedAttention、continuous batching          |
| #520   | GGUF             | Q4_K_M、CPU 推理                             |
| #521   | AWQ              | activation-aware、70B 生产                    |
| #522   | lm-eval          | 60+ benchmarks、MMLU/GSM8K                   |
| #523   | DSPy             | Signatures、Modules、Optimizers              |
| #524   | hermes-agent      | delegate_task、tmux 编排                      |
| #538   | vLLM             | PagedAttention + Continuous Batching 24x 吞吐，axolotl+vLLM workflow |
| #539   | GGUF vs vLLM     | GGUF Q4_K_M CPU/边缘 vs vLLM GPU 生产，互补场景 |
| #540   | W&B + lm-eval    | 实验追踪 sweeps，60+ benchmarks 评估框架补全 MLOps pipeline |

---

*文档版本: 2026-04-16 21:40 - 由 Hermes Agent Run #525 整理*
