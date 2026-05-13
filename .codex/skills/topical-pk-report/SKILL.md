---
name: topical-pk-report
description: Generate a local Chinese report that uses all publicly available PK parameters from existing dosage forms of the same molecule to predict systemic exposure and PK sampling design for a new topical dosage form. Use when the user provides a molecule and target topical formulation, or asks to infer topical PK from oral/injectable/existing topical public PK data.
---

# Topical PK Report

## Overview

Use this skill to predict PK characteristics of a new topical dosage form by first building a same-molecule public PK evidence base across existing dosage forms.

The skill follows the V1.1 tool workflow and has four mandatory layers:

1. Public same-molecule PK evidence extraction: oral, injectable, existing topical, transdermal, or other known dosage forms.
2. Model assumption and mechanism judgment: absorption path, early fast absorption, local distribution, depot release, and elimination kinetics.
3. V1.1 decision gate review: calibration adequacy, safety-threshold source, dose extrapolation, nonlinear risk, terminal follow-up, and missing critical fields.
4. Prediction and report generation: systemic exposure, purpose-specific sampling, single-dose or multiple-dose metrics, reverse calibration, and dose sensitivity.

The companion local tool is distributed in the same GitHub repository as this skill. When running the tool, first locate the repository root by checking:

1. the current working directory, if it contains `pktool/` and `pyproject.toml`;
2. the environment variable `TOPICAL_PK_TOOL_ROOT`, if set;
3. a common clone path such as `~/Projects/topical-pk-report-skill`;
4. on the original authoring machine only, `/Users/huanglu/Projects/外用制剂PK采血点建模`.

Run commands from that repository root.

It generates run-specific inputs, fetches public evidence when requested, runs Monte Carlo exposure simulation, recommends purpose-specific sampling times, and creates Markdown/Excel reports plus structured CSV/JSON outputs.

## Minimum Runnable Input

For teammate-facing use, the skill can start from only four pieces of product information:

- specific molecule: `compound.compound_name`
- specific dosage form: `product.formulation`
- concentration: `product.concentration_percent_w_w`
- dosing amount: either `product.daily_amount_g` or `product.dose_mg_per_application`

Use `templates/minimal_input_template.yaml` when the user only has these basics. If `dose_mg_per_application` is missing, the tool derives it as:

```text
dose_mg_per_application = concentration_percent_w_w x 10 x daily_amount_g / applications_per_day
```

Generic fallback assumptions are applied only when same-molecule PK anchors are absent: half-life 12 h, V 50 L, medium variability, exploratory purpose, and conservative topical absorption ranges. These fallback values are not historical data for the molecule and must not be cited as evidence. The report must clearly mark them as default/model-derived assumptions and treat the output as exploratory only.

If the product is not once daily or single-application, also ask for `applications_per_day` and `treatment_duration_h`.

## Recommended Enhanced Input

Ask the user for only the missing items that materially affect the report:

- study purpose: `exploratory`, `must_max_use`, or `be_bridging`
- single-dose or multiple-dose duration
- treated area and max-use condition
- sampling purposes if different from the main study purpose
- variability preset: `low`, `medium`, or `high` when the user has a preference
- known reference PK anchor if available: half-life, V, CL, Cmax, AUC, LLOQ
- calibration reference if available: observed Cmax/Tmax/AUC from a same-molecule human topical or systemic anchor
- safety comparator thresholds and their sources, especially Cmax and AUC source text
- known PK characteristics of the same molecule in other dosage forms/routes, such as oral, injection, existing topical, or transdermal references

If exact absorption parameters are unavailable, proceed with conservative default ranges and mark them as assumptions.

For topical products, always clarify the actual amount applied, target body area, treatment area, frequency, and whether the scenario is intended to represent maximal use.

## Known Formulation PK Rule

Always try to capture same-molecule prior PK before simulation. Put these records in `known_formulations`:

- route and formulation
- dose or dose description
- single or multiple dosing and regimen duration
- Cmax, Tmax, AUC0-t, AUC0-inf, AUCtau, half-life, CL, V when available
- accumulation ratio, time to steady state, LLOQ/method, population, and formulation/vehicle when available
- protein binding, active metabolite, metabolism pathway, dose proportionality, and linear dose range when available
- source and whether it is the `primary_comparator`

Use non-topical systemic formulations, especially oral or injection, as the preferred systemic disposition anchor. Use existing topical data as local-delivery precedent or calibration evidence, not as a replacement for confirming the target product.

## Workflow

