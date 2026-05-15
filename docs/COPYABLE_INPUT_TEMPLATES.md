# Copyable Input Templates

Use the locked YAML files below when you need to reproduce the dutasteride
2% topical solution 20 mg reports. Open the YAML file on GitHub and copy the
whole file content, or run it directly from this repository.

Do not recreate these inputs from natural language. Small changes to reference
PK anchors, absorption ranges, depot half-life ranges, variability, random seed,
or simulation count can materially change P95 exposure.

| Scenario | Copyable YAML | Run command |
|---|---|---|
| Single dose, 20 mg | `data/reproducible_inputs/dutasteride_2pct_20mg_single_locked.yaml` | `python3 -m pktool.cli run-report --input data/reproducible_inputs/dutasteride_2pct_20mg_single_locked.yaml --no-fetch` |
| Multiple dose, daily QD, steady-state window | `data/reproducible_inputs/dutasteride_2pct_20mg_multiple_daily_qd_steady_state_locked.yaml` | `python3 -m pktool.cli run-report --input data/reproducible_inputs/dutasteride_2pct_20mg_multiple_daily_qd_steady_state_locked.yaml --no-fetch` |
| Multiple dose, weekly QW, steady-state window | `data/reproducible_inputs/dutasteride_2pct_20mg_multiple_weekly_qw_steady_state_locked.yaml` | `python3 -m pktool.cli run-report --input data/reproducible_inputs/dutasteride_2pct_20mg_multiple_weekly_qw_steady_state_locked.yaml --no-fetch` |

## Locked Fields

These locked inputs fix the fields that caused non-reproducible reports:

- `study_design.n_simulations: 3000`
- `study_design.random_seed: 20260515`
- oral single-dose reference for the single-dose run: `Cmax 3.067 ng/mL`, `AUC 48.048 ng*h/mL`
- topical absorption range: `[0.000005, 0.001]`
- depot half-life range: `[2, 72] h`
- variability preset: `medium`
- no 2% topical patent anchor is included

The multiple-dose locked files also explicitly set the steady-state simulation
window used for the reference reports:

- `product.treatment_duration_h: 6048`
- `study_design.dosing_duration_h: 6048`
- `study_design.duration_h: 8568`

For new exploratory work, copy one locked YAML to a new filename first, then
edit it intentionally. For reproducibility checks, run the locked YAML without
changing any field.
