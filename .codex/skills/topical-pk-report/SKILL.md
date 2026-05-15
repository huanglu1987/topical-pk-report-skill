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

The companion local tool is distributed in the same GitHub repository as this skill. A valid run must execute `python3 -m pktool.cli run-report`; otherwise it is not a tool-generated report.

Before creating any report, run this preflight:

```bash
python3 -m pktool.cli --help
```

If this fails, run the installed skill checker:

```bash
python3 ~/.codex/skills/topical-pk-report/scripts/check_pktool_install.py
```

If the checker finds a local companion repository, install it with:

```bash
python3 ~/.codex/skills/topical-pk-report/scripts/check_pktool_install.py --install
```

If no companion repository is found, tell the user to clone and install the full GitHub repository. Do not continue to generate a manual Markdown report.

When running the tool, locate the repository root by checking:

1. the current working directory, if it contains `pktool/` and `pyproject.toml`;
2. the marker file `~/.codex/skills/topical-pk-report/.pktool_root`, if present;
3. the environment variable `TOPICAL_PK_TOOL_ROOT`, if set;
4. a common clone path such as `~/Projects/topical-pk-report-skill`;
5. on the original authoring machine only, `/Users/huanglu/Projects/外用制剂PK采血点建模`.

Run commands from that repository root.

It generates run-specific inputs, fetches public evidence when requested, runs Monte Carlo exposure simulation, recommends purpose-specific sampling times, and creates Markdown/Excel reports plus structured CSV/JSON outputs.

For reproducibility checks, do not recreate YAML from natural language. Use the locked YAML files under `data/reproducible_inputs/` from the companion repository, especially for the dutasteride 2% 20 mg single, daily-QD, and weekly-QW reference runs. These files fix the input assumptions, random seed, and simulation count used by the reference reports.

## No Fallback Rule

If `pktool` is not installed or cannot be located, stop and report the installation problem. Do not write a substitute narrative report, do not say a Monte Carlo report was generated, and do not create a Markdown file with a different structure. The expected report must come from `outputs/reports/pk_sampling_report.md` under a `runs/<timestamp>_<compound>/` directory.

## Minimum Runnable Input

For teammate-facing use, the skill can start from five baseline pieces of product information. Multiple-dose use has one additional required field for dosing frequency.

- specific molecule: `compound.compound_name`
- specific dosage form: `product.formulation`
- concentration: `product.concentration_percent_w_w`
- dosing amount: either `product.daily_amount_g` or `product.dose_mg_per_application`
- dosing scenario: `study_design.dosing_scenario`, either `single` or `multiple`
- multiple-dose frequency, required only when `dosing_scenario: multiple`: `study_design.dosing_frequency` (`daily_qd`, `weekly_qw`, `weekly_biw`) or `product.dosing_interval_h` in hours

Use `templates/minimal_input_template.yaml` when the user only has these basics. If `dose_mg_per_application` is missing, the tool derives it as:

```text
dose_mg_per_application = concentration_percent_w_w x 10 x daily_amount_g / applications_per_day
```

Copyable minimal single-dose YAML:

```yaml
compound:
  compound_name: "dutasteride"
  # Optional but strongly recommended when available:
  # half_life_h: 840
  # volume_l: 400

product:
  formulation: "solution"
  concentration_percent_w_w: 2.0
  dose_mg_per_application: 20
  applications_per_day: 1

study_design:
  dosing_scenario: "single"
  purpose: "exploratory"
  sampling_purposes: ["exploratory"]
  n_simulations: 3000
  random_seed: 20260515

evidence:
  pubchem: false
  fda: false
  cde: false

report:
  format: "md,xlsx"
```

Copyable minimal multiple-dose YAML:

```yaml
compound:
  compound_name: "dutasteride"
  # Optional but strongly recommended when available:
  # half_life_h: 840
  # volume_l: 400

product:
  formulation: "solution"
  concentration_percent_w_w: 2.0
  dose_mg_per_application: 20
  applications_per_day: 1

study_design:
  dosing_scenario: "multiple"
  dosing_frequency: "daily_qd"
  dosing_frequency_scenarios:
    - name: "daily_qd"
      label: "每日一次"
      dosing_interval_h: 24
    - name: "weekly_qw"
      label: "每周一次"
      dosing_interval_h: 168
    - name: "weekly_biw"
      label: "每周两次"
      dosing_interval_h: 84
  purpose: "exploratory"
  sampling_purposes: ["exploratory"]
  n_simulations: 3000
  random_seed: 20260515

evidence:
  pubchem: false
  fda: false
  cde: false

report:
  format: "md,xlsx"
```

For multiple-dose minimal YAML, do not add `duration_h`, `dosing_duration_h`, or `product.treatment_duration_h` unless intentionally overriding the default steady-state window.

Minimal YAML is not a reproducibility input. If no half-life or known formulation PK anchor is provided, the default steady-state window is calculated from model defaults and may coincidentally be 672 h for daily dosing; this is not a fixed 28-day rule. For dutasteride 2% 20 mg report reproduction, use the locked YAML files under `data/reproducible_inputs/`.

The copyable minimal templates default to `n_simulations: 3000` so P95/P5 tail estimates are less noisy. For quick smoke testing only, temporarily reduce it to `1000`.

Generic fallback assumptions are applied only when same-molecule PK anchors are absent: half-life 12 h, V 50 L, medium variability, exploratory purpose, and conservative topical absorption ranges. These fallback values are not historical data for the molecule and must not be cited as evidence. The report must clearly mark them as default/model-derived assumptions and treat the output as exploratory only.

