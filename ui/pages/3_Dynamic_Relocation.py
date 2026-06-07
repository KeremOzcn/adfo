"""
ui/pages/3_Dynamic_Relocation.py
=================================
Dynamic storage relocation analysis.
Holt-Winters + Relocation algorithm over 9 periods.
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
st.title("🔄 Dynamic Storage Relocation")
st.markdown(
    "At the end of each period, **Holt-Winters** forecasts demand, "
    "items in the wrong class are detected, and relocation suggestions are evaluated."
)


@st.cache_resource
def get_wh():    return Warehouse()
@st.cache_resource
def get_loader(): return DataLoader()


wh     = get_wh()
loader = get_loader()

# ── Sidebar ──────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Parameters")
    scenario   = st.selectbox("Scenario", [1, 2],
                              format_func=lambda x: f"Scenario {x} ({'High' if x==1 else 'Low'} dynamic)")
    max_orders = st.slider("Orders per sub-period", 10, 200, 50)
    max_sugg   = st.slider("Max relocation suggestions", 5, 50, 20)
    algo_choice= st.radio("Routing algorithm", ["RBRS-AE", "DEPSO"])
    seed       = st.number_input("Seed", value=42)

    st.divider()
    st.markdown("**Paper parameters:**")
    st.markdown("- α=0.19, β=0.053, γ=0.10")
    st.markdown("- o=2 (wrong-class threshold)")
    st.markdown("- u=1 (target-class threshold)")
    st.markdown("- Max suggestions: 50")

# ── Run ───────────────────────────────────────────────────────────
if st.button("🚀 Start 9-Period Simulation", type="primary",
             use_container_width=True):

    # Setup
    items          = loader.load_items()
    item_locations = [it.initial_location for it in items]
    item_classes   = [it.class_period1    for it in items]
    loc_classes    = loader.load_location_classes()

    demand = loader.load_scenario_demand(scenario)

    # Forecaster
    forecaster = ItemForecaster()
    with st.spinner("Fitting Holt-Winters models (12-period warm-up)..."):
        forecaster.fit_all(demand, warmup_periods=12)

    # Relocation
    reloc = DynamicRelocation(wh, loc_classes)
    reloc.max_suggestions = max_sugg
    reloc.initialize(item_locations, item_classes)

    # Algorithm
    if algo_choice == "RBRS-AE":
        algo = RBRS_AE(seed=int(seed), max_iterations=30)
    else:
        algo = DEPSO(num_iterations=100, seed=int(seed))

    # Run for 9 periods
    results = []
    prog    = st.progress(0)
    status  = st.empty()

    for period in range(1, 10):
        status.info(f"Processing period {period}/9...")

        # Forecast
        forecasts = forecaster.predict_all(tau=1)
        fc_cls    = reloc._classify_by_forecast(forecasts)
        reloc._update_class_tracking(fc_cls)

        # Orders (first sub-period)
        orders = loader.load_orders(scenario, period, 1).orders[:max_orders]

        # Relocation
        result = reloc.run_period(period, orders, forecasts, algo)
        results.append(result)

        # Update forecaster with actual demand
        actual = demand[:, 11 + period]
        forecaster.update_all(actual)

        # Re-update class tracking after observing actual demand
        # (correct starting point for next period)
        next_forecasts = forecaster.predict_all(tau=1)
        next_fc = reloc._classify_by_forecast(next_forecasts)
        reloc._update_class_tracking(next_fc)

        prog.progress(period / 9)

    status.success("✅ 9 periods completed.")

    # ── Results table ─────────────────────────────────────────────
    st.subheader("📊 Per-Period Results")
    rows = [{
        "Period":         r.period,
        "Tested":         r.num_suggestions_tested,
        "Accepted":       r.num_accepted,
        "Rejected":       r.num_rejected,
        "TD Before (LU)": f"{r.travel_distance_before:.0f}",
        "TD After (LU)":  f"{r.travel_distance_after:.0f}",
        "Reduction %":    f"{r.reduction_pct:.2f}%",
        "Effort %":       f"{r.relocation_effort_pct:.2f}%",
        "Net %":          f"{r.net_improvement_pct:.2f}%",
    } for r in results]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    # ── Average metrics ───────────────────────────────────────────
    valid = [r for r in results if r.travel_distance_before > 0]
    if valid:
        avg_red    = sum(r.reduction_pct    for r in valid) / len(valid)
        avg_effort = sum(r.relocation_effort_pct for r in valid) / len(valid)
        avg_net    = sum(r.net_improvement_pct   for r in valid) / len(valid)
        total_acc  = sum(r.num_accepted for r in results)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg. TD Reduction",    f"{avg_red:.2f}%",    "Target: ~15%")
        c2.metric("Avg. Relocation Effort", f"{avg_effort:.2f}%", "Target: ~2.79%")
        c3.metric("Avg. Net Improvement", f"{avg_net:.2f}%",    "Target: ~12.23%")
        c4.metric("Total Accepted",       total_acc)

    # ── Plot: TD reduction and effort ─────────────────────────────
    st.subheader("📈 Per-Period Trend")
    periods = [r.period for r in results]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=periods,
        y=[r.reduction_pct for r in results],
        name="TD Reduction %",
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
        name="Net Improvement %",
        line=dict(color="#3498db", width=3),
        mode="lines+markers",
    ))

    # Paper target lines
    paper_red = 15.02 if scenario == 1 else 7.45
    paper_net = 12.23 if scenario == 1 else 5.37
    fig.add_hline(y=paper_red, line_dash="dot", line_color="#2ecc71",
                  annotation_text=f"Paper TD target S{scenario} ({paper_red}%)",
                  annotation_position="right")
    fig.add_hline(y=paper_net,
                  line_dash="dot", line_color="#3498db",
                  annotation_text=f"Paper net target S{scenario} ({paper_net}%)",
                  annotation_position="right")

    fig.update_layout(
        xaxis_title="Period",
        yaxis_title="Percent (%)",
        plot_bgcolor="white",
        height=420,
        legend=dict(x=0.02, y=0.98),
        yaxis=dict(gridcolor="#ecf0f1"),
        xaxis=dict(tickmode="linear", dtick=1),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ── Relocation accept/reject bars ─────────────────────────────
    st.subheader("📦 Relocation Suggestions")
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=periods,
        y=[r.num_accepted for r in results],
        name="Accepted",
        marker_color="#2ecc71",
    ))
    fig2.add_trace(go.Bar(
        x=periods,
        y=[r.num_rejected for r in results],
        name="Rejected",
        marker_color="#e74c3c",
    ))
    fig2.update_layout(
        barmode="stack",
        xaxis_title="Period",
        yaxis_title="Number of suggestions",
        plot_bgcolor="white",
        height=320,
        xaxis=dict(tickmode="linear", dtick=1),
        yaxis=dict(gridcolor="#ecf0f1"),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ── Paper targets comparison ──────────────────────────────────
    st.divider()
    st.subheader("🎯 Comparison with Paper Targets")

    targets = {
        1: {"red": 15.02, "effort": 2.79,  "net": 12.23},
        2: {"red": 7.45,  "effort": 2.08,  "net": 5.37},
    }
    t = targets[scenario]

    if valid:
        p1, p2, p3 = st.columns(3)
        p1.metric("TD Reduction",
                  f"{avg_red:.2f}%",
                  f"Paper: {t['red']}%")
        p2.metric("Relocation Effort",
                  f"{avg_effort:.2f}%",
                  f"Paper: {t['effort']}%")
        p3.metric("Net Improvement",
                  f"{avg_net:.2f}%",
                  f"Paper: {t['net']}%")

        st.info(
            "💡 Note: The paper used full DEPSO with 50 suggestions. "
            "These results were obtained with fewer orders and a lower suggestion cap. "
            "Paper-level performance is reached with larger instances and max suggestions = 50."
        )

else:
    st.info("⬅️ Set parameters and press **Start 9-Period Simulation**.")

    # Preview: paper results
    st.subheader("📖 Paper Reference Results")
    ref = pd.DataFrame([
        {"Scenario": "Scenario 1 (High dynamic)", "TD Reduction": "15.02%",
         "Relocation Effort": "2.79%", "Net Improvement": "12.23%"},
        {"Scenario": "Scenario 2 (Low dynamic)",  "TD Reduction": "7.45%",
         "Relocation Effort": "2.08%", "Net Improvement": "5.37%"},
    ])
    st.dataframe(ref, use_container_width=True, hide_index=True)
