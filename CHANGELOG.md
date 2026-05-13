# Changelog

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
