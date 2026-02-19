"""Docs page — renders Markdown files from /docs."""
from __future__ import annotations

from pathlib import Path
import streamlit as st

from core.config import APP_TITLE

st.set_page_config(page_title=f"Docs — {APP_TITLE}", page_icon="📚", layout="wide")

st.title("📚 Documentation")

docs_dir = Path(__file__).parent.parent / "docs"

md_files = sorted(docs_dir.glob("*.md"))
if not md_files:
    st.info("No documentation files found in /docs.")
    st.stop()

file_names = {f.stem.replace("_", " ").title(): f for f in md_files}

selected_name = st.sidebar.radio("Select document", list(file_names.keys()))
selected_file = file_names[selected_name]

content = selected_file.read_text(encoding="utf-8")
st.markdown(content, unsafe_allow_html=False)
