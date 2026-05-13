# 预测原理、模型结构和参数来源说明

## 1. 目标用途

本工具用于早期研发阶段的外用制剂 PK 预测和采血点设计。V1.1 后统一定位为内部探索性沙盘工具：不替代 MUsT/max-use PK、BE、PopPK、PBPK，也不可直接用于注册申报暴露预测章节。目标是把同一分子已有剂型的公开 PK 参数作为系统处置锚点，再结合目标外用剂型的给药量、剂型特征、公开外用案例和保守吸收区间，预测：

- 单次给药系统暴露：Cmax、Tmax、AUC0-t、AUC0-inf、末端浓度。
- 多次给药系统暴露：Cmax、AUC、Cavg、Ctrough、Rac、predose > LLOQ 概率。
- 达到 90%/95% 稳态的预计时间。
- 单次和多次给药采血点建议。
- 决策闸门状态：`ok`、`warning` 或 `blocked_for_decision_use`。

## 2. 数据输入层

### 2.1 同一分子已有剂型公开 PK 参数

字段位置：`known_formulations`。

每个既往剂型建议记录：

- route/formulation：给药途径和剂型。
- dose_mg 或 dose_description：剂量或给药描述。
- single_or_multiple：单次或多次给药。
- Cmax、Tmax、AUC0-t、AUC0-inf、AUCtau、Cavg、Ctrough。
- half_life_h、clearance_l_h、volume_l。
- bioavailability、accumulation ratio、steady-state timing、washout/detectability。
- LLOQ、生物分析方法、来源链接或文献/标签来源。
- primary_comparator：是否作为主比较锚点。

工具优先用 `primary_comparator: true` 的非外用系统剂型作为系统处置和暴露比较锚点；既有外用数据优先作为局部递送和早期吸收判定依据。

### 2.2 分子和系统处置参数

字段位置：`compound` 和 `reference_pk`。

核心参数：

- `half_life_h`：用于计算一阶消除速率 `ke = ln(2) / t1/2`。
- `volume_l`：用于把中央室药量换算为血浆浓度。
- `clearance_l_h`：如缺失，则用 `ke x V` 推算。
- `lloq_ng_ml`：用于判断 predose > LLOQ 和末端残留。
- `safety_cmax_ng_ml`、`safety_auc_ng_h_ml`：用于暴露超过阈值的概率计算。
- `elimination_model`、`vmax_ng_h`、`km_ng_ml`、`elimination_notes`：用于消除动力学判定。

### 2.3 目标外用剂型参数

字段位置：`product`。

核心参数：

- `dose_mg_per_application`：单次外用剂量。
- `applications_per_day` 和 `dosing_interval_h`：给药频次。
- `treatment_duration_h`：给药持续时间。
- `absorption_fraction_range`：系统可用吸收比例范围。
- `ka_skin_h_range`：慢速皮肤吸收速率范围。
- `depot_half_life_h_range`：皮肤 depot 释放半衰期范围。
- `lag_time_h_range`：慢速 depot 吸收延迟。
- `fast_absorption_*`：早期快速吸收通道参数。
- `interindividual_cv`、`bioavailability_cv`：个体差异和吸收差异。
- `variability_preset`：`low`、`medium`、`high`、`custom`；默认 medium = IIV CV 0.50、BA CV 0.40。
- `calibration_reference`：人体外用反向校准锚点。

## 3. 模型结构

当前模型是半机制模型：

```text
外用剂量
  ├─ 早期快速吸收通道 -> 中央室 -> 消除
  └─ 慢速皮肤 depot 通道 -> 皮肤库室 -> 中央室 -> 消除
```

### 3.1 早期快速吸收通道

早期快速吸收用于捕捉外用溶液等剂型首剂后数小时内出现的可测血药浓度和早期 Tmax。

参数：

- `fast_absorption_fraction_range`：总系统吸收量中进入快速通道的比例。
- `ka_fast_h_range`：快速吸收速率。
- `fast_lag_time_h_range`：快速吸收延迟。
V1.1 中 `early_apparent_volume_l_range` 不再作用于主模型，仅作为旧输入兼容字段记录为 deprecated；早期通道直接进入中央室。

### 3.2 慢速皮肤 depot 通道

慢速通道用于捕捉皮肤/毛囊滞留、持续释放和长半衰期下多次给药蓄积。

参数：

- `depot_half_life_h_range`：皮肤 depot 释放速度。
- `ka_skin_h_range`：皮肤库室进入中央室的速度。
- `lag_time_h_range`：慢速释放延迟。

### 3.3 消除模型

默认模型为一阶消除：

```text
ke = ln(2) / t1/2
eliminated = Acentral x (1 - exp(-ke x dt))
```

工具也保留了零阶和 Michaelis-Menten/容量限制消除接口：

