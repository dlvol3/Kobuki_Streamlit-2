import json
from pathlib import Path
import unittest

from finance import load_case, model, npv_only, solve_sales, solve_fixed_cost


class FinanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case=load_case()
        cls.reference=json.loads((Path(__file__).parents[1]/'data/workbook_reference.json').read_text())

    def test_matches_group4_all_eight_cashflows_and_present_values(self):
        result=model(self.case)
        for year,fcf,pv in zip(result.years,self.reference['cashflows'],self.reference['present_values']):
            self.assertAlmostEqual(year.fcf,fcf,places=6)
            self.assertAlmostEqual(year.pv,pv,places=6)
        self.assertAlmostEqual(result.npv,self.reference['npv'],places=6)
        self.assertAlmostEqual(result.irr,self.reference['irr'],places=10)
        self.assertAlmostEqual(result.wacc,self.reference['wacc'],places=12)

    def test_q2_preset_matches_all_workbook_cashflows_and_present_values(self):
        inputs=json.loads((Path(__file__).parents[1]/'data/case_inputs.json').read_text())
        preset=inputs['presets']['q2']
        self.assertEqual(preset['sales_coefficient'],1.1)
        self.assertEqual(preset['fixed_cost_change'],-20000)
        result=model(self.case,preset['sales_coefficient'],preset['fixed_cost_change'])
        reference=self.reference['q2']
        self.assertEqual(reference['sheet'],'Question 2')
        self.assertEqual(len(result.years),8)
        self.assertEqual(len(reference['cashflows']),8)
        self.assertEqual(len(reference['present_values']),8)
        for year,fcf,pv in zip(result.years,reference['cashflows'],reference['present_values']):
            with self.subTest(year=year.year):
                self.assertAlmostEqual(year.fcf,fcf,places=6)
                self.assertAlmostEqual(year.pv,pv,places=6)
        self.assertAlmostEqual(result.npv,reference['npv'],places=6)
        self.assertAlmostEqual(result.irr,reference['irr'],places=10)
        self.assertAlmostEqual(result.wacc,reference['wacc'],places=12)
        self.assertEqual(result.years[0].nwc,80000)
        self.assertTrue(all(year.fixed_costs==220000 for year in result.years[1:]))

    def test_cash_margin_identity_across_scenarios(self):
        for m in [.5,.9,1,1.2,2]:
            for d in [-240000,-40000,0,150000,600000]:
                with self.subTest(m=m,d=d):
                    self.assertAlmostEqual(model(self.case,m,d).npv,npv_only(self.case,m,d),places=6)

    def test_flat_cost_change_is_annual_not_compounded(self):
        r=model(self.case,1,15000)
        self.assertTrue(all(y.fixed_costs==255000 for y in r.years[1:]))

    def test_sales_path_and_nwc_scale_together(self):
        r=model(self.case,1.1)
        self.assertAlmostEqual(r.years[1].units,176000)
        self.assertAlmostEqual(r.years[2].units,242000)
        self.assertAlmostEqual(r.years[3].units,275000)
        self.assertAlmostEqual(r.years[1].nwc,89760)
        self.assertEqual(r.years[0].nwc,80000)
        # Q1 at +10% volume is not Q2: no cost synergies are imported.
        self.assertAlmostEqual(r.npv,29228.11,places=2)

    def test_nwc_is_recovered_once(self):
        for m in [.5,1,1.7]:
            r=model(self.case,m)
            self.assertAlmostEqual(sum(y.change_nwc for y in r.years),0,places=7)
            self.assertEqual(r.years[-1].nwc,0)
            self.assertAlmostEqual(-r.years[-1].change_nwc,r.years[-2].nwc)

    def test_initial_outlay_not_discounted(self):
        r=model(self.case)
        self.assertEqual(r.years[0].fcf,-2670000)
        self.assertEqual(r.years[0].pv,r.years[0].fcf)

    def test_loss_tax_offset_and_salvage(self):
        r=model(self.case)
        self.assertAlmostEqual(r.years[1].tax,-7000)
        self.assertEqual(r.years[-1].after_tax_salvage,210000)
        self.assertAlmostEqual(r.years[-1].fcf,869250)

    def test_sales_solver_holds_cost_and_clears_npv_and_irr_hurdle(self):
        for d in [-100000,0,100000,400000]:
            root=solve_sales(self.case,d)
            r=model(self.case,root,d)
            self.assertEqual(r.fixed_cost_change,d)
            self.assertAlmostEqual(r.npv,0,places=6)
            self.assertAlmostEqual(r.irr,self.case.wacc,places=9)

    def test_cost_solver_holds_sales_and_clears_npv_and_irr_hurdle(self):
        for m in [.9,1,1.2,1.8]:
            root=solve_fixed_cost(self.case,m)
            r=model(self.case,m,root)
            self.assertEqual(r.sales_coefficient,m)
            self.assertAlmostEqual(r.npv,0,places=6)
            self.assertAlmostEqual(r.irr,self.case.wacc,places=9)

    def test_infeasible_negative_total_cost_is_not_returned(self):
        self.assertIsNone(solve_fixed_cost(self.case,.5))
        with self.assertRaises(ValueError):model(self.case,1,-240001)

    def test_wacc_never_changes_with_controls(self):
        self.assertEqual(model(self.case,.8,-20000).wacc,model(self.case,1.8,120000).wacc)

    def test_cost_sensitivity_matches_after_tax_annuity(self):
        pv_saving=20000*(1-self.case.tax_rate)*sum((1+self.case.wacc)**-t for t in range(1,8))
        self.assertAlmostEqual(model(self.case,1,-20000).npv-model(self.case).npv,pv_saving,places=6)


if __name__=='__main__':unittest.main()

