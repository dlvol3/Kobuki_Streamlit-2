from pathlib import Path
import unittest
from unittest.mock import patch
import streamlit as st
from streamlit.testing.v1 import AppTest
from finance import load_case,model
APP=Path(__file__).parents[1]/'app.py'

class AppTests(unittest.TestCase):
    def start(self):
        at=AppTest.from_file(str(APP),default_timeout=30).run()
        self.assertEqual(len(at.exception),0)
        return at

    def test_q2_and_q1_shortcuts_reset_all_commercial_inputs(self):
        at=self.start()
        at.number_input(key='price_per_can').set_value(5.35).run()
        at.number_input(key='demand_elasticity').set_value(2.0).run()
        at.button(key='reset_q2').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(at.session_state['sales_coefficient'],1.1)
        self.assertEqual(at.session_state['fixed_cost_change'],-20000)
        self.assertEqual(at.session_state['price_per_can'],5.1)
        self.assertEqual(at.session_state['demand_elasticity'],0)
        self.assertAlmostEqual(at.dataframe[-1].value['FCF'].iloc[-1],951875,places=6)
        at.segmented_control(key='axis').set_value('Fixed-cost change').run()
        self.assertEqual(at.session_state['sales_coefficient'],1.1)
        at.button(key='reset_q1').click().run()
        self.assertAlmostEqual(at.dataframe[-1].value['FCF'].iloc[-1],869250,places=6)
        self.assertEqual(at.session_state['fixed_cost_change'],0)
        self.assertEqual(len(at.expander),1)

    def test_q2_shortcut_rejects_a_delayed_slider_event(self):
        at=self.start()
        old_revision=at.session_state['scenario_revision']
        def delayed(**kwargs):
            st.session_state['drivers']={'scenario':{'sales':.8,'cost':120000,'revision':old_revision}}
            kwargs['on_scenario_change']()
        with patch('controls.vertical_drivers',side_effect=delayed):
            at.button(key='reset_q2').click().run()
        self.assertEqual(at.session_state['sales_coefficient'],1.1)
        self.assertEqual(at.session_state['fixed_cost_change'],-20000)
        self.assertEqual(len(at.exception),0)

    def test_demand_and_cost_solvers_hold_commercial_inputs(self):
        at=self.start()
        at.number_input(key='price_per_can').set_value(5.2).run()
        at.number_input(key='demand_elasticity').set_value(1.0).run()
        at.button(key='solve_sales').click().run()
        kwargs=dict(price_coefficient=5.2/5.1,demand_elasticity=1)
        self.assertAlmostEqual(model(load_case(),at.session_state['sales_coefficient'],0,**kwargs).npv,0,places=5)
        self.assertEqual(at.session_state['price_per_can'],5.2)
        at.button(key='reset_q1').click().run()
        at.button(key='solve_costs').click().run()
        self.assertAlmostEqual(model(load_case(),1,at.session_state['fixed_cost_change']).npv,0,places=5)

    def test_price_stress_changes_actual_units_and_cashflows(self):
        at=self.start()
        at.button(key='price_stress').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertAlmostEqual(at.session_state['sales_coefficient'],1.045)
        self.assertAlmostEqual(at.session_state['price_per_can'],5.355)
        self.assertEqual(at.session_state['demand_elasticity'],2)
        cf=at.dataframe[-1].value
        self.assertAlmostEqual(cf['Cans sold'].iloc[1],160000*1.045/(1.05**2),places=6)
        reference=model(load_case(),1.045,-20000,price_coefficient=1.05,demand_elasticity=2)
        self.assertAlmostEqual(cf['FCF'].iloc[-1],reference.years[-1].fcf,places=6)

    def test_price_and_unit_cost_recovery_solves_zero_npv(self):
        at=self.start()
        at.button(key='downside').click().run()
        at.button(key='solve_price').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertAlmostEqual(model(load_case(),1.045,-20000,price_coefficient=at.session_state['price_per_can']/5.1).npv,0,places=5)
        at.button(key='downside').click().run()
        at.button(key='solve_unit_cost').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertAlmostEqual(model(load_case(),1.045,-20000,variable_cost_coefficient=at.session_state['variable_cost_per_can']/1.6).npv,0,places=5)

    def test_execution_budget_is_included_in_cashflows(self):
        at=self.start()
        at.button(key='execution_budget').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(at.session_state['fixed_cost_change'],-10000)
        self.assertEqual(at.session_state['variable_cost_per_can'],1.55)
        actual=at.dataframe[-1].value
        expected=model(load_case(),1.045,-10000,price_coefficient=1.02,variable_cost_coefficient=1.55/1.6,demand_elasticity=1)
        self.assertLess(expected.npv,0)
        self.assertAlmostEqual(actual['FCF'].iloc[1],expected.years[1].fcf,places=6)

    def test_cleared_price_input_recovers_to_baseline(self):
        at=self.start()
        at.number_input(key='price_per_can').set_value(None).run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(at.session_state['price_per_can'],5.1)

    def test_infeasible_cost_solver_preserves_demand(self):
        at=self.start()
        at.session_state['sales_coefficient']=.5
        at.run()
        at.button(key='solve_costs').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(at.session_state['sales_coefficient'],.5)
        self.assertTrue(any('zero annual fixed costs' in w.value for w in at.warning))

if __name__=='__main__':unittest.main()