1. Create or update a YAML input file using `templates/minimal_input_template.yaml` for onboarding, or `templates/basic_input_template.yaml` for a fuller PK run.
2. Run from the project root:

```bash
python3 -m pktool.cli run-report --input <input_yaml>
```

Use `--no-fetch` when public evidence was already manually captured or when the run must avoid external network calls.

3. Review the generated run directory under `runs/`.
4. Read `simulation_summary.json`, `sampling_recommendation.csv`, `parameter_provenance.csv`, and `dose_extrapolation_sensitivity.csv` before summarizing.
5. Report the Markdown and Excel paths to the user and state the decision-gate status.

## Output

Default outputs include:

- `outputs/reports/pk_sampling_report.md`
- `outputs/reports/pk_sampling_report.xlsx`
- `outputs/simulation_summary.json`
- `outputs/sampling_recommendation.csv`
- `outputs/parameter_provenance.csv`
- `outputs/dose_extrapolation_sensitivity.csv`
- `outputs/simulation_metrics.csv`
- `outputs/simulation_results.csv`

The main structured V1.1 output block is `simulation_summary.json.decision_gate`.

## V1.1 Interpretation Rules

Always report the decision gate first:

- `ok`: model output can be used for internal planning within the stated assumptions.
- `warning`: usable only with explicit caveats; identify the warning trigger.
- `blocked_for_decision_use`: do not use for CRO SOW, final MUsT/max-use sampling schedule, regulatory exposure narrative, or IND/NDA decision text.

For multiple-dose runs, do not present `AUC0-inf` as the main conclusion. Use:

- `AUC_tau_ss`
- `AUC_0_T_studyend`
- `AUC_post_last_dose_to_inf`
- `Cmax_ss_per_cycle`
- `Cmax_global`
- `T_at_global_Cmax`

For single-dose runs, report `Cmax`, `Tmax`, `AUC0-t`, `AUC0-inf`, terminal concentration, AUC extrapolation percent, and reference ratios when available.

Sampling recommendations are purpose-specific:

- `exploratory`: broad curve learning and uncertainty reduction.
- `must_max_use`: maximal-use safety and accumulation-oriented sampling; conservative and decision-gated.
- `be_bridging`: comparison-oriented sampling for formulation bridging; emphasize aligned windows around Cmax and AUC.

Do not convert a `blocked_for_decision_use` output into a definitive clinical conclusion. Treat it as an escalation signal for observed PK, PopPK/PBPK, better calibration, or revised study assumptions.

## Guardrails

- Do not simulate a new topical formulation until same-molecule public PK parameters have been searched or the report clearly states the evidence gap.
- Do not present output as validated clinical PK or a replacement for MUsT/max-use PK.
- Do not use `blocked_for_decision_use` outputs for CRO SOW, final protocol sampling, regulatory communication, or IND/NDA exposure sections.
- Clearly separate public evidence, user input, default assumptions, and model output.
- Clearly separate same-molecule known formulation PK from predicted target topical exposure.
- Clearly distinguish a safety comparator from a true safety threshold. If the threshold source is missing or weak, state that it is not strong evidence.
- Public lookups are evidence cache only; PK parameters must be manually confirmed before regulatory use.
- Do not upload confidential formulation, raw PK data, or company SMILES lists to external services.
- Do not invent Vmax/Km, PopPK, PBPK, or nonlinear parameters. If nonlinear risk is detected but Vmax/Km are absent, report the gate trigger and keep the run exploratory.

## Required Public PK Evidence Table

For each known dosage form, capture as many of these as available:

- route and dosage form
- dose, regimen, single/multiple dosing
- Cmax, Tmax, AUC0-t, AUC0-inf, AUCtau, Cavg, Ctrough
- half-life, CL/F or CL, V/F or V, bioavailability
- accumulation ratio, steady-state timing, washout/detectability
- LLOQ and bioanalytical method if available
- source URL, publication/label/review package, and whether the value is directly quoted or derived

If the existing public data conflict, keep multiple records and mark the primary comparator explicitly. Do not silently average across routes or studies.

## Mechanism Judgments

Before prediction, document:

- whether early fast absorption is supported and why
- whether a skin/local depot is expected and why
- whether elimination is first-order, zero-order, or capacity-limited/nonlinear
- whether the intended topical dose enters a concentration range where oral PK nonlinearity may matter
- whether the model output is calibrated to existing topical data or only anchored to non-topical systemic PK
- whether the terminal follow-up covers enough half-lives for AUC extrapolation
- whether reverse calibration passes, warns, or fails, and whether vehicle match is adequate