- `elimination_model: zero_order` 且提供 `vmax_ng_h` 时使用固定速率消除。
- `elimination_model: michaelis_menten` 且提供 `vmax_ng_h` 和 `km_ng_ml` 时使用容量限制消除。
- 若只存在非线性风险信号，但没有 Vmax/Km，则默认仍按一阶消除运行，并在报告中标记外推风险。

## 4. 自动判定规则

### 4.1 早期快速吸收判定

自动判定字段：`enable_fast_absorption: auto`。

评分规则：

- 既往/公开外用 PK 出现 `Tmax <= 8 h`：+45。
- 既往/公开外用 PK 有可测早期 Cmax：+15。
- 目标剂型为 solution/spray/foam/溶液/喷雾/泡沫：+20。
- 载体含 ethanol/alcohol/propylene glycol/PEG/乙醇/丙二醇：+15。
- 分子量 <= 500 Da：+10；500-550 Da：+5。
- 单次外用剂量 >= 5 mg：+10。

V1.1 评分规则调整为：必须项（MW <= 600、logP 1-5、无角质层破坏）不满足时强制 insufficient；IVPT Jss、人体外用 Tmax/Cmax、促渗剂型、AUC0-8h/AUC0-t、剂量和负向 BLQ/动物证据共同评分。总分 >= 60 才启用；>=75 为 probable，50-74 为 possible，<50 为 insufficient。

### 4.2 消除动力学判定

判定逻辑：

- 用户明确指定 `first_order`、`zero_order` 或 `michaelis_menten` 时优先尊重输入。
- 来源说明出现 nonlinear、capacity、saturable、concentration-dependent、非线性、饱和、浓度依赖等词时，标记非线性风险。
- 半衰期 >= 168 h 时，提示长半衰期与末端采样风险，但长半衰期本身不等于零阶消除。
- 没有 Vmax/Km 时，即便存在非线性风险，也默认用一阶消除进行线性下界探索；如同时触发 P95 超参考暴露、高剂量外推或校准失败，`decision_gate` 会标记 blocked。

### 4.3 稳态时间

V1.1 不再用最终 predose 相对值估算稳态时间，改为：

```text
t_half_eff = max(t_half_ke, t_half_ka_fast, t_half_depot)
t_ss_90 = 3.32 x t_half_eff
t_ss_95 = 4.32 x t_half_eff
```

报告同时说明快通道和 depot 通道的近似稳态时间。

## 5. 蒙特卡洛模拟

默认从参数范围中随机抽样：

- 吸收比例、吸收速率、depot 半衰期、延迟时间。
- 使用 log-uniform 处理跨数量级参数。
- 使用 lognormal multiplier 表示个体差异和吸收差异。
- 输出 P5/P50/P95，而不是单点值。

主要输出：

- `simulation_results.csv`：各时间点浓度 P5/P50/P95。
- `simulation_metrics.csv`：每次模拟的个体 PK 指标。
- `simulation_summary.json`：暴露、风险、稳态时间和模型判定。

## 6. 采血点评分

候选采血点评分维度：

- Cmax/Tmax 捕捉。
- AUC 覆盖。
- Tmax 不确定性覆盖。
- 稳态 trough/predose。
- 末端相。
- LLOQ 附近残留判断。
- 操作可行性。

输出文件：`sampling_recommendation.csv`。

V1.1 按研究目的输出三套骨架：`exploratory`、`must_max_use`、`be_bridging`。MUsT/max-use 包含 Day 1 dense profile、稳态 trough、Day 28 末次给药后 dense profile 与长尾随访；BE/桥接报告自动提示长半衰期 + 浓度依赖清除需 PopPK 复核。

## 7. 当前主要参数来源

度他雄胺验证使用的公开参数来源包括：

- DailyMed/FDA Avodart 标签：口服 dutasteride 的 Tmax、生物利用度、Vd、稳态时间、半衰期和浓度依赖消除描述。
- Fossler et al. 2015：0.5 mg 口服 dutasteride 软胶囊 BE 研究，提供单次 Cmax、Tmax、AUC。
- Panuganti et al. 2025：0.05% 外用 dutasteride 溶液 Phase II 研究，提供早期外用 Tmax/Cmax 和长期低系统暴露线索。
- CDE 模型引导药物研发和 ICH M10 来源作为方法学/生物分析框架线索。

正式应用到其他分子时，需要重新建立该分子的公开 PK 参数表，不得直接复用度他雄胺的吸收参数。

## 8. 当前不适用范围

- 不能替代真实临床 PK、MUsT/max-use PK、BE 或 PopPK/PBPK。
- 不适合没有任何同一分子 PK 锚点的全新分子。
- 对强非线性消除、主动转运、皮肤代谢或高度处方依赖的产品，需要额外模型和数据。
- 对贴剂/系统透皮制剂，当前模型仅可作为参考，不是主适用场景。
