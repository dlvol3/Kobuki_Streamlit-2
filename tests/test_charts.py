"""Financial and interaction contracts for the chart redesign."""
import unittest

from charts import options, sensitivity
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


if __name__ == '__main__':
    unittest.main()
