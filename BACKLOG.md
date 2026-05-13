# V1.2 / V2 Backlog

本清单记录 V1.1 已识别但本轮不实施的事项，避免把内部探索性工具一次性扩成未验证模型平台。

## Modeling

- Michaelis-Menten 双情景模拟：仅在取得可信 Vmax/Km 或浓度-清除率数据后启用。
- 多分子端到端校准：米诺地尔、双氯芬酸、他克莫司、阿达帕林、利多卡因、地塞米松。
- IVPT/IVRT 数据接入接口：Kp、flux、Jss 与载体相似度评分。
- 皮肤代谢室、主动转运、屏障破坏/微针/电导入扩展模型。

## Evidence

- 结构化 openFDA 字段抽取：从 label JSON 中提取 Cmax、Tmax、Vd、CL、t1/2、Rac、Tss，并与用户输入交叉校验。
- 安全阈值标签级自动来源对照。
- 文档双语化：核心字段中英对照、CRO 友好模板。

## Workflow

- 与 PBPK/PopPK 平台的"何时升级"决策文档。
- 报告 HTML 化：交互式风险灯号 dashboard。
- 独立代码复核记录模板：simulation.py / sampling.py / report.py。
