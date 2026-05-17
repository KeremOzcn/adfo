"""
ui/pages/3_Dynamic_Relocation.py
=================================
Dinamik storage relocation analizi.
9 periyot boyunca Holt-Winters + Relocation algoritması.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from core.warehouse import Warehouse
from core.data_loader import DataLoader
from core.forecasting import ItemForecaster
from algorithms.relocation import DynamicRelocation
from algorithms.rbrs_ae import RBRS_AE
from algorithms.depso import DEPSO
import numpy as np

st.set_page_config(page_title="Dynamic Relocation", page_icon="🔄", layout="wide")
st.title("🔄 Dinamik Storage Relocation")
st.markdown(
    "Her periyot sonunda **Holt-Winters** ile talep tahmin edilir, "
    "yanlış sınıftaki ürünler tespit edilir ve relocation önerileri değerlendirilir."
)


@st.cache_resource
def get_wh():    return Warehouse()
@st.cache_resource
def get_loader(): return DataLoader()


wh     = get_wh()
loader = get_loader()

# ── Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Parametreler")
    scenario   = st.selectbox("Senaryo", [1, 2],
                              format_func=lambda x: f"Senaryo {x} ({'Yüksek' if x==1 else 'Düşük'} dinamik)")
    max_orders = st.slider("Sipariş / alt-periyot", 10, 200, 50)
    max_sugg   = st.slider("Maks relocation önerisi", 5, 50, 20)
    algo_choice= st.radio("Routing algoritması", ["RBRS-AE", "DEPSO"])
    seed       = st.number_input("Seed", value=42)

    st.divider()
    st.markdown("**Paper parametreleri:**")
    st.markdown("- α=0.19, β=0.053, γ=0.10")
    st.markdown("- o=2 (yanlış sınıf eşiği)")
    st.markdown("- u=1 (hedef sınıf eşiği)")
    st.markdown("- Maks öneri: 50")

# ── Çalıştır ─────────────────────────────────────────────────────
if st.button("🚀 9 Periyot Simülasyonunu Başlat", type="primary",
             use_container_width=True):

    # Setup
    items          = loader.load_items()
    item_locations = [it.initial_location for it in items]
    item_classes   = [it.class_period1    for it in items]
    loc_classes    = loader.load_location_classes()

    demand = loader.load_scenario_demand(scenario)

    # Forecaster
    forecaster = ItemForecaster()
    with st.spinner("Holt-Winters modelleri fit ediliyor (12 periyot ısınma)..."):
        forecaster.fit_all(demand, warmup_periods=12)

    # Relocation
    reloc = DynamicRelocation(wh, loc_classes)
    reloc.max_suggestions = max_sugg
    reloc.initialize(item_locations, item_classes)

    # Algoritma
    if algo_choice == "RBRS-AE":
        algo = RBRS_AE(seed=int(seed), max_iterations=30)
    else:
        algo = DEPSO(num_iterations=100, seed=int(seed))

    # 9 periyot boyunca çalıştır
    results = []
    prog    = st.progress(0)
    status  = st.empty()

    for period in range(1, 10):
        status.info(f"Periyot {period}/9 işleniyor...")

        # Tahmin
        forecasts = forecaster.predict_all(tau=1)
        fc_cls    = reloc._classify_by_forecast(forecasts)
        reloc._update_class_tracking(fc_cls)

        # Siparişler (ilk alt-periyot)
        orders = loader.load_orders(scenario, period, 1).orders[:max_orders]

        # Relocation
        result = reloc.run_period(period, orders, forecasts, algo)
        results.append(result)

        # Forecaster güncelle (gerçek talep ile)
        actual = demand[:, 11 + period]
        forecaster.update_all(actual)

        # Sınıf tracking'i gerçek talep sonrası tekrar güncelle
        # (bir sonraki periyot için doğru başlangıç noktası)
        next_forecasts = forecaster.predict_all(tau=1)
        next_fc = reloc._classify_by_forecast(next_forecasts)
        reloc._update_class_tracking(next_fc)

        prog.progress(period / 9)

    status.success("✅ 9 periyot tamamlandı.")

    # ── Sonuç tablosu ─────────────────────────────────────────────
    st.subheader("📊 Periyot Bazlı Sonuçlar")
    rows = [{
        "Periyot":       r.period,
        "Test Sayısı":   r.num_suggestions_tested,
        "Kabul":         r.num_accepted,
        "Ret":           r.num_rejected,
        "TD Önce (LU)":  f"{r.travel_distance_before:.0f}",
        "TD Sonra (LU)": f"{r.travel_distance_after:.0f}",
        "Azalma %":      f"{r.reduction_pct:.2f}%",
        "Effort %":      f"{r.relocation_effort_pct:.2f}%",
        "Net %":         f"{r.net_improvement_pct:.2f}%",
    } for r in results]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Ortalama metrikler ─────────────────────────────────────────
    valid = [r for r in results if r.travel_distance_before > 0]
    if valid:
        avg_red    = sum(r.reduction_pct    for r in valid) / len(valid)
        avg_effort = sum(r.relocation_effort_pct for r in valid) / len(valid)
        avg_net    = sum(r.net_improvement_pct   for r in valid) / len(valid)
        total_acc  = sum(r.num_accepted for r in results)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Ort. TD Azalması",  f"{avg_red:.2f}%",   "Hedef: ~15%")
        c2.metric("Ort. Relocation Effort", f"{avg_effort:.2f}%", "Hedef: ~2.79%")
        c3.metric("Ort. Net İyileşme", f"{avg_net:.2f}%",   "Hedef: ~12.23%")
        c4.metric("Toplam Kabul Edilen", total_acc)

    # ── Grafik: TD Azalması ve Effort ─────────────────────────────
    st.subheader("📈 Periyot Bazlı Değişim")
    periods = [r.period for r in results]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=periods,
        y=[r.reduction_pct for r in results],
        name="TD Azalması %",
        line=dict(color="#2ecc71", width=2),
        mode="lines+markers",
    ))
    fig.add_trace(go.Scatter(
        x=periods,
        y=[r.relocation_effort_pct for r in results],
        name="Relocation Effort %",
        line=dict(color="#e74c3c", width=2, dash="dash"),
        mode="lines+markers",
    ))
    fig.add_trace(go.Scatter(
        x=periods,
        y=[r.net_improvement_pct for r in results],
        name="Net İyileşme %",
        line=dict(color="#3498db", width=3),
        mode="lines+markers",
    ))

    # Paper hedef çizgileri
    paper_red = 15.02 if scenario == 1 else 7.45
    paper_net = 12.23 if scenario == 1 else 5.37
    fig.add_hline(y=paper_red, line_dash="dot", line_color="#2ecc71",
                  annotation_text=f"Paper TD hedef S{scenario} ({paper_red}%)",
                  annotation_position="right")
    fig.add_hline(y=paper_net,
                  line_dash="dot", line_color="#3498db",
                  annotation_text=f"Paper net hedef S{scenario} ({paper_net}%)",
                  annotation_position="right")

    fig.update_layout(
        xaxis_title="Periyot",
        yaxis_title="Yüzde (%)",
        plot_bgcolor="white",
        height=420,
        legend=dict(x=0.02, y=0.98),
        yaxis=dict(gridcolor="#ecf0f1"),
        xaxis=dict(tickmode="linear", dtick=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Relocation kabul/ret bar ───────────────────────────────────
    st.subheader("📦 Relocation Önerileri")
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=periods,
        y=[r.num_accepted for r in results],
        name="Kabul",
        marker_color="#2ecc71",
    ))
    fig2.add_trace(go.Bar(
        x=periods,
        y=[r.num_rejected for r in results],
        name="Ret",
        marker_color="#e74c3c",
    ))
    fig2.update_layout(
        barmode="stack",
        xaxis_title="Periyot",
        yaxis_title="Öneri sayısı",
        plot_bgcolor="white",
        height=320,
        xaxis=dict(tickmode="linear", dtick=1),
        yaxis=dict(gridcolor="#ecf0f1"),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ── Paper hedefleri karşılaştırma ─────────────────────────────
    st.divider()
    st.subheader("🎯 Paper Hedefleriyle Karşılaştırma")

    targets = {
        1: {"red": 15.02, "effort": 2.79,  "net": 12.23},
        2: {"red": 7.45,  "effort": 2.08,  "net": 5.37},
    }
    t = targets[scenario]

    if valid:
        p1, p2, p3 = st.columns(3)
        p1.metric("TD Azalması",
                  f"{avg_red:.2f}%",
                  f"Paper: {t['red']}%")
        p2.metric("Relocation Effort",
                  f"{avg_effort:.2f}%",
                  f"Paper: {t['effort']}%")
        p3.metric("Net İyileşme",
                  f"{avg_net:.2f}%",
                  f"Paper: {t['net']}%")

        st.info(
            "💡 Not: Paper tam DEPSO + 50 öneri ile koşturulmuştur. "
            "Buradaki sonuçlar daha az sipariş ve daha az öneri sayısıyla elde edilmiştir. "
            "Daha büyük instance ve maks öneri=50 ile paper'a yaklaşılır."
        )

else:
    st.info("⬅️ Parametreleri ayarlayıp **9 Periyot Simülasyonunu Başlat** butonuna bas.")

    # Preview: paper sonuçları
    st.subheader("📖 Paper Referans Sonuçları")
    ref = pd.DataFrame([
        {"Senaryo": "Senaryo 1 (Yüksek dinamik)", "TD Azalması": "15.02%",
         "Relocation Effort": "2.79%", "Net İyileşme": "12.23%"},
        {"Senaryo": "Senaryo 2 (Düşük dinamik)", "TD Azalması": "7.45%",
         "Relocation Effort": "2.08%", "Net İyileşme": "5.37%"},
    ])
    st.dataframe(ref, use_container_width=True, hide_index=True)
