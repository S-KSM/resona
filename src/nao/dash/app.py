"""Streamlit entry — sidebar nav across Live / Setup / Calibrate."""
from __future__ import annotations

import pathlib

import streamlit as st

st.set_page_config(page_title="NAO — Brain Console", layout="wide")

_HERE = pathlib.Path(__file__).parent
_VIEWS = _HERE / "views"

pg = st.navigation(
    [
        st.Page(str(_VIEWS / "live.py"), title="Live", default=True),
        st.Page(str(_VIEWS / "setup.py"), title="Setup"),
        st.Page(str(_VIEWS / "calibrate.py"), title="Calibrate"),
    ]
)
pg.run()
