# Kobuki / Wake Up! sensitivity analysis

Streamlit + Apache ECharts · Group 2: Jorge Pablo Yue · Version 2026-10-19-v3

## Open locally

Double-click **Start_Kobuki.command**, then open <http://127.0.0.1:8501>.

For a fresh Python 3.12 environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Controls

- **Q1 baseline:** original sales path and EUR 240,000 annual fixed costs.
- **Q2 baseline:** 1.10 times Q1 unit sales; EUR 40,000 project savings plus EUR 20,000 additional corporate cost. Net annual fixed costs are EUR 220,000.
- **Can sales:** multiply every year's Q1 units by one coefficient. The display includes percentage and annual can volumes.
- **Fixed costs:** add or subtract the same EUR amount in each production year.
- **Find break-even sales / fixed costs:** hold the other input constant and solve NPV = 0.

The large decision banner, NPV, IRR and annual costs update together. WACC stays fixed at **0.102974**. Returns are displayed primarily as decimals.

The two charts share the selected sensitivity axis. Decision focus is the default; Full range provides wider context. Grey is the Q1 reference curve; the dashed curve holds the other input at its current value. An open dot fixes the actual Q1 result, while a labelled ring marks the selected scenario and a dotted connector shows their difference. Green and pink regions distinguish outcomes above and below the hurdle; the gold diamond is break-even. Change versus Q1 is shown above both charts. Each chart offers a PNG download. One **Cash flows** expander provides a compact annual table and the complete CSV.

## Workbook reconciliation

Inputs and reference outputs were extracted read-only from `Kobuki_Group_4.xlsx`, sheets `Question 1` and `Question 2`. The workbook is not changed or required at runtime.

| Metric | Q1 baseline | Q2 baseline |
|---|---:|---:|
| Sales coefficient vs Q1 | 1.000000 | 1.100000 |
| Annual fixed costs, EUR | 240,000 | 220,000 |
| WACC | 0.102974 | 0.102974 |
| NPV, EUR | -216,165.762346 | 91,902.595498 |
| IRR | 0.080720058733 | 0.112189728520 |
| Decision | Reject | Accept |

With Q1 costs held constant, sales break-even is **1.088089308660** times the Q1 forecast. With Q1 sales held constant, the fixed-cost change at break-even is **EUR -68,980.462375/year**.

The model preserves the workbook's annual timing and immediate group-level tax loss offsets. Initial NWC is EUR 80,000; closing NWC is 0.10 of current-year revenue in Years 1–6 and zero in Year 7. Terminal NWC recovery is counted once. Sales sensitivity assumes existing equipment capacity and no extra CAPEX. Every headline, chart and solver uses the same full-precision model; absolute NPV up to EUR 1 is labelled break-even.

## Files and validation

- `app.py`: page and scenario state.
- `finance.py`: cash flows, WACC, NPV, IRR and break-even solvers.
- `charts.py`: chart data and options.
- `controls.py`, `echarts_component.py`, `assets/`: vertical controls and local ECharts renderer.
- `data/`: extracted inputs, presets, reference outputs and Q1 cash flows.
- `.streamlit/config.toml`, `requirements.txt`: theme and runtime dependencies.
- `tests/`: workbook reconciliation and interaction checks.

```sh
python -m unittest discover -s tests -v
```

The extraction utility `tools/extract_workbook.py` requires `openpyxl` and the original workbook. Re-run validation after refreshing its data.

## Sharing

This folder is ready to use as a Streamlit app source. Include all source files, `assets/`, `data/`, `.streamlit/config.toml` and `requirements.txt`; exclude `.venv/`, caches, original workbooks and case PDFs. The local address works only on the computer running the app. A public URL is available only after a separate hosting deployment.

ECharts 5.6.0 is bundled locally, retaining its Apache License 2.0 notice. Source: <https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js>. Charts require no external CDN at runtime.
