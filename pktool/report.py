from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

from .io_utils import ensure_dir, read_json


def _fmt(value: Any, digits: int = 3) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "" if value is None else str(value)
    if pd.isna(numeric):
        return ""
    if abs(numeric) >= 100:
        return f"{numeric:.1f}"
    if abs(numeric) >= 10:
        return f"{numeric:.2f}"
    return f"{numeric:.{digits}f}"


def _cell(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    return str(value)


def _data_path(simulation_path: str | Path, filename: str) -> Path:
    return Path(simulation_path).parent / filename


def _known_formulations_path(simulation_path: str | Path) -> Path:
    return Path(simulation_path).parent.parent / "data" / "known_formulations_pk.csv"


def _gate_banner(summary: dict[str, Any]) -> list[str]:
    gate = summary.get("decision_gate", {})
    status = gate.get("status", "ok")
    if status == "blocked_for_decision_use":
        return [
            "> **DECISION GATE: BLOCKED FOR DECISION USE**",
            ">",
            "> 本报告 P95 暴露、剂量外推或校准结果已触发决策闸门。当前一阶消除模拟可能系统性低估真实蓄积或无法支撑高浓度外推。",
            ">",
            "> **请勿用于**：CRO SOW、MUsT 方案最终采血点、监管沟通材料、IND 暴露章节。",
            "> **可用于**：内部风险识别、敏感性讨论、PopPK/PBPK 升级触发依据。",
            "",
        ]
    if status == "warning":
        return [
            "> **DECISION GATE: WARNING**",
            ">",
            "> 本报告存在证据字段、末端随访、校准锚点或安全阈值来源缺口。仅可作为内部探索性讨论材料。",
            "",
        ]
    return []


def _risk_light_lines(summary: dict[str, Any]) -> list[str]:
    gate = summary.get("decision_gate", {})
    color = gate.get("risk_light", "green")
    label = {"green": "绿", "yellow": "黄", "red": "红"}.get(color, color)
    triggers = "；".join(gate.get("triggers", [])) or "无"
    metrics = gate.get("metrics", {})
    return [
        f"- 风险灯号：{label}",
        f"- Gate 状态：{gate.get('status', 'ok')}",
        f"- 触发项：{triggers}",
        f"- P95 Cmax / 参考 Css：{_fmt(metrics.get('p95_cmax_ng_ml'))} / {_fmt(metrics.get('reference_cmax_or_css_ng_ml'))} ng/mL",
        f"- P95 AUC ratio：{_fmt(metrics.get('p95_auc_ratio'))}",
        f"- 末端随访倍数：{_fmt(metrics.get('terminal_followup_x_t_half'))} x t1/2",
    ]


def _metric_table(summary: dict[str, Any]) -> list[str]:
    is_multiple = bool(summary.get("is_multiple_dose"))
    metric_names = {
        "cmax_ss_per_cycle_ng_ml": "Cmax_ss_per_cycle (ng/mL)",
        "auc_tau_ss_ng_h_ml": "AUC_tau_ss (ng*h/mL)",
        "cmax_global_ng_ml": "Cmax_global (ng/mL)",
        "t_at_global_cmax_h": "T_at_global_Cmax (h)",
        "auc_0_t_studyend_ng_h_ml": "AUC_0_T_studyend (ng*h/mL)",
        "auc_post_last_dose_to_inf_ng_h_ml": "AUC_post_last_dose_to_inf (ng*h/mL)",
        "cmax_ng_ml": "Cmax (ng/mL)",
        "tmax_h": "Tmax (h)",
        "auc0_t_ng_h_ml": "AUC0-t (ng*h/mL)",
        "auc0_inf_ng_h_ml": "AUC0-inf (ng*h/mL)",
        "auc_extrap_pct": "AUC_%Extrap",
        "cavg_ng_ml": "Cavg (ng/mL)",
        "ctrough_ng_ml": "Ctrough (ng/mL)",
        "rac": "Rac",
        "terminal_concentration_ng_ml": "末端浓度 (ng/mL)",
        "auc_ratio_reference": "AUC_topical / AUC_reference",
        "cmax_ratio_reference": "Cmax_topical / Cmax_reference",
        "time_to_90pct_steady_state_h": "达到90%稳态时间 (h)",
        "time_to_95pct_steady_state_h": "达到95%稳态时间 (h)",
        "time_to_99pct_steady_state_h": "达到接近100%(99%)稳态时间 (h)",
    }
    if is_multiple:
        order = [
            "cmax_ss_per_cycle_ng_ml",
            "auc_tau_ss_ng_h_ml",
            "cmax_global_ng_ml",
            "t_at_global_cmax_h",
            "auc_0_t_studyend_ng_h_ml",
            "auc_post_last_dose_to_inf_ng_h_ml",
            "cavg_ng_ml",
            "ctrough_ng_ml",
            "rac",
            "auc_ratio_reference",
            "cmax_ratio_reference",
        ]
    else:
        order = [
            "cmax_ng_ml",
            "tmax_h",
            "auc0_t_ng_h_ml",
            "auc0_inf_ng_h_ml",
            "auc_extrap_pct",
            "terminal_concentration_ng_ml",
            "auc_ratio_reference",
            "cmax_ratio_reference",
        ]
    lines = ["| 指标 | P5 | P50 | P95 |", "|---|---:|---:|---:|"]
    for key in order:
        q = summary.get("metric_quantiles", {}).get(key)
        if q:
            lines.append(f"| {metric_names[key]} | {_fmt(q.get('p5'))} | {_fmt(q.get('p50'))} | {_fmt(q.get('p95'))} |")
    return lines


def _steady_state_lines(summary: dict[str, Any]) -> list[str]:
    ss = summary.get("systemic_pk", {}).get("steady_state_assessment", {})
    if not ss:
        return ["- 未记录稳态时间评估。"]
    return [
        f"- t1/2_eff：{_fmt(ss.get('t_half_eff_h'))} h",
        f"- 50% 稳态时间：{_fmt(ss.get('t_ss_50_h'))} h",
        f"- 75% 稳态时间：{_fmt(ss.get('t_ss_75_h'))} h",
        f"- 90% 稳态时间：{_fmt(ss.get('t_ss_90_h'))} h",
        f"- 95% 稳态时间：{_fmt(ss.get('t_ss_95_h'))} h",
        f"- 接近 100% 稳态时间（按 99% 计）：{_fmt(ss.get('t_ss_99_h'))} h",
        f"- 计算口径：{ss.get('method', '')}",
    ]


def _frequency_ss_lines(summary: dict[str, Any]) -> list[str]:
    rows = summary.get("systemic_pk", {}).get("steady_state_assessment", {}).get("by_frequency", [])
    if not rows:
        return ["- 未生成给药频率-稳态时间矩阵。"]
    lines = [
        "| 给药频率 | 给药间隔(h) | 稳态比例 | 理论时间(h) | 理论时间(day) | 首个不早于该时间的给药次序 | 对应给药时间(day) |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {_cell(row.get('frequency_label'))} | {_fmt(row.get('dosing_interval_h'), 1)} | {_cell(row.get('target_label'))} | {_fmt(row.get('theoretical_time_h'), 1)} | {_fmt(row.get('theoretical_time_day'), 2)} | {_cell(row.get('first_dose_number_at_or_after'))} | {_fmt(row.get('first_dose_time_day'), 2)} |"
        )
    lines.append("")
    lines.append("- 注：100% 稳态为理论渐近值，表中“接近100%”按 99% 稳态计算。")
    return lines


def _exposure_section_lines(summary: dict[str, Any]) -> list[str]:
    lines = [
        "## 3. 系统暴露预测",
        "",
        "### 3.1 暴露指标预测",
        "",
        *_metric_table(summary),
    ]
    if summary.get("is_multiple_dose"):
        lines.extend(
            [
                "",
                "### 3.2 稳态时间口径",
                "",
                *_steady_state_lines(summary),
                "",
                "### 3.3 不同给药频率下的稳态时间",
                "",
                *_frequency_ss_lines(summary),
            ]
        )
    return lines


def _risk_lines(summary: dict[str, Any]) -> list[str]:
    labels = {
        "predose_gt_lloq_probability": "predose > LLOQ 概率",
        "auc_extrap_gt_20_probability": "AUC_%Extrap > 20% 概率",
        "cmax_gt_safety_threshold_probability": "Cmax 超过安全阈值概率",
        "auc_gt_safety_threshold_probability": "AUC 超过安全阈值概率",
    }
    source_missing = "safety_threshold_source_missing" in summary.get("decision_gate", {}).get("triggers", [])
    lines = []
    for key, label in labels.items():
        if key in summary.get("risk_summary", {}):
            suffix = "（阈值来源未充分解释）" if source_missing and "safety" in key else ""
            lines.append(f"- {label}：{_fmt(summary['risk_summary'][key] * 100, 2)}%{suffix}")
    return lines or ["- 未设置 LLOQ 或安全阈值，风险概率未完整计算。"]


def _fast_absorption_lines(summary: dict[str, Any]) -> list[str]:
    assessment = summary.get("parameter_ranges", {}).get("fast_absorption_assessment", {})
    if not assessment:
        return ["- 未记录早期快速吸收判定。"]
    status = "启用" if assessment.get("enabled") else "未启用"
    lines = [
        f"- 判定结果：{status}",
        f"- 证据等级：{assessment.get('level', '')}",
        f"- 评分：{assessment.get('score', '')}",
    ]
    if assessment.get("manual_override"):
        lines.append(f"- 自动判定：{assessment.get('auto_level')} / {assessment.get('auto_score')} 分；用户手动覆盖。")
    for reason in assessment.get("reasons", []):
        lines.append(f"- 判定依据：{reason}")
    return lines


def _elimination_lines(summary: dict[str, Any]) -> list[str]:
    assessment = summary.get("systemic_pk", {}).get("elimination_assessment", {})
    if not assessment:
        return ["- 未记录消除动力学判定。"]
    labels = {
        "first_order": "一阶消除",
        "zero_order": "零阶消除",
        "michaelis_menten": "容量限制/Michaelis-Menten 消除",
    }
    model = assessment.get("model", "")
    lines = [
        f"- 当前模型：{labels.get(model, model)}",
        f"- 证据等级：{assessment.get('level', '')}",
        f"- 是否支持零阶消除：{'是' if assessment.get('zero_order_supported') else '否'}",
        f"- 是否存在非线性风险信号：{'是' if assessment.get('nonlinear_flag') else '否'}",
    ]
    for reason in assessment.get("reasons", []):
        lines.append(f"- 判定依据：{reason}")
    return lines


def _known_formulations_lines(known: pd.DataFrame) -> list[str]:
    if known.empty:
        return ["未录入同一分子既往剂型 PK 信息；当前模型仅使用基础 PK 锚点和默认假设。"]
    lines = [
        "| 剂型/给药途径 | 剂量 | Cmax (ng/mL) | Tmax (h) | AUC (ng*h/mL) | t1/2 (h) | 来源 | 用途 |",
        "|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for _, row in known.iterrows():
        auc = _cell(row.get("auc_ng_h_ml")) or _cell(row.get("auc0_t_ng_h_ml")) or _cell(row.get("auc0_inf_ng_h_ml"))
        route_form = " / ".join(part for part in [_cell(row.get("route")), _cell(row.get("formulation"))] if part)
        purpose = "主比较锚点" if str(row.get("primary_comparator", "")).lower() in {"true", "1", "yes", "y"} else "背景证据"
        lines.append(
            f"| {route_form} | {_cell(row.get('dose_mg')) or _cell(row.get('dose_description'))} | {_cell(row.get('cmax_ng_ml'))} | {_cell(row.get('tmax_h'))} | {auc} | {_cell(row.get('half_life_h'))} | {_cell(row.get('source'))} | {purpose} |"
        )
    return lines


def _gap_lines(summary: dict[str, Any]) -> list[str]:
    gaps = summary.get("known_formulation_gaps", [])
    if not gaps:
        return ["- 未发现 known_formulations 关键字段缺口。"]
    lines = ["| 记录 | 缺失字段 |", "|---|---|"]
    for gap in gaps:
        lines.append(f"| {_cell(gap.get('record'))} | {', '.join(gap.get('missing_fields', []))} |")
    return lines


def _provenance_lines(provenance: pd.DataFrame) -> list[str]:
    if provenance.empty:
        return ["- 未生成 parameter_provenance.csv。"]
    lines = ["| 参数 | 值 | provenance | 来源 |", "|---|---:|---|---|"]
    for _, row in provenance.head(80).iterrows():
        lines.append(f"| {_cell(row.get('parameter'))} | {_cell(row.get('value'))} | {_cell(row.get('provenance'))} | {_cell(row.get('source'))} |")
    return lines


def _calibration_lines(summary: dict[str, Any]) -> list[str]:
    cal = summary.get("calibration_assessment", {})
    if not cal:
        return ["- 未记录反向校准。"]
    lines = [
        f"- 校准状态：{cal.get('status', '')}",
        f"- 来源：{cal.get('source_citation', '')}",
        f"- 观测 Tmax/Cmax：{_fmt(cal.get('observed_tmax_h'))} h / {_fmt(cal.get('observed_cmax_ng_ml'))} ng/mL",
        f"- F proxy：{_fmt(cal.get('f_proxy'))}",
    ]
    for msg in cal.get("messages", []):
        lines.append(f"- {msg}")
    return lines


def _sensitivity_lines(sensitivity: pd.DataFrame) -> list[str]:
    if sensitivity.empty:
        return ["- 未生成 dose_extrapolation_sensitivity.csv。"]
    lines = ["| 剂量指数 | 外推倍数 | Cmax P50 | Cmax P95 | AUC P50 | AUC P95 |", "|---:|---:|---:|---:|---:|---:|"]
    for _, row in sensitivity.iterrows():
        lines.append(
            f"| {_fmt(row.get('dose_extrapolation_exponent'))} | {_fmt(row.get('dose_extrapolation_factor'))} | {_fmt(row.get('cmax_p50_ng_ml'))} | {_fmt(row.get('cmax_p95_ng_ml'))} | {_fmt(row.get('auc_p50_ng_h_ml'))} | {_fmt(row.get('auc_p95_ng_h_ml'))} |"
        )
    return lines


def create_figures(
    simulation_path: str | Path = "outputs/simulation_results.csv",
    sampling_path: str | Path = "outputs/sampling_recommendation.csv",
    figures_dir: str | Path = "outputs/figures",
) -> list[Path]:
    figures = []
    figures_dir = ensure_dir(figures_dir)
    sim = pd.read_csv(simulation_path)
    sampling = pd.read_csv(sampling_path) if Path(sampling_path).exists() else pd.DataFrame()

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.fill_between(sim["time_h"], sim["concentration_p5_ng_ml"], sim["concentration_p95_ng_ml"], alpha=0.2, label="P5-P95")
    ax.plot(sim["time_h"], sim["concentration_p50_ng_ml"], label="P50", linewidth=2)
    if "lloq_ng_ml" in sim and sim["lloq_ng_ml"].iloc[0] > 0:
        ax.axhline(sim["lloq_ng_ml"].iloc[0], linestyle="--", linewidth=1, color="gray", label="LLOQ")
    if not sampling.empty and "recommended" in sampling:
        shown = sampling[(sampling["recommended"] == True) & (sampling["candidate_time_h"] >= 0)]  # noqa: E712
        max_time = float(sim["time_h"].max())
        for hour in shown.loc[shown["candidate_time_h"] <= max_time, "candidate_time_h"].head(30):
            ax.axvline(hour, color="tab:red", alpha=0.12)
    ax.set_xlabel("Time (h)")
    ax.set_ylabel("Concentration (ng/mL)")
    ax.set_title("Predicted concentration-time band")
    ax.legend()
    ax.grid(alpha=0.2)
    concentration_path = figures_dir / "concentration_time_band.png"
    fig.tight_layout()
    fig.savefig(concentration_path, dpi=180)
    plt.close(fig)
    figures.append(concentration_path)

    summary = read_json(Path(simulation_path).parent / "simulation_summary.json", default={}) or {}
    metrics = summary.get("metric_quantiles", {})
    selected = ["cmax_ss_per_cycle_ng_ml", "auc_tau_ss_ng_h_ml", "cmax_global_ng_ml", "auc_0_t_studyend_ng_h_ml"]
    if not summary.get("is_multiple_dose"):
        selected = ["cmax_ng_ml", "auc0_t_ng_h_ml", "auc0_inf_ng_h_ml", "terminal_concentration_ng_ml"]
    labels = ["Cmax_ss", "AUCtau", "Cmax_global", "AUC0-T"] if summary.get("is_multiple_dose") else ["Cmax", "AUC0-t", "AUC0-inf", "Terminal C"]
    values = [metrics.get(key, {}).get("p50", 0) for key in selected]
    lower = [max(metrics.get(key, {}).get("p50", 0) - metrics.get(key, {}).get("p5", 0), 0) for key in selected]
    upper = [max(metrics.get(key, {}).get("p95", 0) - metrics.get(key, {}).get("p50", 0), 0) for key in selected]
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(labels, values, yerr=[lower, upper], capsize=4, color="#4575b4")
    ax.set_title("Exposure quantiles (P50 with P5-P95 interval)")
    ax.grid(axis="y", alpha=0.2)
    exposure_path = figures_dir / "exposure_quantiles.png"
    fig.tight_layout()
    fig.savefig(exposure_path, dpi=180)
    plt.close(fig)
    figures.append(exposure_path)
    return figures


def generate_report(
    simulation_path: str | Path = "outputs/simulation_results.csv",
    metrics_path: str | Path = "outputs/simulation_metrics.csv",
    sampling_path: str | Path = "outputs/sampling_recommendation.csv",
    evidence_manifest_path: str | Path = "data/evidence_cache/evidence_manifest.csv",
    formats: str = "md,xlsx",
    reports_dir: str | Path = "outputs/reports",
) -> list[Path]:
    reports_dir = ensure_dir(reports_dir)
    outputs: list[Path] = []

    summary_path = Path(simulation_path).parent / "simulation_summary.json"
    summary = read_json(summary_path, default={}) or {}
    sim = pd.read_csv(simulation_path)
    metrics = pd.read_csv(metrics_path) if Path(metrics_path).exists() else pd.DataFrame()
    sampling = pd.read_csv(sampling_path) if Path(sampling_path).exists() else pd.DataFrame()
    evidence = pd.read_csv(evidence_manifest_path) if Path(evidence_manifest_path).exists() else pd.DataFrame()
    known_path = _known_formulations_path(simulation_path)
    known_formulations = pd.read_csv(known_path) if known_path.exists() else pd.DataFrame()
    provenance = pd.read_csv(_data_path(simulation_path, "parameter_provenance.csv")) if _data_path(simulation_path, "parameter_provenance.csv").exists() else pd.DataFrame()
    sensitivity = pd.read_csv(_data_path(simulation_path, "dose_extrapolation_sensitivity.csv")) if _data_path(simulation_path, "dose_extrapolation_sensitivity.csv").exists() else pd.DataFrame()
    create_figures(simulation_path, sampling_path)

    requested = {item.strip().lower() for item in formats.split(",") if item.strip()}
    if "md" in requested or "markdown" in requested:
        report_path = reports_dir / "pk_sampling_report.md"
        recommended = sampling[sampling["recommended"] == True].sort_values(["purpose", "candidate_time_h"]) if not sampling.empty else pd.DataFrame()  # noqa: E712
        lines = [
            "# 外用制剂系统暴露预测与 PK 采血点建议报告",
            "",
            *_gate_banner(summary),
            "## 0. 风险灯号汇总",
            "",
            *_risk_light_lines(summary),
            "",
            "## 1. 结论摘要",
            "",
            f"- pktool 版本：{summary.get('pktool_version', '')}",
            f"- 模拟次数：{summary.get('n_simulations', '')}",
            f"- 随机种子：{summary.get('random_seed', '')}",
            f"- 模拟时长：{_fmt(summary.get('duration_h'))} h",
            f"- 给药间隔：{_fmt(summary.get('dosing_interval_h'))} h",
            f"- 单次外用剂量：{_fmt(summary.get('dose_mg_per_application'))} mg",
            f"- 解释边界：{summary.get('interpretation_boundary', '模型预测，仅供内部讨论。')}",
            "",
            "## 1.5 参数来源分列",
            "",
            *_provenance_lines(provenance),
            "",
            "## 2. 同一分子既往剂型 PK 特征",
            "",
            *_known_formulations_lines(known_formulations),
            "",
            *_exposure_section_lines(summary),
            "",
            "## 4. 早期快速吸收判定",
            "",
            *_fast_absorption_lines(summary),
            "",
            "## 5. 消除动力学判定",
            "",
            *_elimination_lines(summary),
            "",
            "## 6. 风险信号",
            "",
            *_risk_lines(summary),
            "",
            "## 6.5 关键字段缺口",
            "",
            *_gap_lines(summary),
            "",
            "## 7. 推荐采血点",
            "",
        ]
        if recommended.empty:
            lines.append("未生成采血点推荐。")
        else:
            lines.extend(["| 采血目的 | 时间 (h) | 阶段 | 目的 | P50浓度 | P95浓度 |", "|---|---:|---|---|---:|---:|"])
            for _, row in recommended.iterrows():
                lines.append(
                    f"| {row['purpose']} | {_fmt(row['candidate_time_h'], 1)} | {_cell(row.get('stage'))} | {_cell(row.get('sample_intent'))} | {_fmt(row.get('concentration_p50_ng_ml'))} | {_fmt(row.get('concentration_p95_ng_ml'))} |"
                )
            if "be_bridging" in set(recommended["purpose"]):
                lines.append("")
                lines.append("- BE/桥接提示：长半衰期 + 浓度依赖清除药物通常不适合直接套用传统 80-125% 判定，应考虑 PopPK 桥接或临床实测。")
        lines.extend(["", "## 8. 公开证据与来源", ""])
        if evidence.empty:
            lines.append("未检索或登记公开证据。")
        else:
            shown = evidence.tail(20)
            lines.extend(["| 来源 | 查询词 | 字段 | 状态 | 来源链接 |", "|---|---|---|---|---|"])
            for _, row in shown.iterrows():
                lines.append(
                    f"| {_cell(row.get('source', ''))} | {_cell(row.get('query', ''))} | {_cell(row.get('field', ''))} | {_cell(row.get('status', ''))} | {_cell(row.get('source_url', ''))} |"
                )
        warnings = summary.get("systemic_pk", {}).get("warnings", [])
        lines.extend(["", "## 9. 模型假设与限制", ""])
        lines.append("- 在线检索结果仅作为公开证据缓存；真实 PK 参数必须人工确认后进入模型。")
        lines.append("- 同一分子既往剂型 PK 用于约束系统处置参数和暴露比较；不同给药途径的 F、剂量线性和人群差异需单独判断。")
        lines.append("- 外用吸收参数来自输入区间和默认假设，需用 IVRT/IVPT、探索性 PK 或同类案例校准。")
        lines.append("- 本模型不替代真实 MUsT/max-use PK、BE、PopPK、PBPK 或临床药理研究。")
        for warning in warnings:
            lines.append(f"- {warning}")
        gate_metrics = summary.get("decision_gate", {}).get("metrics", {})
        lines.extend(
            [
                "",
                "## 9.5 末端随访充分性评估",
                "",
                f"- post-last-dose follow-up：{_fmt(gate_metrics.get('post_last_followup_h'))} h",
                f"- actual_followup_x_t_half：{_fmt(gate_metrics.get('terminal_followup_x_t_half'))}",
                "",
                "## 10. 安全阈值来源审核",
                "",
                f"- safety_cmax_source：{summary.get('compound', {}).get('safety_cmax_source', '')}",
                f"- safety_auc_source：{summary.get('compound', {}).get('safety_auc_source', '')}",
                f"- interpretation：{summary.get('compound', {}).get('safety_threshold_interpretation', '')}",
                "",
                "## 11. 反向校准结果",
                "",
                *_calibration_lines(summary),
                "",
                "## 12. 剂量外推敏感性",
                "",
                *_sensitivity_lines(sensitivity),
            ]
        )
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        outputs.append(report_path)

    if "xlsx" in requested or "excel" in requested:
        xlsx_path = reports_dir / "pk_sampling_report.xlsx"
        with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
            gate_df = pd.DataFrame(
                [
                    {
                        "status": summary.get("decision_gate", {}).get("status", "ok"),
                        "risk_light": summary.get("decision_gate", {}).get("risk_light", "green"),
                        "triggers": "; ".join(summary.get("decision_gate", {}).get("triggers", [])),
                    }
                ]
            )
            gate_df.to_excel(writer, index=False, sheet_name="decision_gate")
            pd.DataFrame([summary.get("risk_summary", {})]).to_excel(writer, index=False, sheet_name="risk_summary")
            pd.DataFrame(summary.get("metric_quantiles", {})).T.to_excel(writer, sheet_name="metric_quantiles")
            ss_rows = summary.get("systemic_pk", {}).get("steady_state_assessment", {}).get("by_frequency", [])
            if ss_rows:
                pd.DataFrame(ss_rows).to_excel(writer, index=False, sheet_name="ss_by_frequency")
            if provenance.empty is False:
                provenance.to_excel(writer, index=False, sheet_name="parameter_provenance")
            if sensitivity.empty is False:
                sensitivity.to_excel(writer, index=False, sheet_name="dose_sensitivity")
            sim.to_excel(writer, index=False, sheet_name="time_profile")
            if not metrics.empty:
                metrics.describe(include="all").to_excel(writer, sheet_name="metrics_describe")
                metrics.head(5000).to_excel(writer, index=False, sheet_name="metrics_sample")
            if not sampling.empty:
                sampling.to_excel(writer, index=False, sheet_name="sampling")
            if not known_formulations.empty:
                known_formulations.to_excel(writer, index=False, sheet_name="known_formulations")
            if not evidence.empty:
                evidence.tail(1000).to_excel(writer, index=False, sheet_name="evidence_manifest")

            workbook = writer.book
            sheet = workbook["decision_gate"]
            from openpyxl.styles import Font, PatternFill

            status = summary.get("decision_gate", {}).get("status", "ok")
            color = "C00000" if status == "blocked_for_decision_use" else "FFC000" if status == "warning" else "70AD47"
            fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
            for cell in sheet[1]:
                cell.fill = fill
                cell.font = Font(bold=True, color="FFFFFF")
        outputs.append(xlsx_path)

    return outputs
