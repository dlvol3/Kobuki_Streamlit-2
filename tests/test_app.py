from pathlib import Path
import unittest
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest
from finance import load_case,model

APP=Path(__file__).parents[1]/'app.py'


class AppTests(unittest.TestCase):
    def test_q2_shortcut_persists_on_axis_change_and_q1_reset_restores_baseline(self):
        at=AppTest.from_file(str(APP),default_timeout=30).run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(len(at.expander),1)
        self.assertEqual(at.expander[0].label,'Cash flows')
        initial_revision=at.session_state['scenario_revision']
        at.button(key='reset_q2').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(at.session_state['sales_coefficient'],1.1)
        self.assertEqual(at.session_state['fixed_cost_change'],-20000)
        self.assertEqual(at.session_state['scenario_revision'],initial_revision+1)
        cashflows=at.dataframe[0].value
        self.assertEqual(len(cashflows),8)
        self.assertAlmostEqual(cashflows['FCF'].iloc[-1],951875,places=6)
        at.segmented_control(key='axis').set_value('Fixed-cost change').run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(at.session_state['sales_coefficient'],1.1)
        self.assertEqual(at.session_state['fixed_cost_change'],-20000)
        self.assertEqual(at.session_state['scenario_revision'],initial_revision+1)
        at.button(key='reset_q1').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(at.session_state['sales_coefficient'],1)
        self.assertEqual(at.session_state['fixed_cost_change'],0)
        self.assertEqual(at.session_state['scenario_revision'],initial_revision+2)
        self.assertAlmostEqual(at.dataframe[0].value['FCF'].iloc[-1],869250,places=6)
        self.assertEqual(len(at.expander),1)
        self.assertEqual(at.expander[0].label,'Cash flows')

    def test_q2_shortcut_rejects_a_delayed_slider_event(self):
        at=AppTest.from_file(str(APP),default_timeout=30).run()
        old_revision=at.session_state['scenario_revision']

        def delayed_driver_event(**kwargs):
            st.session_state['drivers']={'scenario':{
                'sales':.8,'cost':120000,'revision':old_revision,
            }}
            kwargs['on_scenario_change']()

        with patch('controls.vertical_drivers',side_effect=delayed_driver_event) as drivers:
            at.button(key='reset_q2').click().run()
        drivers.assert_called_once()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(at.session_state['scenario_revision'],old_revision+1)
        self.assertEqual(at.session_state['sales_coefficient'],1.1)
        self.assertEqual(at.session_state['fixed_cost_change'],-20000)

    def test_baseline_renders_and_both_shortcuts_hold_other_input(self):
        at=AppTest.from_file(str(APP),default_timeout=30).run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(at.session_state['sales_coefficient'],1)
        at.button(key='solve_sales').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(at.session_state['fixed_cost_change'],0)
        self.assertAlmostEqual(model(load_case(),at.session_state['sales_coefficient'],0).npv,0,places=5)
        at.button(key='reset_q1').click().run()
        at.button(key='solve_costs').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(at.session_state['sales_coefficient'],1)
        self.assertAlmostEqual(model(load_case(),1,at.session_state['fixed_cost_change']).npv,0,places=5)
        at.button(key='reset_q1').click().run()
        self.assertEqual(at.session_state['fixed_cost_change'],0)
        self.assertEqual(at.session_state['sales_coefficient'],1)

    def test_cost_axis_and_infeasible_solver_state(self):
        at=AppTest.from_file(str(APP),default_timeout=30).run()
        at.segmented_control(key='axis').set_value('Fixed-cost change').run()
        self.assertEqual(len(at.exception),0)
        at.session_state['sales_coefficient']=.5
        at.run()
        at.button(key='solve_costs').click().run()
        self.assertEqual(len(at.exception),0)
        self.assertEqual(at.session_state['sales_coefficient'],.5)
        self.assertTrue(any('zero annual fixed costs' in w.value for w in at.warning))


if __name__=='__main__':unittest.main()