If the product is multiple-dose, do not proceed until the frequency is explicit. If the product is not once daily or single-application, also ask for `applications_per_day`, `product.dosing_interval_h`, and `treatment_duration_h` as applicable.

## New Project Reproducibility Rule

For a new project, the same skill plus the same minimal natural-language input is not enough to guarantee the same result. A reproducible main analysis requires a locked analysis package. Before running or comparing reports, explicitly fix the items below in the YAML or generated input snapshot:

- project facts: compound, formulation, concentration, active dose, application frequency, treated site/area, single vs multiple dosing, max-use intent, and study purpose.
- primary comparator rule: one declared main PK anchor for the main analysis, with other public PK records kept as background evidence unless they are named sensitivity scenarios.
- model assumptions: `absorption_fraction_range`, `ka_skin_h_range`, `depot_half_life_h_range`, `lag_time_h_range`, `enable_fast_absorption`, fast-absorption ranges if used, `variability_preset`, `n_simulations`, `random_seed`, simulation duration/time-step overrides, and safety comparator sources.
- tool and evidence state: `pktool` version, fetch/no-fetch choice, manually confirmed public evidence, and any run-specific input files under the generated `runs/<timestamp>_<compound>/inputs/` directory.

Anchor selection must follow this hierarchy unless the user intentionally requests a sensitivity scenario:

1. same molecule with the closest route, body site, formulation/use condition, and single/multiple dosing scenario.
2. for a single-dose target, prefer single-dose human PK anchors; use repeated-dose, steady-state, or max-use anchors as background or conservative sensitivity only.
3. for a multiple-dose, steady-state, or max-use target, prefer repeated-dose, steady-state, or max-use anchors that match the intended use condition.
4. skin-target products should prefer skin-application data over nail, mucosal, oral, or injectable data; less-matched routes are disposition context or background evidence, not the default main comparator.
5. if no well-matched anchor exists, keep the run exploratory, document the mismatch, and do not silently promote a weak anchor to decision-grade evidence.

Fast absorption is `auto` by default. Set `enable_fast_absorption: true` only when there is explicit support such as observed early human topical Tmax, IVPT/Jss evidence, formulation/vehicle evidence for rapid systemic entry, or a user-approved conservative sensitivity run. If the automatic assessment is insufficient and the user manually turns it on, label the run as a sensitivity scenario, not the main analysis.

Sensitivity analyses are allowed and encouraged, but they must be separate named scenarios. Change one major assumption at a time where possible, such as high absorption, slow depot, fast absorption on, alternative comparator, longer terminal follow-up, or higher variability. Do not merge sensitivity assumptions into the main-analysis conclusion.

Default duration logic:

- `single`: defaults to one application over 24 h. The simulation window is at least 168 h and is extended to at least 3 x `t_half_eff` for long half-life or slow depot products, so terminal elimination has at least two late follow-up points.
- `multiple`: requires `study_design.dosing_frequency` or `product.dosing_interval_h`; when only the frequency is provided, defaults to a dosing window that reaches the near-100% steady-state dose time. Near-100% means 99%, because true 100% is a theoretical asymptote. The simulation window then adds at least 168 h or 3 x `t_half_eff` after the last dose, whichever is longer.
- Explicit `product.treatment_duration_h`, `study_design.dosing_duration_h`, or `study_design.duration_h` overrides these defaults.

For multiple-dose planning, always include a steady-state frequency matrix for:

- `daily_qd`: once daily, dosing interval 24 h
- `weekly_qw`: once weekly, dosing interval 168 h
- `weekly_biw`: twice weekly, dosing interval 84 h

The matrix must report 50%, 75%, 90%, 95%, and near-100% steady state. Near-100% means 99%, because true 100% is a theoretical asymptote.

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

For the main analysis, mark exactly one record as `primary_comparator: true` when a usable comparator exists. If there are competing plausible anchors, choose one main comparator according to the hierarchy above and put the alternatives into named sensitivity YAML files. Do not average conflicting public PK anchors, and do not mix single-dose and repeated-dose anchors in the same main comparator unless the user explicitly labels the run as exploratory sensitivity.

## Workflow

1. Create or update a YAML input file using `templates/minimal_input_template.yaml` for onboarding, or `templates/basic_input_template.yaml` for a fuller PK run.
2. Verify the companion tool is available:

```bash
python3 -m pktool.cli --help
```

3. Run from the project root:

```bash
python3 -m pktool.cli run-report --input <input_yaml>
```

Use `--no-fetch` when public evidence was already manually captured or when the run must avoid external network calls.

4. Review the generated run directory under `runs/`.
5. Read `simulation_summary.json`, `sampling_recommendation.csv`, `parameter_provenance.csv`, and `dose_extrapolation_sensitivity.csv` before summarizing.
6. For comparisons between two reports, read the run-specific input snapshot and summarize differences in primary comparator, absorption ranges, fast absorption status, depot/lag ranges, duration, `n_simulations`, `random_seed`, and `pktool` version before comparing exposure outputs.
7. Report the Markdown and Excel paths to the user and state the decision-gate status.

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

For long half-life products, `sampling_recommendation.csv` should include adaptive terminal points at 2 x and 3 x `t_half_eff` after the last dose when they are inside or relevant to the simulation window.

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
- Do not create manual fallback reports when `pktool` is unavailable. Installation failure is a blocker, not a reason to change the report format.

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
