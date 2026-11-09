import hashlib

import streamlit as st
import streamlit.components.v2 as components

from . import ROOT


@st.cache_resource
def register(css, js):
    fingerprint = hashlib.sha256((css + js).encode()).hexdigest()[:12]
    return components.component(
        f"social_experiment_{fingerprint}", html='<div id="social-root"></div>', css=css, js=js
    )


def component():
    return register(
        (ROOT / "frontend/style.css").read_text(encoding="utf-8"),
        (ROOT / "frontend/component.js").read_text(encoding="utf-8"),
    )
