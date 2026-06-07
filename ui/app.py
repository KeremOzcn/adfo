"""
ui/app.py  —  Main page
Run with: streamlit run ui/app.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
from core.warehouse import Warehouse
from ui.components.warehouse_plot import plot_warehouse_layout

st.set_page_config(
    page_title="Warehouse Optimization",
    page_icon="📦",
    layout="wide",
)

@st.cache_resource
def get_wh():
    return Warehouse()

wh = get_wh()

# ── Title ─────────────────────────────────────────────────────────
st.title("📦 Warehouse Optimization")
st.markdown(
    "**Paper:** Kübler, Glock, Bauernhansl (2020) · "
    "*Computers & Industrial Engineering 147, 106645*"
)
st.divider()

# ── Two columns: description + metrics ───────────────────────────
col_left, col_right = st.columns([3, 1])

with col_left:
    st.subheader("Project Overview")
    st.markdown("""
This application solves three interrelated problems in a **picker-to-parts manual warehouse**:

- **Order Batching** — group orders so the picker walks less
- **Picker Routing** — shortest tour for each batch
- **Dynamic Storage Assignment** — keep items on the right rack

Two algorithms are compared:

| Algorithm | Method | Advantage |
|---|---|---|
| **DEPSO** | Discrete PSO (paper) | High quality, strong search |
| **RBRS-AE** | Regret Search + LNS (new) | Fast, deterministic convergence |

**From the menu:**
- 🎯 **Single Run** — run a single algorithm, visualize routes
- ⚖️ **Comparison** — run all 4 algorithms side by side
""")

with col_right:
    st.subheader("Dataset")
    st.metric("Locations", f"{wh.total_locations:,}")
    st.metric("Items", "6,000")
    st.metric("Scenarios", "2")
    st.metric("Test horizon", "9 × 20 sub-periods")
    st.metric("Picker capacity", "100 WU")

st.divider()

# ── Warehouse visualization ───────────────────────────────────────
st.subheader("Warehouse Layout")
st.caption(
    f"{wh.num_aisles} picking aisles · {wh.num_blocks} blocks · "
    f"{wh.total_locations:,} locations · "
    f"Depot: ({wh.depot_x:.0f}, {wh.depot_y:.0f}) LU"
)

show_cls = st.checkbox("Show ABC class locations (sample)",
                       help="A=red (near depot), B=orange, C=blue")

fig = plot_warehouse_layout(wh, show_class_locations=show_cls)
st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Gray blocks represent racks. "
    "Horizontal gaps are cross aisles. "
    "Depot is at the bottom-right (black square)."
)

# ── Reference results ─────────────────────────────────────────────
st.divider()
st.subheader("Validation Results (50 orders, Scenario 1)")
r1, r2, r3, r4 = st.columns(4)
r1.metric("SOP",     "1,384 LU", "baseline")
r2.metric("FCFS",    "187 LU",   "-86%")
r3.metric("RBRS-AE", "157 LU",   "-89%")
r4.metric("DEPSO",   "139 LU",   "-90% (paper target -88%)")
