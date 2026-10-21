"""Financial and interaction contracts for the chart redesign."""
import unittest

from charts import options, sensitivity, pricing_options, decision_frontier_options
from finance import load_case, model


class ChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case = load_case()
        cls.baseline = model(cls.case)

    def chart(self, active, axis, metric, full_range=False):
        rows, root = sensitivity(self.case, active, axis, full_range=full_range)
        chart = options(self.case, active, rows, root, axis, metric)
        series = {item['id']: item for item in chart['series']}
        return rows, root, chart, series

    def point(self, datum):
        return datum.get('value') if isinstance(datum, dict) else datum

    def assert_point(self, datum, x, y):
        point = self.point(datum)
        self.assertAlmostEqual(point[0], x, places=10)
        self.assertAlmostEqual(point[1], y, places=8)

    def test_q1_and_q2_points_match_the_financial_results_on_both_axes(self):
        for sales, cost in [(1, 0), (1.1, -20000)]:
            active = model(self.case, sales, cost)
            for axis in ['Sales coefficient', 'Fixed-cost change']:
                for metric in ['NPV', 'IRR']:
                    with self.subTest(sales=sales, cost=cost, axis=axis, metric=metric):
                        _, _, _, series = self.chart(active, axis, metric)
                        base_x = 1 if axis == 'Sales coefficient' else 0
                        current_x = sales if axis == 'Sales coefficient' else cost / 1000
                        base_y = self.baseline.npv / 1000 if metric == 'NPV' else self.baseline.irr
                        current_y = active.npv / 1000 if metric == 'NPV' else active.irr
                        self.assertEqual(len(series['q1_point']['data']), 1)
                        self.assertEqual(len(series['current_point']['data']), 1)
                        self.assert_point(series['q1_point']['data'][0], base_x, base_y)
                        self.assert_point(series['current_point']['data'][0], current_x, current_y)

    def test_npv_zero_and_wacc_hurdles_remain_fixed_across_scenarios(self):
        for sales, cost in [(1, 0), (1.1, -20000), (2, 600000), (0, 600000)]:
            active = model(self.case, sales, cost)
            for axis in ['Sales coefficient', 'Fixed-cost change']:
                for metric in ['NPV', 'IRR']:
                    with self.subTest(sales=sales, cost=cost, axis=axis, metric=metric):
                        _, root, _, series = self.chart(active, axis, metric)
                        target = 0 if metric == 'NPV' else self.case.wacc
                        horizontal = [line['yAxis'] for line in series['scenario_curve']['markLine']['data']
                                      if isinstance(line, dict) and 'yAxis' in line]
                        self.assertTrue(any(abs(value - target) < 1e-12 for value in horizontal))
                        if root is not None:
                            factor = 1 if axis == 'Sales coefficient' else 1000
                            self.assert_point(series['break_even']['data'][0], root / factor, target)
                        else:
                            self.assertNotIn('break_even', series)

    def test_focus_and_full_ranges_include_presets_current_and_feasible_root(self):
        for sales, cost in [(0, 0), (0, 600000), (1, 0), (1.1, -20000), (2, 600000)]:
            active = model(self.case, sales, cost)
            for axis in ['Sales coefficient', 'Fixed-cost change']:
                for full_range in [False, True]:
                    with self.subTest(sales=sales, cost=cost, axis=axis, full_range=full_range):
                        rows, root, chart, _ = self.chart(active, axis, 'NPV', full_range)
                        anchors = [1, 1.1, sales] if axis == 'Sales coefficient' else [0, -20000, cost]
                        if root is not None:
                            anchors.append(root)
                        factor = 1 if axis == 'Sales coefficient' else 1000
                        self.assertGreater(len(rows), 1)
                        self.assertTrue(all(a['x'] < b['x'] for a, b in zip(rows, rows[1:])))
                        self.assertLessEqual(rows[0]['x'], min(anchors) + 1e-9)
                        self.assertGreaterEqual(rows[-1]['x'], max(anchors) - 1e-9)
                        self.assertLessEqual(chart['xAxis']['min'], min(anchors) / factor + 1e-9)
                        self.assertGreaterEqual(chart['xAxis']['max'], max(anchors) / factor - 1e-9)
                        self.assertGreaterEqual(rows[0]['x'], 0 if axis == 'Sales coefficient' else -self.case.annual_fixed_cost)

    def test_comparison_link_connects_actual_q1_and_current_points(self):
        active = model(self.case, 1.1, -20000)
        for axis in ['Sales coefficient', 'Fixed-cost change']:
            for metric in ['NPV', 'IRR']:
                with self.subTest(axis=axis, metric=metric):
                    _, _, _, series = self.chart(active, axis, metric)
                    link = series['comparison_link']['data']
                    self.assertEqual(len(link), 2)
                    expected = [self.point(series['q1_point']['data'][0]),
                                self.point(series['current_point']['data'][0])]
                    for actual, point in zip(link, expected):
                        self.assert_point(actual, *point)

    def test_comparison_link_is_omitted_at_the_baseline(self):
        for axis in ['Sales coefficient', 'Fixed-cost change']:
            for metric in ['NPV', 'IRR']:
                with self.subTest(axis=axis, metric=metric):
                    _, _, _, series = self.chart(self.baseline, axis, metric)
                    self.assertNotIn('comparison_link', series)

    def test_no_irr_does_not_generate_a_fake_current_point_or_link(self):
        active = model(self.case, 0, 600000)
        self.assertIsNone(active.irr)
        for axis in ['Sales coefficient', 'Fixed-cost change']:
            with self.subTest(axis=axis):
                _, _, _, series = self.chart(active, axis, 'IRR')
                self.assertEqual(series['current_point']['data'], [])
                self.assertNotIn('comparison_link', series)
                self.assertEqual(len(series['q1_point']['data']), 1)
                self.assertFalse(series['scenario_curve'].get('connectNulls', False))
                _, _, _, npv_series = self.chart(active, axis, 'NPV')
                self.assertEqual(len(npv_series['current_point']['data']), 1)

    def test_curve_values_keep_the_sweep_and_held_driver_distinct(self):
        active = model(self.case, 1.1, -20000)
        for axis in ['Sales coefficient', 'Fixed-cost change']:
            rows, _ = sensitivity(self.case, active, axis)
            for index in [0, len(rows) // 2, len(rows) - 1]:
                row = rows[index]
                with self.subTest(axis=axis, index=index):
                    if axis == 'Sales coefficient':
                        reference = model(self.case, row['x'], 0)
                        current = model(self.case, row['x'], active.fixed_cost_change)
                    else:
                        reference = model(self.case, 1, row['x'])
                        current = model(self.case, active.sales_coefficient, row['x'])
                    self.assertAlmostEqual(row['reference_npv_eur'], reference.npv, places=6)
                    self.assertAlmostEqual(row['current_npv_eur'], current.npv, places=6)
                    for key, expected in [('reference_irr', reference.irr), ('current_irr', current.irr)]:
                        if expected is None:
                            self.assertIsNone(row[key])
                        else:
                            self.assertAlmostEqual(row[key], expected, places=10)


    def test_extended_driver_curves_and_roots_hold_prices_costs_and_response(self):
        kwargs = dict(price_coefficient=1.05, variable_cost_coefficient=1.1, demand_elasticity=2)
        active = model(self.case, 1.045, -20000, **kwargs)
        for axis in ['Sales coefficient', 'Fixed-cost change']:
            rows, root, _, _ = self.chart(active, axis, 'NPV')
            for row in rows[::23]:
                m = row['x'] if axis == 'Sales coefficient' else active.sales_coefficient
                d = active.fixed_cost_change if axis == 'Sales coefficient' else row['x']
                expected = model(self.case, m, d, **kwargs)
                self.assertAlmostEqual(row['current_npv_eur'], expected.npv, places=6)
                self.assertAlmostEqual(row['effective_sales_coefficient'], m * 1.05**-2, places=10)
            self.assertIsNotNone(root)
            m = root if axis == 'Sales coefficient' else active.sales_coefficient
            d = active.fixed_cost_change if axis == 'Sales coefficient' else root
            self.assertAlmostEqual(model(self.case, m, d, **kwargs).npv, 0, places=5)

    def test_price_curve_discloses_response_and_preserves_two_price_roots(self):
        active = model(self.case, 1.06, -20000, demand_elasticity=1.4)
        chart = pricing_options(self.case, active)
        series = {item['id']: item for item in chart['series']}
        self.assertIn('price_fixed_volume', series)
        self.assertEqual(len(series['price_break_even']['data']), 2)
        for price, value in series['price_break_even']['data']:
            self.assertEqual(value, 0)
            expected = model(self.case, 1.06, -20000,
                             price_coefficient=price/self.case.price, demand_elasticity=1.4)
            self.assertAlmostEqual(expected.npv, 0, places=5)
        self.assertIn('not an estimated', chart['aria']['description'])
        response = series['price_response']['data']
        for price, value in response[::29]:
            expected = model(self.case, 1.06, -20000,
                             price_coefficient=price/self.case.price, demand_elasticity=1.4)
            self.assertAlmostEqual(value * 1000, expected.npv, places=6)
        self.assertGreater(max(p[1] for p in response), response[0][1])
        self.assertGreater(max(p[1] for p in response), response[-1][1])
        marks = series['price_response']['markLine']['data']
        self.assertTrue(any(mark.get('yAxis') == 0 for mark in marks))
        self.assertEqual(series['price_current']['data'][0][0], self.case.price)

    def test_price_curve_avoids_duplicate_series_when_no_volume_response(self):
        active = model(self.case, 1.1, -20000)
        chart = pricing_options(self.case, active)
        ids = [series['id'] for series in chart['series']]
        self.assertNotIn('price_fixed_volume', ids)
        self.assertIn('price_response', ids)
        self.assertEqual(chart['xAxis']['min'], self.case.price * .8)
        self.assertEqual(chart['xAxis']['max'], self.case.price * 1.3)

    def test_joint_frontier_shading_and_current_point_use_one_held_cost_scenario(self):
        kwargs = dict(price_coefficient=1.05, variable_cost_coefficient=.95, demand_elasticity=2)
        active = model(self.case, 1.045, -20000, **kwargs)
        chart = decision_frontier_options(self.case, active)
        series = {item['id']: item for item in chart['series']}
        self.assertNotIn('q1_point', series)
        self.assertNotIn('q2_point', series)
        self.assertEqual(series['decision_current']['data'], [[self.case.price * 1.05, 1.045, active.npv]])
        self.assertEqual(series['decision_boundary']['lineStyle']['type'], 'dashed')
        boundary = series['decision_boundary']['data']
        for price, demand in boundary[::31]:
            if demand is None:
                continue
            held = dict(kwargs, price_coefficient=price/self.case.price)
            self.assertAlmostEqual(model(self.case, demand, -20000, **held).npv, 0, places=5)
            self.assertGreater(model(self.case, demand+.001, -20000, **held).npv, 0)
        self.assertGreater(len(series['decision_positive_area']['data']), 0)
        for left, right, lroot, rroot, top in series['decision_positive_area']['data']:
            self.assertLessEqual(lroot, top)
            self.assertLessEqual(rroot, top)
            for price, demand in [(left, lroot), (right, rroot)]:
                held = dict(kwargs, price_coefficient=price/self.case.price)
                self.assertGreaterEqual(model(self.case, demand, -20000, **held).npv, -.01)

    def test_joint_frontier_does_not_shade_an_infeasible_price_demand_region(self):
        active = model(self.case, 1.0, 0, variable_cost_coefficient=10)
        chart = decision_frontier_options(self.case, active)
        series = {item['id']: item for item in chart['series']}
        self.assertEqual(series['decision_positive_area']['data'], [])


    def test_new_charts_keep_units_clear_without_long_left_axis_titles(self):
        active = model(self.case, 1.045, -20000, demand_elasticity=2)
        for chart in [pricing_options(self.case, active), decision_frontier_options(self.case, active)]:
            self.assertEqual(chart['yAxis']['name'], '')
            self.assertGreater(chart['legend']['top'], chart['title']['top'] + 15)
            self.assertGreater(chart['grid']['top'], chart['legend']['top'] + 25)
            self.assertEqual(chart['xAxis']['name'], 'Price · EUR / can')
        self.assertEqual(decision_frontier_options(self.case, active)['title']['text'], 'Pre-price demand · × Q1')


if __name__ == '__main__':
    unittest.main()
