# 外用制剂系统暴露预测与采血点建模工具

这是一个本地命令行 MVP，用于先整理同一分子已有剂型的公开 PK 参数，再外推其他外用新剂型的系统暴露和 PK 采血点。它把公开证据、人工确认的 PK 参数和外用制剂假设整合起来，输出：

- 外用制剂系统暴露预测：`Cmax`、`Tmax`、`AUC0-t`、`AUC0-inf`、`Cavg`、`Ctrough`、`Rac`、末端浓度、`predose > LLOQ` 风险。
- PK 采血点推荐：覆盖峰值、AUC、稳态 trough、末端相和残留判断。
- 公开证据缓存：PubChem、openFDA、CDE 官方来源登记。
- 中文 Markdown、Excel 和 PNG 图表报告。

> 本工具是一个"早期外用制剂系统暴露与采血点设计的内部探索性沙盘工具"。它基于同一分子已有剂型的公开 PK 参数和外用剂型半机制吸收假设，输出 order-of-magnitude 级别的系统暴露区间和候选采血点。**不替代** MUsT/max-use PK、BE、PopPK、PBPK，**不可** 用于注册申报材料的暴露预测章节。当 P95 暴露超过参考剂型稳态或输入分子存在浓度依赖清除时，必须由临床药理审评后再决定是否使用模型结果。

## V1.1 修订要点

- 新增 `decision_gate`：对非线性清除、高剂量外推、P95 超参考暴露、校准失败、末端随访不足、安全阈值来源缺失进行 warning 或 blocked 标记。
- 多次给药主指标改为 `Cmax_ss_per_cycle`、`AUC_tau_ss`、`Cmax_global`、`AUC_0_T_studyend`、`AUC_post_last_dose_to_inf`。
- 稳态时间改为 `t_half_eff = max(消除半衰期, 快通道吸收半衰期, depot 半衰期)` 公式推算。
- 采血点按 `exploratory`、`must_max_use`、`be_bridging` 三套目的输出。
- 新增 `parameter_provenance.csv`、`dose_extrapolation_sensitivity.csv` 和报告首页 gate 横幅。

## 同事快速安装

仓库同时包含 Python 命令行工具和 Codex Skill。下载后在仓库根目录运行：

```bash
chmod +x install.sh
./install.sh
```

安装脚本会做两件事：

- 以 editable 方式安装本地 Python 工具包 `topical-pk-tool`。
- 把 `.codex/skills/topical-pk-report` 安装到 `${CODEX_HOME:-$HOME/.codex}/skills/topical-pk-report`。
- 在已安装 Skill 中写入 `.pktool_root`，让 Codex 能找到配套工具仓库。

也可以手动安装 Skill：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R .codex/skills/topical-pk-report "${CODEX_HOME:-$HOME/.codex}/skills/"
python3 -m pip install -e .
```

安装后可用下面命令检查结构：

```bash
python3 scripts/validate_skill_structure.py
python3 ~/.codex/skills/topical-pk-report/scripts/check_pktool_install.py
python3 -m unittest discover -s tests
```

如果同事只安装了 Skill 文件夹，没有 clone 完整仓库或没有运行 `install.sh`，Codex 可能找不到 `pktool`。这种情况下**不要接受手工生成的替代 Markdown 报告**，先按下面方式修复安装：

```bash
git clone https://github.com/huanglu1987/topical-pk-report-skill.git
cd topical-pk-report-skill
chmod +x install.sh
./install.sh
```

如果仓库已经 clone 到其他路径：

```bash
export TOPICAL_PK_TOOL_ROOT=/absolute/path/to/topical-pk-report-skill
python3 ~/.codex/skills/topical-pk-report/scripts/check_pktool_install.py --install
```

真正安装成功的标志是下面命令能输出帮助信息：

```bash
python3 -m pktool.cli --help
```

## 工具安装

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

如果只是运行工具，使用：

```bash
python -m pip install -e .
```

## 快速开始

### 同事最小输入模式

如果同事只是想先跑一个探索性预测，最低只需要填写 5 类基础信息；如果是多次给药，还必须填写给药频率：

| 必填信息 | YAML 字段 | 示例 |
|---|---|---|
| 具体分子 | `compound.compound_name` | `efinaconazole` |
| 具体剂型 | `product.formulation` | `film-forming solution` |
| 浓度 | `product.concentration_percent_w_w` | `3.0` |
| 给药剂量 | `product.daily_amount_g` 或 `product.dose_mg_per_application` | `4.0 g` 或 `120 mg` |
| 单次或多次 | `study_design.dosing_scenario` | `single` 或 `multiple` |
| 多次给药频率（多次时必填） | `study_design.dosing_frequency` 或 `product.dosing_interval_h` | `daily_qd`、`weekly_qw`、`weekly_biw` 或 `168` |

最小模板位置：

```bash
data/minimal_input_template.yaml
```

可直接在 GitHub 页面复制的度他雄胺 single / daily_qd / weekly_qw 输入模板见：

```bash
docs/COPYABLE_INPUT_TEMPLATES.md
```

如果目标是复现既有度他雄胺 2% 20 mg 报告，不要让 Codex 根据自然语言重新生成 YAML；直接运行：

```bash
python3 -m pktool.cli run-report --input data/reproducible_inputs/dutasteride_2pct_20mg_single_locked.yaml --no-fetch
python3 -m pktool.cli run-report --input data/reproducible_inputs/dutasteride_2pct_20mg_multiple_daily_qd_steady_state_locked.yaml --no-fetch
python3 -m pktool.cli run-report --input data/reproducible_inputs/dutasteride_2pct_20mg_multiple_weekly_qw_steady_state_locked.yaml --no-fetch
```

运行示例：

```bash
python3 -m pktool.cli run-report \
  --input data/minimal_input_template.yaml \
  --output-root runs \
  --no-fetch
