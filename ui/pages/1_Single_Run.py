"""
ui/pages/1_Single_Run.py
========================
Tek algoritma, tek problem instance.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd

from core.warehouse import Warehouse
from core.data_loader import DataLoader
from benchmarks.sop import SOP
from benchmarks.fcfs import FCFS
from algorithms.depso import DEPSO
from algorithms.rbrs_ae import RBRS_AE
from ui.components.warehouse_plot import plot_batch_routes, plot_convergence

st.set_page_config(page_title="Tek Koşu", page_icon="🎯", layout="wide")
st.title("🎯 Tek Algoritma Koşusu")


@st.cache_resource
def get_wh():
    return Warehouse()


@st.cache_resource
def get_loader():
    return DataLoader()


wh     = get_wh()
loader = get_loader()

# ── Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.header("Problem")
    scenario  = st.selectbox("Senaryo", [1, 2],
                              format_func=lambda x: f"Senaryo {x} ({'Yüksek' if x==1 else 'Düşük'} dinamik)")
    period    = st.number_input("Periyot", 1, 9, 1)
    subperiod = st.number_input("Alt-periyot", 1, 20, 20)
    max_ord   = st.slider("Maks sipariş", 10, 300, 50)

    st.divider()
    st.header("Algoritma")
    algo_name = st.radio("Seç", ["SOP", "FCFS", "DEPSO", "RBRS-AE"])

    seed = st.number_input("Seed", value=42)

    if algo_name == "DEPSO":
        st.subheader("DEPSO Parametreleri")
        n_iter = st.slider("İterasyon", 50, 500, 200)
        n_part = st.slider("Parçacık", 2, 10, 5)
    elif algo_name == "RBRS-AE":
        st.subheader("RBRS-AE Parametreleri")
        r_iter  = st.slider("Maks iterasyon", 20, 200, 100)
        r_noimp = st.slider("No-improvement limiti", 5, 30, 15)
        r_shift = st.slider("Shift denemesi", 20, 200, 50)
        r_swap  = st.slider("Swap denemesi", 20, 200, 50)

# ── Problem bilgisi ───────────────────────────────────────────────
orders = loader.load_orders(scenario, period, subperiod).orders[:max_ord]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Sipariş", len(orders))
c2.metric("Orderline", sum(o.num_orderlines for o in orders))
c3.metric("Toplam ağırlık", f"{sum(o.total_weight for o in orders):.0f} WU")
c4.metric("Unique lokasyon", len({l for o in orders for l in o.locations}))

st.divider()

# ── Çalıştır ─────────────────────────────────────────────────────
if st.button("🚀 Çalıştır", type="primary", use_container_width=True):
    if algo_name == "SOP":
        algo = SOP()
    elif algo_name == "FCFS":
        algo = FCFS()
    elif algo_name == "DEPSO":
        algo = DEPSO(num_iterations=n_iter, num_particles=n_part, seed=int(seed))
    else:
        algo = RBRS_AE(max_iterations=r_iter, max_no_improvement=r_noimp,
                       shift_attempts=r_shift, swap_attempts=r_swap, seed=int(seed))

    with st.spinner(f"{algo_name} çalıştırılıyor..."):
        sol = algo.solve(orders, wh)

    st.success(f"✅ {algo_name} tamamlandı.")

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Travel Distance (LU)", f"{sol.total_travel_distance:.1f}")
    m2.metric("Batch sayısı", sol.num_batches)
    m3.metric("Ort. doluluk", f"{sol.avg_capacity_utilization:.2f}")
    m4.metric("Süre (s)", f"{sol.runtime_seconds:.2f}")
    m5.metric("İterasyon", sol.iterations_used or "—")

    if sol.convergence_history:
        st.subheader("Yakınsama Grafiği")
        st.plotly_chart(
            plot_convergence(sol.convergence_history, f"{algo_name} — iyileşme"),
            use_container_width=True)

    st.subheader("Picker Rotaları (ilk 5 batch)")
    st.plotly_chart(
        plot_batch_routes(wh, sol.batches, max_batches_to_show=5),
        use_container_width=True)

    st.subheader("Batch Detayları")
    rows = [{
        "Batch":               b.batch_id,
        "Sipariş":             len(b.orders),
        "Orderline":           b.num_orderlines,
        "Ağırlık (WU)":        f"{b.total_weight:.1f}",
        "Travel Distance (LU)":f"{b.travel_distance:.1f}",
        "Doluluk %":           f"{b.total_weight / 100 * 100:.0f}%",
    } for b in sol.batches[:25]]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    if len(sol.batches) > 25:
        st.caption(f"İlk 25 / {len(sol.batches)} batch gösteriliyor.")

else:
    st.info("Parametreleri ayarlayıp Çalıştır butonuna bas.")
