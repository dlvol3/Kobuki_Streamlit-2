"""Self-contained Apache ECharts 5.6 renderer using Streamlit components v2."""
from pathlib import Path
import streamlit as st

ASSETS=Path(__file__).parent/'assets'


class JsCode:
    """Mark only trusted chart callbacks authored in charts.py for JS revival."""
    def __init__(self,code):
        self.js_code={'$js':code}


_echart=st.components.v2.component(
    'kobuki_apache_echarts',
    html='<div id="chart" role="img" style="width:100%;height:345px;min-width:0;"></div>',
    js=(ASSETS/'echarts.min.js').read_text()+'\n'+(ASSETS/'chart_renderer.js').read_text(),
)


def st_echarts(*,options,height='345px',key=None):
    return _echart(data={'options':options,'height':height,'chartId':key},key=key)

