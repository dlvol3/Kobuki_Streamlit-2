import json
from pathlib import Path
import unittest

from finance import (load_case, model, npv_only, solve_sales, solve_fixed_cost,
                     solve_price, solve_unit_variable_cost)


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

    def test_pricing_response_and_revenue_based_working_capital(self):
        r=model(self.case,1.045,-20000,price_coefficient=1.05,
                variable_cost_coefficient=.95,demand_elasticity=2)
        volume=1.045/1.05**2
        self.assertAlmostEqual(r.effective_sales_coefficient,volume)
        self.assertAlmostEqual(r.unit_price,5.355)
        self.assertAlmostEqual(r.unit_variable_cost,1.52)
        for y,q in zip(r.years[1:],self.case.base_units):
            self.assertAlmostEqual(y.units,q*volume)
            self.assertAlmostEqual(y.revenue,q*volume*5.355)
            self.assertAlmostEqual(y.variable_costs,q*volume*1.52)
            if y.year<self.case.life:
                self.assertAlmostEqual(y.nwc,.1*y.revenue)
        self.assertEqual(r.years[0].nwc,80000)
        self.assertEqual(r.years[-1].nwc,0)
        self.assertAlmostEqual(sum(y.change_nwc for y in r.years),0,places=7)

    def test_independent_cash_margin_identity_with_price_and_cost_changes(self):
        for p,v,e in [(.9,1.1,0),(1.05,.95,1),(1.1,1,2),(.8,0,3)]:
            with self.subTest(price=p,cost=v,elasticity=e):
                kwargs=dict(price_coefficient=p,variable_cost_coefficient=v,demand_elasticity=e)
                r=model(self.case,1.045,-20000,**kwargs)
                self.assertAlmostEqual(r.npv,npv_only(self.case,1.045,-20000,**kwargs),places=6)
                # Compute a year's cash generation without the model's EBIT/NOPAT bridge.
                y=r.years[1]
                cash=y.revenue-y.variable_costs-y.fixed_costs-y.tax-y.change_nwc
                self.assertAlmostEqual(y.fcf,cash,places=7)

    def test_more_elastic_demand_can_reverse_the_price_increase_decision(self):
        low=model(self.case,1.045,-20000,price_coefficient=1.05,demand_elasticity=1)
        high=model(self.case,1.045,-20000,price_coefficient=1.05,demand_elasticity=2)
        self.assertAlmostEqual(low.npv,13812.931688763492,places=6)
        self.assertAlmostEqual(high.npv,-111008.15835091891,places=6)
        self.assertGreater(low.npv,0)
        self.assertLess(high.npv,0)

    def test_extended_sales_and_fixed_cost_solvers_hold_all_other_drivers(self):
        kwargs=dict(price_coefficient=1.05,variable_cost_coefficient=.97,demand_elasticity=2)
        m=solve_sales(self.case,-20000,**kwargs)
        self.assertAlmostEqual(model(self.case,m,-20000,**kwargs).npv,0,places=6)
        d=solve_fixed_cost(self.case,1.045,**kwargs)
        self.assertAlmostEqual(model(self.case,1.045,d,**kwargs).npv,0,places=6)

    def test_price_solver_reports_every_root_including_second_nonmonotone_root(self):
        roots=solve_price(self.case,.99,-20000,demand_elasticity=2)
        self.assertEqual(len(roots),2)
        self.assertAlmostEqual(roots[0],.5031033024495492,places=9)
        self.assertAlmostEqual(roots[1],.8625907275304552,places=9)
        for p in roots:
            self.assertAlmostEqual(model(self.case,.99,-20000,price_coefficient=p,
                                         demand_elasticity=2).npv,0,places=6)
        middle=(roots[0]+roots[1])/2
        self.assertGreater(npv_only(self.case,.99,-20000,price_coefficient=middle,demand_elasticity=2),0)
        self.assertLess(npv_only(self.case,.99,-20000,price_coefficient=1,demand_elasticity=2),0)

    def test_price_solver_respects_bounds_and_no_root_case(self):
        self.assertEqual(solve_price(self.case,.99,-20000,demand_elasticity=2,lower=1,upper=1.5),())
        root=solve_price(self.case,1.045,-20000,demand_elasticity=1)[0]
        self.assertAlmostEqual(root,1.037403004792555,places=9)
        self.assertEqual(solve_price(self.case,0,-20000),())
        # A break-even at an endpoint is retained exactly once.
        endpoint=solve_price(self.case,1.045,-20000,demand_elasticity=1,lower=root,upper=1.5)
        self.assertEqual(len(endpoint),1)
        self.assertAlmostEqual(endpoint[0],root,places=9)

    def test_price_solver_recovers_tangent_at_stationary_point(self):
        constant=npv_only(self.case,0,-20000)
        a=npv_only(self.case,1.1,-20000,variable_cost_coefficient=0)-constant
        b=a-(npv_only(self.case,1.1,-20000)-constant)
        peak=2*b/a
        cost=solve_fixed_cost(self.case,1.1,price_coefficient=peak,demand_elasticity=2)
        roots=solve_price(self.case,1.1,cost,demand_elasticity=2)
        self.assertEqual(len(roots),1)
        self.assertAlmostEqual(roots[0],peak,places=9)
        self.assertAlmostEqual(model(self.case,1.1,cost,price_coefficient=roots[0],
                                     demand_elasticity=2).npv,0,places=6)

    def test_unit_variable_cost_ceiling_includes_price_volume_response(self):
        for m,p,e in [(1.045,1,0),(.99,1,0),(1.045,1.05,2)]:
            with self.subTest(m=m,p=p,e=e):
                cost=solve_unit_variable_cost(self.case,m,-20000,price_coefficient=p,demand_elasticity=e)
                kwargs=dict(price_coefficient=p,variable_cost_coefficient=cost/self.case.unit_variable_cost,
                            demand_elasticity=e)
                self.assertAlmostEqual(model(self.case,m,-20000,**kwargs).npv,0,places=6)
                kwargs['variable_cost_coefficient']+=.01
                self.assertLess(model(self.case,m,-20000,**kwargs).npv,0)
        self.assertIsNone(solve_unit_variable_cost(self.case,0,-20000))
        self.assertIsNone(solve_unit_variable_cost(self.case,.01,-20000))

    def test_invalid_pricing_cost_and_elasticity_inputs_are_rejected(self):
        for kwargs in [dict(price_coefficient=0),dict(price_coefficient=-1),
                       dict(price_coefficient=float('nan')),dict(variable_cost_coefficient=-.1),
                       dict(variable_cost_coefficient=float('inf')),dict(demand_elasticity=-1),
                       dict(demand_elasticity=float('inf'))]:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):model(self.case,**kwargs)
                with self.assertRaises(ValueError):npv_only(self.case,1,0,**kwargs)
        with self.assertRaises(ValueError):solve_price(self.case,1,0,lower=0)
        with self.assertRaises(ValueError):solve_price(self.case,1,0,lower=1.5,upper=.5)


if __name__=='__main__':unittest.main()

