SCOPE_VERSION = "sales-fixed-v4"
from pathlib import Path
import streamlit as st

ASSETS=Path(__file__).parent/'assets'
vertical_drivers=st.components.v2.component(
    'kobuki_sales_cost_drivers',
    html=(ASSETS/'controls.html').read_text(),
    css=(ASSETS/'controls.css').read_text(),
    js=(ASSETS/'controls.js').read_text(),
)

