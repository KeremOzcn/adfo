"""
ui/pages/2_Comparison.py
========================
Compare all algorithms side by side.
DEPSO vs RBRS-AE vs baselines.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from core.warehouse import Warehouse
from core.data_loader import DataLoader
from benchmarks.sop import SOP
from benchmarks.fcfs import FCFS
from algorithms.depso import DEPSO
from algorithms.rbrs_ae import RBRS_AE

st.set_page_config(page_title="Comparison", page_icon="⚖️", layout="wide")
st.title("⚖️ Algorithm Comparison")
st.markdown("SOP · FCFS · **DEPSO** · **RBRS-AE** — side by side on the same problem.")

@st.cache_resource
def get_wh(): return Warehouse()
@st.cache_resource
def get_loader(): return DataLoader()

wh     = get_wh()
loader = get_loader()

# ── Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.header("🗂️ Problem")
    scenario  = st.selectbox("Scenario", [1, 2], format_func=lambda x: f"Scenario {x} ({'High' if x==1 else 'Low'} dynamic)")
    period    = st.number_input("Period (1-9)", 1, 9, 1)
    subperiod = st.number_input("Sub-period (1-20)", 1, 20, 20)
    max_ord   = st.slider("Max orders", 10, 200, 50)

    st.divider()
    st.header("🔧 DEPSO")
    d_iter = st.slider("Iterations", 50, 500, 200)
    d_part = st.slider("Particles", 2, 10, 5)

    st.divider()
    st.header("🔧 RBRS-AE")
    r_iter  = st.slider("Max iterations", 20, 200, 100)
    r_noimp = st.slider("No-improvement limit", 5, 30, 15)
    r_shift = st.slider("Shift attempts", 20, 200, 50)
    r_swap  = st.slider("Swap attempts", 20, 200, 50)

    seed = st.number_input("Seed", value=42)

# ── Load problem ──────────────────────────────────────────────────
orders = loader.load_orders(scenario, period, subperiod).orders[:max_ord]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Orders", len(orders))
c2.metric("Orderlines", sum(o.num_orderlines for o in orders))
c3.metric("Total weight", f"{sum(o.total_weight for o in orders):.0f} WU")
c4.metric("Unique locations", len({l for o in orders for l in o.locations}))

st.divider()

# ── Run ───────────────────────────────────────────────────────────
if st.button("🚀 Run All Algorithms", type="primary", use_container_width=True):

    algos = [
        ("SOP",     SOP()),
        ("FCFS",    FCFS()),
        ("DEPSO",   DEPSO(num_iterations=d_iter, num_particles=d_part, seed=int(seed))),
        ("RBRS-AE", RBRS_AE(max_iterations=r_iter, max_no_improvement=r_noimp,
                             shift_attempts=r_shift, swap_attempts=r_swap, seed=int(seed))),
    ]

    solutions = {}
    prog = st.progress(0)
    for i, (label, algo) in enumerate(algos):
        with st.spinner(f"Running {label}..."):
            solutions[label] = algo.solve(orders, wh)
        prog.progress((i + 1) / len(algos))

    st.success("✅ All algorithms completed.")

    # ── Results table ────────────────────────────────────────────
    st.subheader("📊 Results Table")
    sop_td = solutions["SOP"].total_travel_distance
    rows = []
    for label, sol in solutions.items():
        vs_sop = (sol.total_travel_distance - sop_td) / sop_td * 100
        rows.append({
            "Algorithm":            label,
            "Travel Distance (LU)": f"{sol.total_travel_distance:.1f}",
            "Number of batches":    sol.num_batches,
            "Avg. utilization":     f"{sol.avg_capacity_utilization:.2f}",
            "Runtime (s)":          f"{sol.runtime_seconds:.2f}",
            "vs SOP":               f"{vs_sop:+.1f}%",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Bar chart ─────────────────────────────────────────────────
    st.subheader("📉 Travel Distance Comparison")
    labels = list(solutions.keys())
    dists  = [s.total_travel_distance for s in solutions.values()]
    colors = ["#95a5a6", "#7f8c8d", "#e74c3c", "#3498db"]

    fig = go.Figure(go.Bar(
        x=labels, y=dists,
        marker_color=colors,
        text=[f"{d:.0f}" for d in dists],
        textposition="outside",
    ))
    fig.update_layout(
        yaxis_title="Total Travel Distance (LU)",
        plot_bgcolor="white", height=380, showlegend=False,
        yaxis=dict(gridcolor="#ecf0f1"),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── DEPSO vs RBRS-AE side by side ────────────────────────────
    st.subheader("🆚 DEPSO vs RBRS-AE")
    col1, col2 = st.columns(2)

    dep_sol  = solutions["DEPSO"]
    rbrs_sol = solutions["RBRS-AE"]
    dep_td   = dep_sol.total_travel_distance
    rbrs_td  = rbrs_sol.total_travel_distance
    diff_pct = (rbrs_td - dep_td) / dep_td * 100

    with col1:
        st.metric("DEPSO", f"{dep_td:.1f} LU", f"{dep_sol.runtime_seconds:.1f}s")
    with col2:
        st.metric("RBRS-AE", f"{rbrs_td:.1f} LU",
                  f"{rbrs_sol.runtime_seconds:.1f}s  ({diff_pct:+.1f}% vs DEPSO)",
                  delta_color="inverse")

    # Convergence
    if dep_sol.convergence_history or rbrs_sol.convergence_history:
        st.subheader("📈 Convergence Plot")
        fig2 = go.Figure()
        if dep_sol.convergence_history:
            fig2.add_trace(go.Scatter(
                y=dep_sol.convergence_history, name="DEPSO",
                line=dict(color="#e74c3c", width=2)))
        if rbrs_sol.convergence_history:
            fig2.add_trace(go.Scatter(
                y=rbrs_sol.convergence_history, name="RBRS-AE",
                line=dict(color="#3498db", width=2, dash="dash")))
        # Baseline reference lines
        fig2.add_hline(y=solutions["FCFS"].total_travel_distance,
                       line_dash="dot", line_color="#7f8c8d",
                       annotation_text="FCFS", annotation_position="right")
        fig2.update_layout(
            xaxis_title="Iteration",
            yaxis_title="Travel Distance (LU)",
            plot_bgcolor="white", height=380,
            yaxis=dict(gridcolor="#ecf0f1"),
            legend=dict(x=0.8, y=0.95),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Paper targets ─────────────────────────────────────────────
    st.divider()
    st.subheader("🎯 Comparison with Paper Targets")
    p1, p2, p3 = st.columns(3)
    dep = solutions["DEPSO"]
    vs_sop_actual  = (dep.total_travel_distance - sop_td) / sop_td * 100
    vs_fcfs_actual = (dep.total_travel_distance - solutions["FCFS"].total_travel_distance) / solutions["FCFS"].total_travel_distance * 100
    p1.metric("DEPSO vs SOP",  f"{vs_sop_actual:+.1f}%",  "Target: ~-88%")
    p2.metric("DEPSO vs FCFS", f"{vs_fcfs_actual:+.1f}%", "Target: ~-39%")
    p3.metric("RBRS-AE vs DEPSO", f"{diff_pct:+.1f}%",   "Positive = DEPSO better")

else:
    st.info("⬅️ Set parameters and press **Run All Algorithms**.")
