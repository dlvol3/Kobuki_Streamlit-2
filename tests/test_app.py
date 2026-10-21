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

    def test_baseline_shortcuts_restore_price_cost_and_exact_cashflows(self):
        at=self.start()
        self.assertEqual(at.session_state['baseline_id'],'q1')
        self.assertAlmostEqual(next(x.value for x in at.dataframe if 'FCF' in x.value.columns)['FCF'].iloc[-1],869250,places=6)
        at.button(key='reset_q2').click().run()
        self.assertEqual(at.session_state['baseline_id'],'q2')
        self.assertEqual(at.session_state['price_per_can'],5.1)
        self.assertEqual(at.session_state['fixed_cost_change'],-20000)
        self.assertAlmostEqual(next(x.value for x in at.dataframe if 'FCF' in x.value.columns)['FCF'].iloc[-1],951875,places=6)
        at.segmented_control(key='axis').set_value('Fixed-cost change').run()
        self.assertEqual(at.session_state['baseline_id'],'q2')
        at.button(key='reset_q1').click().run()
        self.assertEqual(at.session_state['fixed_cost_change'],0)
        self.assertEqual(len(at.exception),0)

    def test_only_two_driver_values_are_sent_to_control_component(self):
        at=self.start()
        with patch('controls.vertical_drivers') as driver:
            at.run()
        data=driver.call_args.kwargs['data']
        self.assertIn('price',data)
        self.assertIn('cost',data)
        self.assertNotIn('sales',data)
        self.assertNotIn('variable_cost',data)
        self.assertEqual(len(at.number_input),0)
        self.assertEqual(len(at.expander),1)
        button_keys={b.key for b in at.button}
        self.assertNotIn('solve_sales',button_keys)
        self.assertNotIn('solve_unit_cost',button_keys)
        self.assertNotIn('execution_budget',button_keys)

    def test_delayed_driver_event_cannot_override_q2_shortcut(self):
        at=self.start();old=at.session_state['scenario_revision']
        def delayed(**kwargs):
            st.session_state['drivers']={'scenario':{'price':6.1,'cost':120000,'revision':old}}
            kwargs['on_scenario_change']()
        with patch('controls.vertical_drivers',side_effect=delayed):
            at.button(key='reset_q2').click().run()
        self.assertEqual(at.session_state['price_per_can'],5.1)
        self.assertEqual(at.session_state['fixed_cost_change'],-20000)

    def test_price_increase_automatically_reduces_units(self):
        at=self.start()
        at.button(key='price_example').click().run()
        self.assertEqual(at.session_state['baseline_id'],'q2')
        expected=model(load_case(),1.1,-20000,price_coefficient=1.05,demand_elasticity=1)
        cf=next(x.value for x in at.dataframe if 'FCF' in x.value.columns)
        self.assertAlmostEqual(cf['Cans sold'].iloc[1],176000/1.05,places=6)
        self.assertAlmostEqual(cf['FCF'].iloc[-1],expected.years[-1].fcf,places=6)
        self.assertEqual(len(at.exception),0)

    def test_joint_example_includes_additional_annual_fixed_cost(self):
        at=self.start()
        at.button(key='joint_example').click().run()
        self.assertEqual(at.session_state['fixed_cost_change'],10000)
        expected=model(load_case(),1.1,10000,price_coefficient=1.05,demand_elasticity=1)
        self.assertAlmostEqual(next(x.value for x in at.dataframe if 'FCF' in x.value.columns)['FCF'].iloc[1],expected.years[1].fcf,places=6)

    def test_price_and_fixed_cost_solvers_reach_zero_npv(self):
        at=self.start();at.button(key='solve_price').click().run()
        p=at.session_state['price_per_can']
        self.assertAlmostEqual(model(load_case(),1,0,price_coefficient=p/5.1,demand_elasticity=1).npv,0,places=5)
        at.button(key='reset_q2').click().run()
        at.button(key='solve_costs').click().run()
        self.assertEqual(at.session_state['price_per_can'],5.1)
        self.assertAlmostEqual(model(load_case(),1.1,at.session_state['fixed_cost_change'],demand_elasticity=1).npv,0,places=5)
        self.assertEqual(len(at.exception),0)

    def test_app_refreshes_an_old_cached_chart_module(self):
        import charts
        saved=charts.SCOPE_VERSION
        charts.SCOPE_VERSION=None
        del charts.operating_options
        try:
            at=self.start()
            self.assertEqual(charts.SCOPE_VERSION,'sales-price-fixed-v3')
            self.assertTrue(callable(charts.operating_options))
            self.assertEqual(len(at.exception),0)
        finally:
            if not hasattr(charts,'operating_options'):
                import importlib
                importlib.reload(charts)
            charts.SCOPE_VERSION=saved

    def test_app_refreshes_an_old_cached_controls_module(self):
        import controls
        controls.SCOPE_VERSION=None
        at=self.start()
        self.assertEqual(controls.SCOPE_VERSION,'price-fixed-v2')
        self.assertEqual(len(at.exception),0)

    def test_sales_only_scenarios_do_not_change_price_cost_controls(self):
        at=self.start()
        at.button(key='price_example').click().run()
        price,cost=at.session_state['price_per_can'],at.session_state['fixed_cost_change']
        for key,m in [('sales_below_q1',.9),('sales_no_q2',1.),('sales_q2',1.1)]:
            at.button(key=key).click().run()
            self.assertEqual(at.session_state['sales_test'],m)
            self.assertEqual(at.session_state['price_per_can'],price)
            self.assertEqual(at.session_state['fixed_cost_change'],cost)
            expected=model(load_case(),m,-20000)
            self.assertTrue(any(f'{abs(expected.npv):,.0f}' in x.value for x in at.info))
        self.assertEqual(len(at.exception),0)

    def test_map_shortcuts_include_negative_and_positive_price_examples(self):
        at=self.start()
        for key,p,d in [('map_low_safe',4.5,-50000),('map_low_loss',4.5,-20000),('map_high_safe',5.355,10000),('map_q2',5.1,-20000)]:
            at.button(key=key).click().run()
            self.assertEqual(at.session_state['baseline_id'],'q2')
            self.assertAlmostEqual(at.session_state['price_per_can'],p)
            self.assertEqual(at.session_state['fixed_cost_change'],d)
            expected=model(load_case(),1.1,d,price_coefficient=p/5.1,demand_elasticity=1)
            cf=next(x.value for x in at.dataframe if 'FCF' in x.value.columns)
            self.assertAlmostEqual(cf['FCF'].iloc[-1],expected.years[-1].fcf,places=6)
        self.assertEqual(len(at.exception),0)

    def test_stale_removed_inputs_cannot_change_simplified_model(self):
        at=self.start()
        at.session_state['variable_cost_per_can']=0
        at.session_state['demand_elasticity']=5
        at.session_state['sales_coefficient']=2
        at.run()
        self.assertAlmostEqual(next(x.value for x in at.dataframe if 'FCF' in x.value.columns)['FCF'].iloc[-1],869250,places=6)

if __name__=='__main__':unittest.main()
