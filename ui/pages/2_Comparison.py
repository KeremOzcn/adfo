"""
ui/pages/2_Comparison.py
========================
Tüm algoritmaları yan yana karşılaştır.
DEPSO vs RBRS-AE vs baseline'lar.
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

st.set_page_config(page_title="Karşılaştırma", page_icon="⚖️", layout="wide")
st.title("⚖️ Algoritma Karşılaştırması")
st.markdown("SOP · FCFS · **DEPSO** · **RBRS-AE** — aynı problem üzerinde yan yana.")

@st.cache_resource
def get_wh(): return Warehouse()
@st.cache_resource
def get_loader(): return DataLoader()

wh     = get_wh()
loader = get_loader()

# ── Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.header("🗂️ Problem")
    scenario  = st.selectbox("Senaryo", [1, 2], format_func=lambda x: f"Senaryo {x} ({'Yüksek' if x==1 else 'Düşük'} dinamik)")
    period    = st.number_input("Periyot (1-9)", 1, 9, 1)
    subperiod = st.number_input("Alt-periyot (1-20)", 1, 20, 20)
    max_ord   = st.slider("Maks sipariş", 10, 200, 50)

    st.divider()
    st.header("🔧 DEPSO")
    d_iter = st.slider("İterasyon", 50, 500, 200)
    d_part = st.slider("Parçacık", 2, 10, 5)

    st.divider()
    st.header("🔧 RBRS-AE")
    r_iter  = st.slider("Maks iterasyon", 20, 200, 100)
    r_noimp = st.slider("No-improvement limiti", 5, 30, 15)
    r_shift = st.slider("Shift denemesi", 20, 200, 50)
    r_swap  = st.slider("Swap denemesi", 20, 200, 50)

    seed = st.number_input("Seed", value=42)

# ── Problem yükle ────────────────────────────────────────────────
orders = loader.load_orders(scenario, period, subperiod).orders[:max_ord]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Sipariş", len(orders))
c2.metric("Orderline", sum(o.num_orderlines for o in orders))
c3.metric("Toplam ağırlık", f"{sum(o.total_weight for o in orders):.0f} WU")
c4.metric("Unique lokasyon", len({l for o in orders for l in o.locations}))

st.divider()

# ── Çalıştır ─────────────────────────────────────────────────────
if st.button("🚀 Tüm Algoritmaları Çalıştır", type="primary", use_container_width=True):

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
        with st.spinner(f"{label} çalıştırılıyor..."):
            solutions[label] = algo.solve(orders, wh)
        prog.progress((i + 1) / len(algos))

    st.success("✅ Tüm algoritmalar tamamlandı.")

    # ── Sonuç tablosu ────────────────────────────────────────────
    st.subheader("📊 Sonuç Tablosu")
    sop_td = solutions["SOP"].total_travel_distance
    rows = []
    for label, sol in solutions.items():
        vs_sop = (sol.total_travel_distance - sop_td) / sop_td * 100
        rows.append({
            "Algoritma":           label,
            "Travel Distance (LU)": f"{sol.total_travel_distance:.1f}",
            "Batch sayısı":         sol.num_batches,
            "Ort. doluluk":         f"{sol.avg_capacity_utilization:.2f}",
            "Süre (s)":             f"{sol.runtime_seconds:.2f}",
            "vs SOP":               f"{vs_sop:+.1f}%",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Bar chart ─────────────────────────────────────────────────
    st.subheader("📉 Travel Distance Karşılaştırması")
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

    # ── DEPSO vs RBRS-AE yan yana ─────────────────────────────────
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
        st.subheader("📈 Yakınsama Grafiği")
        fig2 = go.Figure()
        if dep_sol.convergence_history:
            fig2.add_trace(go.Scatter(
                y=dep_sol.convergence_history, name="DEPSO",
                line=dict(color="#e74c3c", width=2)))
        if rbrs_sol.convergence_history:
            fig2.add_trace(go.Scatter(
                y=rbrs_sol.convergence_history, name="RBRS-AE",
                line=dict(color="#3498db", width=2, dash="dash")))
        # Baseline çizgileri
        fig2.add_hline(y=solutions["FCFS"].total_travel_distance,
                       line_dash="dot", line_color="#7f8c8d",
                       annotation_text="FCFS", annotation_position="right")
        fig2.update_layout(
            xaxis_title="İterasyon",
            yaxis_title="Travel Distance (LU)",
            plot_bgcolor="white", height=380,
            yaxis=dict(gridcolor="#ecf0f1"),
            legend=dict(x=0.8, y=0.95),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Paper hedefleri ───────────────────────────────────────────
    st.divider()
    st.subheader("🎯 Paper Hedefleriyle Karşılaştırma")
    p1, p2, p3 = st.columns(3)
    dep = solutions["DEPSO"]
    vs_sop_actual  = (dep.total_travel_distance - sop_td) / sop_td * 100
    vs_fcfs_actual = (dep.total_travel_distance - solutions["FCFS"].total_travel_distance) / solutions["FCFS"].total_travel_distance * 100
    p1.metric("DEPSO vs SOP",  f"{vs_sop_actual:+.1f}%",  "Hedef: ~-88%")
    p2.metric("DEPSO vs FCFS", f"{vs_fcfs_actual:+.1f}%", "Hedef: ~-39%")
    p3.metric("RBRS-AE vs DEPSO", f"{diff_pct:+.1f}%",   "Pozitif = DEPSO daha iyi")

else:
    st.info("⬅️ Parametreleri ayarlayıp **Tüm Algoritmaları Çalıştır** butonuna bas.")
