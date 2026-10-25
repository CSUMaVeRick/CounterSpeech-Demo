import hashlib
from pathlib import Path

import streamlit as st
import streamlit.components.v2 as components

ROOT = Path(__file__).parent


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
