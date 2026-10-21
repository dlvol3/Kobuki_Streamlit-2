from pathlib import Path
import unittest
from unittest.mock import patch
import streamlit as st
from streamlit.testing.v1 import AppTest
from finance import load_case, model
APP=Path(__file__).parents[1]/'app.py'

class AppTests(unittest.TestCase):
    def start(self):
        at=AppTest.from_file(str(APP),default_timeout=30).run()
        self.assertEqual(len(at.exception),0)
        return at

    def cashflows(self,at):
        return next(x.value for x in at.dataframe if 'FCF' in x.value.columns)

    def test_baseline_shortcuts_restore_sales_costs_and_cashflows(self):
        at=self.start()
        self.assertEqual(at.session_state['sales_multiplier'],1.)
        self.assertAlmostEqual(self.cashflows(at)['FCF'].iloc[-1],869250,places=6)
        at.button(key='reset_q2').click().run()
        self.assertEqual(at.session_state['sales_multiplier'],1.1)
        self.assertEqual(at.session_state['fixed_cost_change'],-20000)
        self.assertAlmostEqual(self.cashflows(at)['FCF'].iloc[-1],951875,places=6)
        at.segmented_control(key='axis').set_value('Fixed-cost change').run()
        self.assertEqual(at.session_state['sales_multiplier'],1.1)
        at.button(key='reset_q1').click().run()
        self.assertEqual(at.session_state['sales_multiplier'],1.)
        self.assertEqual(at.session_state['fixed_cost_change'],0)

    def test_main_component_has_sales_and_cost_not_price(self):
        at=self.start()
        with patch('controls.vertical_drivers') as driver:at.run()
        data=driver.call_args.kwargs['data']
        self.assertIn('sales',data)
        self.assertIn('cost',data)
        self.assertNotIn('price',data)
        self.assertNotIn('variable_cost',data)
        self.assertEqual(len(at.expander),1)
        keys={b.key for b in at.button}
        self.assertIn('solve_sales',keys)
        self.assertNotIn('solve_price',keys)

    def test_sales_driver_changes_each_year_without_changing_price(self):
        at=self.start()
        def move_slider(**kwargs):
            revision=kwargs['data']['revision']
            st.session_state['drivers']={'scenario':{'sales':1.2,'cost':-20000,'revision':revision}}
            kwargs['on_scenario_change']()
        with patch('controls.vertical_drivers',side_effect=move_slider):at.run()
        at.run()
        self.assertAlmostEqual(self.cashflows(at)['Cans sold'].iloc[1],192000)
        self.assertAlmostEqual(self.cashflows(at)['Revenue'].iloc[1],192000*5.1)
        self.assertAlmostEqual(self.cashflows(at)['FCF'].iloc[-1],model(load_case(),1.2,-20000).years[-1].fcf)

    def test_delayed_driver_event_cannot_override_q2_shortcut(self):
        at=self.start();old=at.session_state['scenario_revision']
        def delayed(**kwargs):
            st.session_state['drivers']={'scenario':{'sales':1.7,'cost':120000,'revision':old}}
            kwargs['on_scenario_change']()
        with patch('controls.vertical_drivers',side_effect=delayed):at.button(key='reset_q2').click().run()
        self.assertEqual(at.session_state['sales_multiplier'],1.1)
        self.assertEqual(at.session_state['fixed_cost_change'],-20000)

    def test_downside_shortcuts_keep_q2_costs_and_q1_price(self):
        at=self.start()
        for key,m in [('no_extra_sales',1.),('sales_downside',.9)]:
            at.button(key=key).click().run()
            self.assertEqual(at.session_state['sales_multiplier'],m)
            self.assertEqual(at.session_state['fixed_cost_change'],-20000)
            cf=self.cashflows(at)
            self.assertAlmostEqual(cf['Revenue'].iloc[1],160000*m*5.1)
            self.assertAlmostEqual(cf['FCF'].iloc[-1],model(load_case(),m,-20000).years[-1].fcf)

    def test_sales_and_cost_solvers_reach_zero_npv(self):
        at=self.start();at.button(key='solve_sales').click().run()
        self.assertAlmostEqual(model(load_case(),at.session_state['sales_multiplier'],0).npv,0,places=5)
        at.button(key='reset_q2').click().run();at.button(key='solve_costs').click().run()
        self.assertEqual(at.session_state['sales_multiplier'],1.1)
        self.assertAlmostEqual(model(load_case(),1.1,at.session_state['fixed_cost_change']).npv,0,places=5)

    def test_figure2_examples_cannot_change_main_sales_or_costs(self):
        at=self.start();at.button(key='sales_downside').click().run()
        before=self.cashflows(at).copy()
        for key,p,cost in [('map_low_safe',4.5,190000),('map_low_loss',4.5,220000),('map_high_safe',5.355,250000),('map_q2',5.1,220000)]:
            at.button(key=key).click().run()
            self.assertEqual(at.session_state['pricing_price'],p)
            self.assertEqual(at.session_state['pricing_fixed_cost'],cost)
            self.assertEqual(at.session_state['sales_multiplier'],.9)
            self.assertEqual(at.session_state['fixed_cost_change'],-20000)
            self.assertTrue(before.equals(self.cashflows(at)))
        self.assertEqual(len(at.exception),0)

    def test_fixed_sales_panel_is_independent_of_main_controls(self):
        at=self.start();at.button(key='sales_downside').click().run()
        for key,m in [('sales_below_q1',.9),('sales_no_q2',1.),('sales_q2',1.1)]:
            at.button(key=key).click().run()
            self.assertEqual(at.session_state['sales_test'],m)
            self.assertEqual(at.session_state['sales_multiplier'],.9)
            self.assertEqual(at.session_state['fixed_cost_change'],-20000)
            self.assertTrue(any(f'{abs(model(load_case(),m,-20000).npv):,.0f}' in x.value for x in at.info))

    def test_old_price_state_cannot_affect_main_cashflows(self):
        at=self.start()
        at.session_state['price_per_can']=6.5
        at.session_state['demand_elasticity']=5
        at.session_state['variable_cost_per_can']=0
        at.run()
        self.assertAlmostEqual(self.cashflows(at)['Revenue'].iloc[1],160000*5.1)
        self.assertAlmostEqual(self.cashflows(at)['FCF'].iloc[-1],869250)

    def test_cached_modules_are_refreshed_after_scope_change(self):
        import charts,controls
        charts.SCOPE_VERSION=None;controls.SCOPE_VERSION=None
        at=self.start()
        self.assertEqual(charts.SCOPE_VERSION,'sales-fixed-v4')
        self.assertEqual(controls.SCOPE_VERSION,'sales-fixed-v4')
        self.assertEqual(len(at.exception),0)

if __name__=='__main__':unittest.main()
