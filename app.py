"""Duchy Coaching Manager — main entry point.

Run with: streamlit run app.py
"""
import streamlit as st

from core.config import APP_TITLE
from core.db import init_db

# ---------------------------------------------------------------------------
# Page config (must be first Streamlit call)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🚴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Initialise DB
# ---------------------------------------------------------------------------
init_db()


# ---------------------------------------------------------------------------
# Optional password gate
# ---------------------------------------------------------------------------
def _check_auth() -> bool:
    try:
        password = st.secrets.get("APP_PASSWORD")
    except Exception:
        password = None

    if not password:
        st.session_state["auth_user"] = "local"
        return True

    if st.session_state.get("authenticated"):
        return True

    st.title(f"🔒 {APP_TITLE}")
    with st.form("login_form"):
        entered = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
    if submitted:
        if entered == password:
            st.session_state["authenticated"] = True
            st.session_state["auth_user"] = "web_user"
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not _check_auth():
    st.stop()


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
st.sidebar.title(f"🚴 {APP_TITLE}")
st.sidebar.caption("Coaching business manager")

pages = {
    "Dashboard": "pages/01_dashboard.py",
    "Clients": "pages/02_clients.py",
    "Coaches": "pages/03_coaches.py",
    "Import / Export": "pages/04_import_export.py",
    "Audit Log": "pages/05_audit_log.py",
    "Docs": "pages/06_docs.py",
}

# Multipage navigation is handled by Streamlit's built-in mechanism.
# This file serves as the landing redirect to Dashboard.
st.switch_page("pages/01_dashboard.py")
