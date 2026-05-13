# 外用制剂 PK 预测工具第三方评估说明书

## 1. 评估目的

本评估包用于请外部临床药理/药代动力学专家评估一个本地化预测工具的实用性。

工具目标是：基于同一分子已有剂型的公开药代动力学参数，例如口服、注射、既有外用或其他剂型，预估该分子其他外用新剂型的系统暴露、单次/多次给药采血点和多次给药达到稳态的时间。

当前版本是 MVP，不是经验证的临床药理模型，也不能替代 MUsT/max-use PK、BE 或正式群体 PK/PBPK 分析。V1.1 已新增 `decision_gate`，当报告显示 `blocked_for_decision_use` 时，输出只能作为内部风险识别和升级 PopPK/PBPK/临床实测的触发依据。

## 2. 建议专家重点审评的问题

请优先审评以下问题：

1. 公开 PK 参数抽取表是否足以支撑同一分子跨剂型外推。
2. 双通道外用吸收模型是否符合外用溶液/喷雾/泡沫等剂型的早期吸收和皮肤 depot 特征。
3. “是否启用早期快速吸收”的判定规则是否合理、是否需要增加或调整权重。
4. 消除动力学判定是否充分区分一阶、零阶和容量限制/非线性消除。
5. 使用既往口服/其他剂型 PK 作为系统处置锚点时，是否存在不可接受的外推风险。
6. 输出的采血点是否足以覆盖 Cmax/Tmax、AUC、稳态 trough、末端相和 LLOQ 附近残留。
7. 当前报告是否能支持早期内部决策、CRO 咨询或监管沟通前准备。
8. 工具还需要哪些真实数据、校准案例或敏感性分析，才能进入更正式的研发使用。
9. V1.1 的决策闸门、稳态时间公式、多次给药 AUC 语义和三套采血点是否足以防止误用。

## 3. 评估包内容

建议从以下文件开始阅读：

1. `docs/MODEL_METHODS_AND_PARAMETERS.md`  
   预测原理、模型结构、参数来源、自动判定规则、输出指标和限制。

2. `docs/DUTASTERIDE_VALIDATION_CASE_SUMMARY.md`  
   以度他雄胺为例，用公开口服和外用 PK 信息预测 1%/2% 外用溶液单次和多次给药暴露。

3. `.codex/skills/topical-pk-report/SKILL.md`  
   Codex Skill 的使用说明、输入要求、证据抽取要求和安全边界。

4. `data/*dutasteride*.yaml`  
   度他雄胺验证用输入文件。

5. 本地重跑后生成的 `runs/` 目录  
   1%/2% 单次和多次验证报告、Excel 附件、模拟汇总和采血点推荐。GitHub 分发包默认不附历史运行产物。

6. `tests/`  
   当前最小测试集。

## 4. 快速复现

在项目根目录运行：

```bash
python3 -m unittest discover -s tests
python3 -m pktool.cli run-report --input data/dutasteride_1pct_solution_single_input.yaml --output-root runs --no-fetch
python3 -m pktool.cli run-report --input data/dutasteride_2pct_solution_single_input.yaml --output-root runs --no-fetch
python3 -m pktool.cli run-report --input data/dutasteride_1pct_solution_multiple_input.yaml --output-root runs --no-fetch
python3 -m pktool.cli run-report --input data/dutasteride_2pct_solution_multiple_input.yaml --output-root runs --no-fetch
```

如需联网补充公开证据缓存，去掉 `--no-fetch`。

## 5. 当前验证状态

- 单元测试：`python3 -m unittest discover -s tests`，17 个测试通过。
- 已完成度他雄胺 1%/2% 外用溶液单次与多次给药验证。
- 已完成早期快速吸收判定、消除动力学判定和采血点推荐输出。

## 6. 重要边界

- 公开来源信息只作为证据缓存；正式建模参数必须人工核对。
- 当前工具使用半机制模型和蒙特卡洛模拟，不是经过充分外部验证的 PopPK/PBPK。
- 1%/2% 度他雄胺外用溶液属于从 0.05% 外用公开数据向高浓度外推，剂量跨度较大，P95 区间需要特别谨慎解释。
- 对存在非线性/容量限制消除风险的药物，若无 Vmax/Km 或浓度-清除率数据，工具默认按低系统暴露场景的一阶消除模拟，并把非线性作为外推风险；若同时命中 V1.1 gate，则不得用于 CRO SOW、最终采血点或监管材料。
