# LLM Evaluation 0026 Iteration Platform

评估驱动开发平台 | Prompt 版本管理 | LLM002das002dJudge + 规则指标 | Streamlit0026nbsp;Dashboard

[![CI](https://github.com/Gashen0/llm-eval-iteration-platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Gashen0/llm-eval-iteration-platform/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-supported-blue?logo=docker)](Dockerfile)

支持 Prompt 版本管理、自动化评估与迭代优化的工程师平台

## 项目概述

LLM Evaluation & Iteration Platform 是一个面向 LLM 应用开发和 Prompt 工程的系统化评估平台，核心目标是解决当前 LLM 原型开发中存在的三大效率瓶颈：Prompt 迭代缺乏结构化版本管理导致的历史混乱、输出质量评估依赖人工主观判断难以量化、以及缺乏系统化的反馈闭环导致调优方向模糊。平台提供 Prompt 的语义化版本管理、LLM-as-Judge 与规则引擎结合的自动化评估、以及基于评估指标差分的迭代方向建议，使 Prompt 开发过程从"玄学调参"转变为数据驱动的工程实践。

这是我的独立学习项目，重点探索 LLM 应用开发中"评估驱动开发"（Evaluation-Driven Development）的工程化实践。选择此方向是因为观察到大多数项目（包括我自身的实践）在将 LLM Demo 推向生产时都面临"不知道改哪里""改了之后不知道怎么从而改差""没有量化依据证明改动有效"等现实痛点。了解到 Anthropic、OpenAI 等公司在内部构建的 Prompt 工程平台后，我判断此类工具在中文开发者场景中存在基础设施缺失，值得从零构建并开源。

## 核心功能

- **Prompt 语义化版本管理**：支持 Prompt YAML/JSON 的结构化存储，自动提取变量插槽（`{{variable}}`），记录每次迭代的完整元数据（修改人、动机、时间、关联的评估实验 ID），支持基于语义 diff 的版本对比而非纯文本 diff。解决 Prompt A/B 实验中"改了哪里导致变好/差"的可追溯问题。
- **LLM-as-Judge 自动化评估**：用户定义评估维度（如准确性、相关性、安全性、风格一致性），系统自动调用更强的 LLM（如 GPT-4 / Claude-3）作为评判者，对一组候选 Prompt 的输出进行打分和优劣分析。支持自定义评判维度与权重，评测 Prompt 可控且可复现。
- **规则-based 互补指标**：针对结构固定的任务（如 JSON 输出解析、SQL 生成、代码补全），提供基于规则的精确度、语法正确率、格式合规率等硬性指标，作为 LLM-as-Judge 的补充，避免纯主观评分的偏差与非确定性。
- **评估驱动的迭代闭环**：当单次评估结果触发预设阈值（如平均分 < 0.7 或某单项指标连续两次下降）时，系统自动标记问题维度并提示下一轮迭代方向。用户输入新 Prompt 版本后，平台自动回溯历史评估数据，对比分析改善与劣化点。
- **A/B 测试与版本对比**：支持在不同 Prompt 版本间进行受控 A/B 实验，固定 LLM 模型、温度、种子数据集，输出统计显著性检验（如 t-test）结果。信息不对称的对比（如不同模型）会明确标注标注不具可比性
- **可视化 Dashboard**：基于 Streamlit 构建，展示 Prompt 版本演进曲线、各维度评估得分的雷达图与热力图、实验对比矩阵。蓝色与橙色分别标注不同版本在评估指标上的优劣。
- **批量数据集管理与运行**：支持上传批量测试数据集（CSV/JSONL），一键对不同 Prompt 版本发起评测任务，输出带有置信区间的统计结果。支持历史运行记录的留存与重新执行。
- **失败的自动分类与归因**：评估失败的样本会被自动归类（如"格式错误""事实性错误""风格偏离""安全违规"），辅助用户精准定位 Prompt 的 weak spot。

## 系统架构与关键技术决策

### 整体架构

```
               User / Developer
                        |
           +---------------------------+
           |  Streamlit Dashboard      |
           |  (可视化 + 交互)          |
           +---------------------------+
                        |
          +-------------+-------------+
          |       API 层 (FastAPI)      |
          +-------------+-------------+
                        |
    +-------------------+-------------------+
    |                                       |
+---v------------+              +-----------v-----------+
| Prompt Manager |              | Evaluation Engine   |
| (版本 + 语义)  |              | (LLM-Judge + Rules) |
+---^------------+              +-----------^-----------+
    |                                       |
    +----------+                            +-----------+
    |                                  +------+--------+  |
    |                                  | Experiment    | |
    |                                  | (A/B test)    | |
    |                                  +---------------+ |
    +-----------------+-------------------------------+
                      |
          +-----------v-----------+
          |   Iteration Loop     |
          | (闭环 + 方向建议)   |
          +-----------+----------+
                      |
          +-----------v-----------+
          |   Data / Logs        |
          | (版本 + 评估 + 结果) |
          +----------------------+
```

### 关键技术决策

#### 1. 为什么采用 LLM-as-Judge + 规则-based 结合的评估方式

**为什么不用单一方式**：

- **纯 LLM-as-Judge**：主观性强，评分不稳定（Non-deterministic），成本高（每次评估都要调用 LLM），且对 LLM 自身的知识储备有依赖。例如评判"代码是否正确"时，LLM 可能给出错误判断。
- **纯规则-based**：无法评估开放性任务（如创意写作、摘要生成）的质量，只能做硬性约束校验（如 JSON 格式是否合法）。缺乏对语义质量的理解。

**结合方式**：
- 对**硬性指标**（JSON 语法正确率、SQL 执行通过率、输出格式合规率），使用规则引擎进行 100% 确定性的自动判断。
- 对**软性指标**（准确性、相关性、流畅度、风格一致性），使用 LLM-as-Judge 进行语义层面的理解和评分。
- 将两者结果通过加权融合（Weighted Score）得到综合得分：
  ```
  final_score = α * score_llm + β * score_rules
  ```
  其中 α+β=1，用户可根据任务类型进行调节。

**Trade-off**：
- 需要维护两套评估逻辑，增加了代码复杂度。
- LLM-as-Judge 的 Prompt 工程本身也需要持续迭代和评估，存在"用魔法打败魔法"的递归风险。
- 规则引擎对未知输出格式的覆盖率有限，容易遗漏 corner case。

#### 2. Prompt 版本管理的实现机制

**方案**：基于文件的版本管理（Git + 结构化 YAML），而非数据库或纯 UI 操作。

**选择原因**：
- **可审计性**：Git 的 commit history 天然记录了"谁在什么时间改了什么"，且回滚操作零成本。数据库方案需要自行搭建审计模块。
- **可复现性**：Prompt 文件 + 评估脚本 + 数据文件全部在项目中，通过 Git 标签固定版本，任何实验都可以被完全复现。
- **开发者友好**：开发者的本地工作流无需改变，可以直接在 IDE 中编辑 Prompt YAML，通过 Git diff 查看修改内容。无需离开编辑器进入 Web UI。
- **CI/CD 集成**：可以直接在 CI Pipeline 中加载特定版本的 Prompt 文件执行回归测试。

**实现方式**：
```
data/prompts/
  v1.0.0_sql_generato      content: "..."
      variables: ["schema", "query"]
      version: "1.0.0"
      created_at: "2024-01-01"
      parent: null
      evaluation_id: "exp-001"
```

**Trade-off**：
- 面对大规模（>1000 个）Prompt 的管理时，文件系统的查询效率不如数据库。
- 多人协作时，YAML 文件的合并冲突需要手动处理。解决方案是通过小型模块化（每个 Prompt 一个文件）减少冲突。
- 缺乏数据库事务保护，并发写操作可能产生脏数据。当前方案通过 Git 的锁机制解决（只能串行提交）。

**决策结论**：对于独立项目和中小型团队，基于 Git 的文件管理在开发体验和工程简便性上优于数据库存储方案。若未来 Prompt 规模过大，可迁移至 Git-LFS 或直接切换至数据库。

#### 3. 评估驱动的迭代闭环设计

**核心机制**：

闭环流程如下：
1. 用户提交新 Prompt 版本（Vn）。
2. 平台自动加载预设的测试数据集（固定 seed）。
3. 对 Vn-1 和 Vn 执行双轨评估（Parallel Evaluation）。
4. 对比评估结果，输出差分报告（Delta Report），标注哪些维度改善了、哪些恶化了。
5. 若恶化维度超过阈值，自动触发 `regression_alert`，建议回滚或针对性修正。
6. 用户根据反馈调整，再次提交新版本（Vn+1），循环往复。

**失败模式识别**：
- **Regression Detector**：如果新版本在任何指标上低于前版本的 `best_ever_version * (1 - tolerance)`（默认 tolerance = 0.05），标记为回归（Regression）。
- **Pattern Classifier**：对失败的样本进行聚类，自动归因到具体的质量类别（如"未能保持 JSON 格式""引入了新的事实性错误"）。
- **Suggestion Generator**：基于失败模式的聚类结果，生成结构化的优化建议（如"请加强 JSON 输出格式的约束说明""The prompt's instruction on entity grounding is weak"）。

**Trade-off**：
- 自动化的闭环可能导致"为提升指标而牺牲质量"的针对性过拟合。用户需警惕指标陷阱，结合人工抽样判断。
- 闭环速度受限于 LLM 评估耗的延迟（慢）。若数据集过大，完整评估循环时间很长（>30分钟）。解决方案是采用分层采样（先小数据集快速验证，通过后再放大样本）。

#### 4. A/B 测试的实现机制

**公平对比的关键约束**：
- **模型固定**：两个版本的 Prompt 必须使用同一个 LLM 模型、相同的 temperature、top-p 等超参数。
- **数据固定**：使用同一套 seed 数据集，不重新采样，避免数据污染。
- **顺序随机化**：为了避免 LLM 的 order bias，对对比结果进行交叉验证（swap order）。
- **统计显著性**：使用 t-test 或 wilcoxon signed-rank test 判断差异是否统计上显著（p<0.05）。仅当差异显著时才认定新版本更优。

**实现方式**：
实验对象 `ExperimentConfig`，通过唯一的 experiment_id 进行版本锁定，确保可复现。

**Trade-off**：
- 固定的 seed 看起来不够"随机"，但实际上是工程对比所必需的。
- 统计显著性检验依赖于足够多的样本量（建议单版本至少 50-100 条）。
- LLM-as-Judge 的非确定性会导致同一对版本多次评估结果略有波动，可通过多次采样平滑并注明置信区间。

#### 5. Dashboard 技术栈选择

**选择 Streamlit 而非 React/Vue**：
- **开发效率**：Streamlit 用纯 Python 即可构建完整交互界面，学习曲线近乎为零，对于独立项目的人力成本更优。
- **与 Python 生态深度集成**：所有计算逻辑（调用模型、处理数据、生成图表）都在 Python 侧，无需前后端分离和 API 对接。
- **数据可视化**：自带 Pandas、Altair、Plotly 集成的展示控件，开发评估指标的雷达图和热力图非常方便。
- **迭代速度**：修改代码后自动刷新，适合快速原型验证。

**Trade-off**：
- Streamlit 的 UI 定制能力较弱，无法达到商业级别的前端质量（如精细的交互、动画效果）。
- 性能上不如专业前端框架，承载大规模实时数据（>1000 条/秒）的能力有限。
- 缺乏多用户隔离和权限管理，无法作为多租户 SaaS 直接使用。

**决策结论**：对于以"评估"为核心的工程工具，Streamlit 在功能覆盖和开发效率上是最优选择。若后期需要构建多团队共用的商业化平台，再考虑迁移至 React + FastAPI 的分离架构。

## 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.11+ | 主语言 |
| FastAPI | API 框架 |
| Streamlit | Dashboard 前端 |
| LangChain / LLM SDK | 调用 LLM 进行判断与生成 |
| Pydantic | 数据模型与校验 |
| GitPython / PyGit2 | Prompt 版本的程序化操作 |
| Matplotlib / Plotly / Altair | 数据可视化 |
| SciPy / Statsmodels | 统计显著性检验 (A/B Test) |
| PyYAML | Prompt YAML 解析与对比 |
| Docker + Docker Compose | 部署 |
| pytest + ruff + mypy | 测试与代码质量 |

## 评估方法与当前结果

### 评估方案

1. **LLM-as-Judge**：对每个测试样本，构造包含"标准答案/参考答案"的 Prompt，要求 Judge LLM 输出结构化的评分 JSON，包含各维度得分和简短说明。
2. **规则-based 引擎**：针对硬性指标（如 JSON 合法性），直接调用 Python `json.loads()` 或正则表达式进行判断，100% 确定性，零成本。
3. **自定义指标**：针对特定任务类型（如文本摘要的长度、SQL 查询的执行计划等），扩展规则库。

### 计划支持的评估维度

| 维度 | 类型 | 说明 |
|------|------|------|
| Correctness | 规则 + LLM | 输出是否正确、符合事实 |
| Relevance | LLM | 输出是否回答了问题 |
| Format Compliance | 规则 | 输出格式（JSON/XML/固定模板）是否合法 |
| Safety | LLM | 是否包含有害内容或违规信息 |
| Conciseness | 规则 | 输出长度是否在合理范围内 |
| Consistency | LLM | 多次运行输出的稳定性（标准差） |

### 当前阶段与后续计划

**当前状态**：
- Prompt 版本管理框架（YAML 解析 + Git 操作）已搭建。
- LLM-as-Judge 的基础调用与 JSON 解析逻辑已跑通。
- 初代 Dashboard 展示 Prompt 版本列表和单次评估结果。

**后续计划**：
- [ ] 完成 20 组真实场景下的 A/B 测试用例，覆盖问答、摘要、代码、SQL 四个方向。
- [ ] 引入 wilcox 统计检验，提升对比报告的科学性。
- [ ] 支持批量评估的异步任务队列（如 Celery）。
- [ ] 开源汇总一份 "Prompt Engineering Benchmark" 评估数据集。

**评估结果 Dashboard 占位**：

> [此处将插入 Dashboard 截图展示：Prompt 版本演进趋势图、A/B 测试对比柱状图、失败样本归因分析热力图]

## 运行与部署

### Docker 一键运行

```bash
# 1. 克隆仓库
git clone https://github.com/Gashen0/llm-eval-iteration-platform.git
cd llm-eval-iteration-platform

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM API Key

# 3. 构建并启动
docker-compose up --build
```

### 本地运行

```bash
pip install -r requirements.txt

# 启动 Dashboard
streamlit run src/dashboard/app.py

# 启动 API 服务（可选）
uvicorn src.main:app --reload
```

### Streamlit Dashboard

```bash
streamlit run src/dashboard/app.py --server.port 8501
```

访问 `http://localhost:8501`

## 项目结构

```text
llm-eval-iteration-platform/
├── config/                 # 配置文件
├── data/                   # 数据存储
│   ├── prompts/            # Prompt YAML 版本
│   ├── experiments/          # 实验配置与结果
│   ├── evaluations/          # 评估原始数据
│   └── results/              # 汇总报告
├── docs/                     # 文档
├── dashboard/               # Streamlit 前端文件
├── scripts/                  # 维护脚本
├── src/
│   ├── evaluation/           # 评估引擎（LLM Judge + Rules）
│   ├── prompt_manager/       # Prompt 版本管理
│   ├── iteration/            # 迭代闭环逻辑
│   ├── dashboard/            # 可视化组件
│   └── utils/                # 工具函数
├── tests/                    # 测试
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## 当前局限性与未来优化方向

1. **缺乏大规模用户验证的 A/B 评估骨架**：当前 A/B 测试逻辑基于离线评测集，尚未接入真实线上流量（如 Shadow Mode）进行 A/B。计划构建一个可切入线上流量旁路的 "Shadow Testing" 框架。

2. **LLM-as-Judge 的非确定性与校准困难**：不同的 Judge Prompt 和模型版本会导致评分的尺度不一致，缺乏一个"Judge 的 Judge"来持续校准评估质量。计划引入 meta-evaluation 机制，定期用人工标注校准自动评分的偏差。

3. **Prompt 版本管理对非技术用户不友好**：当前的 YAML + Git 方案面向开发者，对于 PM 或业务人员的学习成本太高。未来计划提供一个轻量的 Web UI 来可视化管理 Prompt 版本并支持"一键提交评审"。

4. **评估维度扩展成本较高**：每引入一个新的评估维度（如"幽默度"），都需要人工维护对应的 Judge Prompt 和校准标准，缺乏自动化的维度发现机制。计划探索 AutoPrompt 或 Meta Prompting 来自动扩展现有评估框架。

5. **单用户架构，缺乏多租户协作**：当前架构假设为单人单机使用，无法支持团队中多人协作、权限隔离、审批流等功能。未来若开源推广，需要重构为多用户架构。

6. **仅支持单模型对比，缺乏多模型评估**：目前只能对比不同 Prompt 在同一模型下的表现，无法直接横向对比不同 LLM 的基准性能（如 GPT-4 vs Claude vs DeepSeek）。计划扩展多模型路由和对比评估功能。