```

标准报告必须来自 `runs/<timestamp>_<compound>/outputs/reports/pk_sampling_report.md`。如果报告中出现“未执行 Monte Carlo 自动模拟”或结构与本 README 描述不一致，说明没有调用到 `pktool`，需要先修复安装。

`dosing_scenario` 的默认规则：

- `single`：默认单次给药，给药持续 24 h；模拟窗口至少 168 h。若半衰期或 depot 释放较长，会自动延长到至少 3 x `t_half_eff`，并在采血点中加入至少 2 个末端相确认点。
- `multiple`：必须填写 `study_design.dosing_frequency` 或 `product.dosing_interval_h`；如只填给药频率，默认给药窗口会覆盖到接近 100% 稳态（按 99% 计）对应的给药时点，并额外模拟末次给药后至少 168 h 或 3 x `t_half_eff`（取较大者）。
- 如已知真实周期，可用 `product.treatment_duration_h`、`study_design.dosing_duration_h` 或 `study_design.duration_h` 覆盖默认值。

`study_design.dosing_frequency` 可直接控制实际模拟给药间隔；多次给药频率规划还会默认额外输出三种稳态情景：

| 场景 | 字段值 | 给药间隔 |
|---|---|---:|
| 每日一次 | `daily_qd` | 24 h |
| 每周一次 | `weekly_qw` | 168 h |
| 每周两次 | `weekly_biw` | 84 h |

报告会列出每种频率达到 50%、75%、90%、95%、接近 100% 稳态的时间；其中“接近 100%”按 99% 稳态计算，因为真实 100% 是理论渐近值。

最小模式在缺少同分子 PK 锚点时，会启用通用兜底假设，例如 `t1/2 = 12 h`、`V = 50 L`、`medium variability` 和保守外用吸收范围。这里的兜底值不是该分子的历史数据，也不是可引用证据；报告会把这些参数标记为 `default` 或 `model_default_or_derived`。它适合内部快速判断和采血点初筛，不适合直接用于 CRO SOW、正式 MUsT/max-use 方案或监管材料。

如需更可靠的结果，再补充：半衰期、V/CL、已有剂型 Cmax/AUC/Tmax、LLOQ、安全阈值来源、给药面积、最大使用条件和校准参考。

```bash
pktool init-demo
pktool fetch-pubchem --name ivermectin
pktool fetch-fda --ingredient ivermectin
pktool fetch-cde --keyword 药代动力学
pktool simulate-exposure --compound data/compound_profile.csv --reference data/reference_pk.csv --product data/topical_product.yaml
pktool recommend-sampling --simulation outputs/simulation_results.csv
pktool report --format md,xlsx
```

如果你只想输入一个品种的基础信息并自动生成报告，使用一键模式：

```bash
python3 -m pktool.cli run-report --input data/basic_input_example.yaml
```

可用 CLI 覆盖 YAML 中的采血目的和变异度 preset：

```bash
python3 -m pktool.cli run-report \
  --input data/dutasteride_2pct_solution_multiple_input.yaml \
  --output-root runs \
  --no-fetch \
  --purpose must_max_use \
  --variability-preset medium
