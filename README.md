# Wake Up! · Group 2: Jorge, Pablo, Yue

## Main controls: can sales and annual fixed costs

- Can sales: coefficient times each corresponding Q1 annual forecast. 1.0 gives 160,000 / 220,000 / 250,000 cans; 1.1 gives the Q2 forecast. The vertical slider shows 50–200% and the exact box accepts decimals.
- Flat annual fixed-cost change relative to Q1's EUR 240,000/year. Q2 uses EUR -20,000, giving EUR 220,000/year.

Price stays EUR 5.10 in the main analysis. Q1 and Q2 buttons restore the original sales and cost assumptions. The other top shortcuts show no extra Q2 sales or 10% below Q1, both retaining Q2 annual fixed costs. The headline, NPV/IRR charts, can counts and downloadable cash flows respond to these two controls. Break-even buttons solve for can sales or annual fixed costs, holding the other control fixed.

Production cost stays EUR 1.60/can. Revenue, tax, working capital and free cash flow are recalculated. WACC remains 0.102974; Q1/Q2 NPVs remain -EUR 216,165.76 / +EUR 91,902.60.

## Figure 1: sales shortfall only

This panel is separate from the main sales/cost controls: price stays EUR 5.10 and annual fixed costs EUR 220,000. The same sales factor applies to each corresponding Q1 year (160,000 / 220,000 / 250,000 cans, then 250,000 through Year 7).

- 90% of Q1: 10% fewer cans than Q1; NPV -EUR 398,885.14.
- 100% of Q1: no additional Q2 sales, keeping Q1's growth between years; NPV -EUR 153,491.27.
- 110% of Q1: the full Q2 forecast; NPV +EUR 91,902.60.

Break-even is 106.2549% of each Q1 year: 6.2549% above Q1, or 3.4046% below Q2. Scenario buttons change only this panel. Market demand, a competing drink or fewer repeat purchases after promotion are possible reasons for a miss.

## Figure 2: price and the fixed-cost ceiling

The map always uses Q2's underlying sales plan and the same inverse price response. Green below the dashed line means positive NPV. Hollow circles show zero-NPV annual fixed-cost ceilings; A/B/C/D are worked examples. The A/B/C/D buttons update a separate Figure 2 result. They leave the main sales and fixed-cost controls and their cash flows unchanged.

- A: EUR 4.50/can and EUR 190,000 annual fixed costs; NPV +EUR 18,276.96, with EUR 5,832.34/year of cost headroom.
- B: Q2 baseline; NPV +EUR 91,902.60, with EUR 29,326.95/year of cost headroom.
- C: EUR 5.355/can and EUR 250,000 annual fixed costs; NPV +EUR 57,761.35, with EUR 18,432.17/year of cost headroom.
- D: EUR 4.50/can and EUR 220,000 annual fixed costs; NPV -EUR 75,734.77. Fixed costs would have to fall below EUR 195,832.34/year for positive NPV at that price.

Cost headroom is an annual amount; NPV is the present value of the whole project. At D, more cans exactly offset the lower price, leaving revenue unchanged, while total production spending rises. The discussion mentions a smaller discount, additional fixed savings, lower ingredient/packaging prices and less waste; no new savings are included in the calculations.

Price changes appear only in Figure 2, using the Q2 underlying sales path and the inverse relationship `cans = Q2 planned cans × 5.10 / price`. There is no elasticity-2 comparison, production-cost control or net-price control. All results appraise the full project before investment. Price examples assume no extra equipment.

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

Forty-three tests passed; local browser checks confirmed that the can-sales slider changes the main NPV at EUR5.10 and Figure 2 pricing examples leave the main analysis unchanged. Apache ECharts is bundled with its licence notices. Original case workbooks are not required at runtime.
