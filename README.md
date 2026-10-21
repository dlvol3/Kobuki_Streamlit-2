# Wake Up! · Group 2: Jorge, Pablo, Yue

## Price and annual fixed-cost controls

- Price per can: EUR 4.08–6.63; original price EUR 5.10.
- Flat annual fixed-cost change relative to Q1's EUR 240,000/year. Q2 uses EUR -20,000, giving EUR 220,000/year.

Q1 and Q2 buttons restore the original case plans. The headline, cash flows and NPV/IRR charts use those two controls. Price changes use one assumed response only:

`cans = selected Q1/Q2 plan cans × 5.10 / price`

A 1% price rise reduces cans by about 1%. Production cost stays at EUR 1.60/can. Revenue, tax, working capital and free cash flow are recalculated. WACC remains 0.102974; original Q1/Q2 NPVs remain -EUR 216,165.76 / +EUR 91,902.60.

## Figure 1: sales shortfall only

This panel is separate from the price/cost controls: price stays EUR 5.10 and annual fixed costs EUR 220,000. The same sales factor applies to each corresponding Q1 year (160,000 / 220,000 / 250,000 cans, then 250,000 through Year 7).

- 90% of Q1: 10% fewer cans than Q1; NPV -EUR 398,885.14.
- 100% of Q1: no additional Q2 sales, keeping Q1's growth between years; NPV -EUR 153,491.27.
- 110% of Q1: the full Q2 forecast; NPV +EUR 91,902.60.

Break-even is 106.2549% of each Q1 year: 6.2549% above Q1, or 3.4046% below Q2. Scenario buttons change only this panel. Market demand, a competing drink or fewer repeat purchases after promotion are possible reasons for a miss.

## Figure 2: price and the fixed-cost ceiling

The map always uses Q2's underlying sales plan and the same inverse price response. Green below the dashed line means positive NPV. Hollow circles show zero-NPV annual fixed-cost ceilings; A/B/C/D are worked examples. The current marker appears only when Q2 is selected in the main controls.

- A: EUR 4.50/can and EUR 190,000 annual fixed costs; NPV +EUR 18,276.96, with EUR 5,832.34/year of cost headroom.
- B: Q2 baseline; NPV +EUR 91,902.60, with EUR 29,326.95/year of cost headroom.
- C: EUR 5.355/can and EUR 250,000 annual fixed costs; NPV +EUR 57,761.35, with EUR 18,432.17/year of cost headroom.
- D: EUR 4.50/can and EUR 220,000 annual fixed costs; NPV -EUR 75,734.77. Fixed costs would have to fall below EUR 195,832.34/year for positive NPV at that price.

Cost headroom is an annual amount; NPV is the present value of the whole project. At D, more cans exactly offset the lower price, leaving revenue unchanged, while total production spending rises. The discussion mentions a smaller discount, additional fixed savings, lower ingredient/packaging prices and less waste; no new savings are included in the calculations.

There is no elasticity-2 comparison, independent sales slider, production-cost control or net-price control. Two break-even buttons find a price or annual fixed-cost ceiling while holding the other control fixed. All results appraise the full project before investment. Price examples assume no extra equipment.

## Run locally

Double-click `Start_Kobuki.command`, or use a Python 3.12 environment:

```sh
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Update the existing Streamlit app

Review the changed files in VS Code, commit and push the existing main branch. If the cloud app retains old imports, use Manage app > Reboot app. No commit or push has been performed automatically.

## Check

```sh
python -m unittest discover -s tests -q
```

Forty-four tests passed; local browser checks covered the sales-only buttons and a negative-NPV map example. Apache ECharts is bundled with its licence notices. Original case workbooks are not required at runtime.
