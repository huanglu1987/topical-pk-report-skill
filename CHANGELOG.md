# Changelog

## Unreleased

- Added general new-project reproducibility rules to the Skill and README: lock the main-analysis comparator, absorption/depot/lag assumptions, fast-absorption rule, simulation duration, random seed, simulation count, evidence state, and tool version before comparing reports.
- Clarified that sensitivity analyses must be separate named scenarios and should not be merged into the main-analysis conclusion.
- Added template comments so teammate onboarding inputs distinguish minimal input from a decision-comparable locked analysis package.

## v0.1.1 - 2026-05-15

- Changed the default multiple-dose one-click duration logic from a 28-day run to a near-100% steady-state run when only dosing frequency is provided.
- Added locked dutasteride 2% 20 mg reproducible input YAML files for single-dose, daily-QD multiple-dose, and weekly-QW multiple-dose reports.
- Added reproducibility tests to protect key report-driving inputs: random seed, simulation count, reference PK anchors, absorption range, depot half-life range, and variability preset.
- Added `pktool_version` and `random_seed` to `simulation_summary.json` and the Markdown report summary.

## V1.1 - 2026-05-13

- Added `decision_gate` with `ok` / `warning` / `blocked_for_decision_use` states.
- Reworked multiple-dose metrics to use `Cmax_ss_per_cycle`, `AUC_tau_ss`, `Cmax_global`, `AUC_0_T_studyend`, and `AUC_post_last_dose_to_inf`.
- Replaced predose-relative steady-state timing with `t_half_eff` formula-based timing.
- Extended single-dose simulations for long half-life/depot products and added adaptive terminal sampling at 2 x / 3 x `t_half_eff`.
- Added multiple-dose frequency handling: `study_design.dosing_frequency` is required for minimal multiple-dose inputs, and reports include daily, weekly, and twice-weekly steady-state timing.
- Added variability presets, fast absorption V2 scoring, deprecated `early_apparent_volume_l_range` handling, calibration checks, and dose-extrapolation sensitivity output.
- Added purpose-specific sampling schedules for exploratory PK, MUsT/max-use PK, and BE/bridging.
- Added `parameter_provenance.csv`, `dose_extrapolation_sensitivity.csv`, Markdown gate banners, Excel decision gate sheet, and `decision_gate` JSON schema.
- Expanded `known_formulations` fields while keeping old YAML inputs compatible.
- Updated dutasteride validation inputs and documentation to clarify internal exploratory use only.

Breaking changes: none intended. Existing CSV/YAML inputs remain accepted; deprecated fields are retained as warnings rather than hard errors.
