"""Contracts for the simplified two-lever operating views."""
import unittest
from dataclasses import replace
from charts import operating_sensitivity,operating_options,sales_sensitivity,sales_options,decision_frontier_options
from finance import load_case,model

class ChartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.case=load_case()
    def result(self,m=1.1,d=-20000,p=1):return model(self.case,m,d,price_coefficient=p,demand_elasticity=1)
    def series(self,chart):return {s['id']:s for s in chart['series']}

    def test_original_baselines_stay_exact_with_price_response(self):
        for m,d,npv in [(1,0,-216165.7623464),(1.1,-20000,91902.5954984)]:
            r=self.result(m,d)
            self.assertAlmostEqual(r.npv,npv,places=5)
            for axis in ['Can sales','Fixed-cost change']:
                rows,roots=operating_sensitivity(self.case,r,axis)
                for metric in ['NPV','IRR']:
                    chart=operating_options(self.case,r,rows,roots,axis,metric)
                    s=self.series(chart)
                    x=r.sales_coefficient*100 if axis=='Can sales' else d/1000
                    y=r.npv/1000 if metric=='NPV' else r.irr
                    self.assertAlmostEqual(s['current_point']['data'][0][0],x)
                    self.assertAlmostEqual(s['current_point']['data'][0][1],y)
                    self.assertAlmostEqual(s['q1_point']['data'][0][1],model(self.case).npv/1000 if metric=='NPV' else model(self.case).irr)

    def test_sweeps_hold_price_and_other_main_control(self):
        active=self.result(m=1.2,d=-20000)
        for axis in ['Can sales','Fixed-cost change']:
            rows,roots=operating_sensitivity(self.case,active,axis)
            for row in rows[::23]:
                m=row['x'] if axis=='Can sales' else 1.2
                d=-20000 if axis=='Can sales' else row['x']
                expected=model(self.case,m,d)
                self.assertAlmostEqual(row['current_npv_eur'],expected.npv,places=6)
                self.assertAlmostEqual(row['actual_sales_coefficient'],m,places=10)
                self.assertEqual(row['price_per_can'],5.1)
            for root in roots:
                m=root if axis=='Can sales' else 1.2
                d=-20000 if axis=='Can sales' else root
                self.assertAlmostEqual(model(self.case,m,d).npv,0,places=5)

    def test_sales_axis_changes_cans_at_fixed_price(self):
        rows,_=operating_sensitivity(self.case,self.result(),'Can sales')
        self.assertTrue(all(a['actual_sales_coefficient']<b['actual_sales_coefficient'] for a,b in zip(rows,rows[1:])))
        self.assertTrue(all(r['price_per_can']==5.1 for r in rows))

    def test_fixed_hurdles_and_true_root_points(self):
        active=self.result(m=1.2)
        for axis in ['Can sales','Fixed-cost change']:
            rows,roots=operating_sensitivity(self.case,active,axis)
            for metric in ['NPV','IRR']:
                s=self.series(operating_options(self.case,active,rows,roots,axis,metric))
                hurdle=0 if metric=='NPV' else self.case.wacc
                marks=s['scenario_curve']['markLine']['data']
                self.assertTrue(any(x.get('yAxis')==hurdle for x in marks))
                if roots:
                    for point in s['break_even']['data']:self.assertEqual(point[1],hurdle)

    def test_focus_and_full_axes_include_current_and_original(self):
        active=self.result(m=.7,d=400000)
        for axis in ['Can sales','Fixed-cost change']:
            for full in [False,True]:
                rows,roots=operating_sensitivity(self.case,active,axis,full)
                anchors=[1.,1.1,active.sales_coefficient] if axis=='Can sales' else [0,-20000,400000]
                self.assertLessEqual(rows[0]['x'],min(anchors))
                self.assertGreaterEqual(rows[-1]['x'],max(anchors))
                self.assertTrue(all(a['x']<b['x'] for a,b in zip(rows,rows[1:])))

    def test_sales_only_curve_locks_price_and_fixed_costs(self):
        rows,root=sales_sensitivity(self.case)
        for row in rows[::19]:
            expected=model(self.case,row['sales_coefficient'],-20000)
            self.assertAlmostEqual(row['npv'],expected.npv,places=6)
        self.assertAlmostEqual(root,1.0625489438585962,places=10)
        self.assertAlmostEqual(model(self.case,root,-20000).npv,0,places=5)
        chart=sales_options(self.case);s=self.series(chart)
        for i,m in enumerate([.9,1,1.1]):
            self.assertAlmostEqual(s[f'sales_example_{i}']['data'][0][1]*1000,model(self.case,m,-20000).npv,places=6)
        self.assertIn('not flat annual volume',chart['aria']['description'])

    def test_price_fixed_cost_frontier_shades_below_true_boundary(self):
        active=self.result(p=1.05)
        chart=decision_frontier_options(self.case,active);s=self.series(chart)
        self.assertNotIn('q1_point',s);self.assertNotIn('q2_point',s)
        self.assertEqual(s['decision_current']['data'],[[active.unit_price,220.,active.npv]])
        self.assertEqual(s['decision_boundary']['lineStyle']['type'],'dashed')
        for price,cost in s['decision_boundary']['data'][::29]:
            if cost is None:continue
            self.assertAlmostEqual(self.result(d=cost*1000-240000,p=price/self.case.price).npv,0,places=5)
            self.assertGreater(self.result(d=cost*1000-240001,p=price/self.case.price).npv,0)
        self.assertGreater(len(s['decision_positive_area']['data']),0)
        for left,right,bottom,lefttop,righttop in s['decision_positive_area']['data']:
            self.assertGreaterEqual(lefttop,bottom);self.assertGreaterEqual(righttop,bottom)
            for price,top in [(left,lefttop),(right,righttop)]:
                midpoint=(bottom+top)/2
                self.assertGreaterEqual(self.result(d=midpoint*1000-240000,p=price/self.case.price).npv,-.01)

    def test_no_false_shading_when_even_zero_fixed_cost_cannot_help(self):
        case=replace(self.case,capex=100000000)
        active=model(case,1.1,-20000,demand_elasticity=1)
        chart=decision_frontier_options(case,active)
        self.assertEqual(self.series(chart)['decision_positive_area']['data'],[])

    def test_map_examples_include_real_npv_and_annual_cost_headroom(self):
        s=self.series(decision_frontier_options(self.case,self.result()))
        examples={p['name']:p['value'] for p in s['decision_example']['data']}
        self.assertEqual(set(examples),{'A','B','C','D'})
        self.assertGreater(examples['A'][2],0);self.assertLess(examples['D'][2],0)
        for point in examples.values():
            price,cost,npv,headroom=point
            expected=self.result(d=cost*1000-240000,p=price/5.1)
            self.assertAlmostEqual(npv,expected.npv,places=6)
            self.assertAlmostEqual(self.result(d=(cost*1000+headroom)-240000,p=price/5.1).npv,0,places=5)
        self.assertEqual(len(s['decision_example_ceiling']['data']),2)

    def test_map_remains_q2_when_q1_is_selected(self):
        q1=model(self.case)
        chart=decision_frontier_options(self.case,q1);s=self.series(chart)
        self.assertEqual(s['decision_current']['data'],[])
        for price,cost in s['decision_boundary']['data'][::29]:
            if cost is None:continue
            self.assertAlmostEqual(self.result(d=cost*1000-240000,p=price/5.1).npv,0,places=5)

    def test_mobile_unit_titles_and_axis_labels(self):
        chart=decision_frontier_options(self.case,self.result())
        self.assertEqual(chart['yAxis']['name'],'')
        self.assertGreater(chart['legend']['top'],chart['title']['top']+15)
        self.assertGreater(chart['grid']['top'],chart['legend']['top']+25)
        self.assertEqual(chart['xAxis']['name'],'Price · EUR / can')
        self.assertEqual(chart['title']['text'],'Annual fixed costs · EUR thousands')

if __name__=='__main__':unittest.main()