```

每次运行会在 `runs/` 下生成独立目录，里面包含自动展开的输入文件、公开证据缓存、模拟结果、采血点推荐和报告。

也可以不安装入口，直接运行：

```bash
python -m pktool.cli init-demo
python -m pktool.cli simulate-exposure --compound data/compound_profile.csv --reference data/reference_pk.csv --product data/topical_product.yaml
```

## 输入文件

`pktool init-demo` 会生成示例输入：

- `data/compound_profile.csv`：分子属性、系统处置参数、LLOQ、安全阈值。
- `data/reference_pk.csv`：已有剂型或公开标签中的参考 PK 参数。
- `data/topical_product.yaml`：外用制剂、给药、吸收参数区间。
- `data/study_design.yaml`：模拟次数、模拟时长、候选采血点和推荐点数量。

更推荐的 Skill/插件式输入是：

- `data/basic_input_example.yaml`：只填写品种基础信息，工具自动展开成上述 CSV/YAML。

这个模板支持 `known_formulations`，用于录入同一分子既往已有剂型的公开 PK 特征，例如口服、注射、已上市外用或其他给药途径。工具会把这些信息写入 `known_formulations_pk.csv`，并优先用 `primary_comparator: true` 的记录作为系统处置参数和暴露比较锚点。

使用这个 Skill 时，推荐先完成公开 PK 证据表，再模拟目标外用新剂型。至少要记录每条 PK 参数的来源、剂型/给药途径、剂量、单次/多次给药、Cmax、Tmax、AUC、t1/2、CL/V、稳态时间和 LLOQ 是否可得。

在线检索结果保存在：

- `data/evidence_cache/*.json`
- `data/evidence_cache/evidence_manifest.csv`

在线检索结果只作为公开证据缓存；真实 PK 参数进入模型前应人工确认。

## 输出文件

- `outputs/simulation_results.csv`：浓度-时间预测区间。
- `outputs/simulation_metrics.csv`：每次蒙特卡洛模拟的 PK 参数。
- `outputs/simulation_summary.json`：系统暴露汇总和风险概率。
- `outputs/parameter_provenance.csv`：核心参数来源分列，标注 public/user/default。
- `outputs/dose_extrapolation_sensitivity.csv`：0.7/1.0/1.3 剂量-暴露指数敏感性。
- `outputs/sampling_recommendation.csv`：采血点评分和推荐结果。
- `outputs/reports/pk_sampling_report.md`
- `outputs/reports/pk_sampling_report.xlsx`
- `outputs/figures/concentration_time_band.png`
- `outputs/figures/exposure_quantiles.png`

## 关键边界

- 第一版默认适用于小分子局部外用制剂，如乳膏、凝胶、软膏、溶液、喷雾、泡沫、成膜/涂膜制剂。
- 贴剂和系统透皮制剂不是第一版主目标。
- CDE 没有在此工具中假设稳定公开 API；第一版用官方 URL 来源清单和缓存管理。
- 真实处方、SMILES 清单、PK 原始数据不应上传到外部 AI 或非授权服务。
- `decision_gate.status = blocked_for_decision_use` 时，报告仍会生成，但不得用于 CRO SOW、正式 MUsT 采血点、监管沟通或 IND 暴露章节。

## 测试

```bash
python -m unittest discover -s tests
```

安装开发依赖后也可以运行：

```bash
pytest
```

## 外部专家评估包

第三方评估建议从以下文件开始：

- `docs/THIRD_PARTY_REVIEW_BRIEF.md`
- `docs/MODEL_METHODS_AND_PARAMETERS.md`
- `docs/DUTASTERIDE_VALIDATION_CASE_SUMMARY.md`
- `docs/PUBLIC_PK_EVIDENCE_EXTRACTION_TEMPLATE.md`

这些文件说明了工具目标、预测原理、参数来源、模型判定规则、度他雄胺验证结果和专家审评重点。
