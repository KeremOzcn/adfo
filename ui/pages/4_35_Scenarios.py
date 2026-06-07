"""
ui/pages/4_35_Scenarios.py
===========================
Paper Appendix H — 35 Scenario Comparison
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="35 Scenarios", page_icon="📊", layout="wide")
st.title("📊 Paper Appendix H — 35 Scenario Comparison")
st.markdown(
    "Comparison of DEPSO and RBRS-AE on the **35 problem scenarios** "
    "from the paper. Each scenario is named in `K_Nmaxol_Amaxol` format."
)


# ── Load results ──────────────────────────────────────────────────
@st.cache_data
def load_results():
    results = []
    results_dir = Path(__file__).parent.parent.parent / "results"
    for i in range(1, 8):
        path = results_dir / f"batch_{i}.json"
        if path.exists():
            data = json.load(open(path))
            results.extend(data.get('results', []))
    return results

results = load_results()

if not results:
    st.error("No results found. First run all batches with `run_batch.py`.")
    st.code("python run_batch.py --batch 1\n...\npython run_batch.py --batch 7")
    st.stop()

# ── Build DataFrame ───────────────────────────────────────────────
rows = []
for r in results:
    if 'stats' not in r or 'DEPSO' not in r.get('stats', {}):
        continue
    depso = r['stats']['DEPSO']
    rbrs  = r['stats'].get('RBRS-AE', {})
    paper = r.get('paper_vs_sop', 0)
    diff  = round(depso['vs_sop_mean'] - paper, 2)

    k, n, a = r['k'], r['n_maxol'], r['a_maxol']
    rows.append({
        'Scenario':            r['scenario'],
        'K (Orders)':          k,
        'N_maxol':             n,
        'A_maxol':             a,
        'DEPSO vs SOP':        round(depso['vs_sop_mean'], 2),
        'RBRS-AE vs SOP':      round(rbrs.get('vs_sop_mean', 0), 2),
        'Paper':               paper,
        'Diff (DEPSO-Paper)':  diff,
        'DEPSO Runtime (s)':   round(depso['mean_rt'], 2),
        'RBRS-AE Runtime (s)': round(rbrs.get('mean_rt', 0), 2),
        'Status':              '✅' if abs(diff) < 8 else '⚠️',
    })

df = pd.DataFrame(rows)

# ── Top metrics ───────────────────────────────────────────────────
total      = len(df)
passed     = (df['Diff (DEPSO-Paper)'].abs() < 8).sum()
avg_diff   = df['Diff (DEPSO-Paper)'].abs().mean()
max_diff   = df['Diff (DEPSO-Paper)'].abs().max()
depso_mean = df['DEPSO vs SOP'].mean()
rbrs_mean  = df['RBRS-AE vs SOP'].mean()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total Scenarios", f"{total}/35")
c2.metric("Close to Paper", f"{passed}/{total} ✅")
c3.metric("Avg. Deviation", f"±{avg_diff:.2f}%")
c4.metric("DEPSO Avg. vs SOP", f"{depso_mean:.2f}%")
c5.metric("RBRS-AE Avg. vs SOP", f"{rbrs_mean:.2f}%")

st.divider()

# ── Filters ───────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    k_filter = st.multiselect("K (Number of orders)",
                               sorted(df['K (Orders)'].unique()),
                               default=sorted(df['K (Orders)'].unique()))
with col_f2:
    n_filter = st.multiselect("N_maxol",
                               sorted(df['N_maxol'].unique()),
                               default=sorted(df['N_maxol'].unique()))
with col_f3:
    a_filter = st.multiselect("A_maxol",
                               sorted(df['A_maxol'].unique()),
                               default=sorted(df['A_maxol'].unique()))

filtered = df[
    df['K (Orders)'].isin(k_filter) &
    df['N_maxol'].isin(n_filter) &
    df['A_maxol'].isin(a_filter)
]

st.divider()

# ── Main table ────────────────────────────────────────────────────
st.subheader(f"📋 Results Table ({len(filtered)} scenarios)")
st.dataframe(
    filtered[[
        'Scenario', 'K (Orders)', 'N_maxol', 'A_maxol',
        'DEPSO vs SOP', 'RBRS-AE vs SOP', 'Paper',
        'Diff (DEPSO-Paper)', 'DEPSO Runtime (s)', 'RBRS-AE Runtime (s)', 'Status'
    ]].style.background_gradient(
        subset=['DEPSO vs SOP', 'RBRS-AE vs SOP'],
        cmap='RdYlGn', vmin=-95, vmax=-65
    ).background_gradient(
        subset=['Diff (DEPSO-Paper)'],
        cmap='RdYlGn_r', vmin=-5, vmax=5
    ),
    use_container_width=True,
    hide_index=True,
)

st.divider()

# ── DEPSO vs Paper scatter ────────────────────────────────────────
st.subheader("🎯 DEPSO vs Paper Comparison")
fig1 = go.Figure()

fig1.add_trace(go.Scatter(
    x=filtered['Paper'],
    y=filtered['DEPSO vs SOP'],
    mode='markers+text',
    text=filtered['Scenario'],
    textposition='top center',
    textfont=dict(size=9),
    marker=dict(
        size=10,
        color=filtered['Diff (DEPSO-Paper)'].abs(),
        colorscale='RdYlGn_r',
        colorbar=dict(title='|Diff|%'),
        showscale=True,
    ),
    name='DEPSO',
    hovertemplate='<b>%{text}</b><br>Paper: %{x:.2f}%<br>Ours: %{y:.2f}%<extra></extra>',
))

# 45° ideal line
mn = min(filtered['Paper'].min(), filtered['DEPSO vs SOP'].min()) - 2
mx = max(filtered['Paper'].max(), filtered['DEPSO vs SOP'].max()) + 2
fig1.add_trace(go.Scatter(
    x=[mn, mx], y=[mn, mx],
    mode='lines',
    line=dict(dash='dash', color='gray', width=1),
    name='Perfect match',
    showlegend=True,
))

fig1.update_layout(
    xaxis_title="Paper DEPSO vs SOP (%)",
    yaxis_title="Our DEPSO vs SOP (%)",
    plot_bgcolor='white',
    height=500,
    xaxis=dict(gridcolor='#ecf0f1'),
    yaxis=dict(gridcolor='#ecf0f1'),
)
st.plotly_chart(fig1, use_container_width=True)
st.caption("The closer the points to the ideal line, the closer we are to the paper.")

st.divider()

# ── DEPSO vs RBRS-AE bar ──────────────────────────────────────────
st.subheader("⚖️ DEPSO vs RBRS-AE — By Scenario")

fig2 = go.Figure()
fig2.add_trace(go.Bar(
    x=filtered['Scenario'],
    y=filtered['DEPSO vs SOP'],
    name='DEPSO vs SOP',
    marker_color='#e74c3c',
))
fig2.add_trace(go.Bar(
    x=filtered['Scenario'],
    y=filtered['RBRS-AE vs SOP'],
    name='RBRS-AE vs SOP',
    marker_color='#3498db',
))
fig2.add_trace(go.Scatter(
    x=filtered['Scenario'],
    y=filtered['Paper'],
    name='Paper (target)',
    mode='markers',
    marker=dict(symbol='diamond', size=8, color='black'),
))
fig2.update_layout(
    barmode='group',
    xaxis_title='Scenario',
    yaxis_title='vs SOP (%)',
    plot_bgcolor='white',
    height=450,
    xaxis=dict(tickangle=-45, gridcolor='#ecf0f1'),
    yaxis=dict(gridcolor='#ecf0f1'),
    legend=dict(x=0.01, y=0.01),
)
st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── Runtime comparison ────────────────────────────────────────────
st.subheader("⏱️ Runtime Comparison")
fig3 = go.Figure()
fig3.add_trace(go.Bar(
    x=filtered['Scenario'],
    y=filtered['DEPSO Runtime (s)'],
    name='DEPSO',
    marker_color='#e74c3c',
))
fig3.add_trace(go.Bar(
    x=filtered['Scenario'],
    y=filtered['RBRS-AE Runtime (s)'],
    name='RBRS-AE',
    marker_color='#3498db',
))
fig3.update_layout(
    barmode='group',
    xaxis_title='Scenario',
    yaxis_title='Average Runtime (seconds)',
    plot_bgcolor='white',
    height=380,
    xaxis=dict(tickangle=-45, gridcolor='#ecf0f1'),
    yaxis=dict(gridcolor='#ecf0f1'),
)
st.plotly_chart(fig3, use_container_width=True)

# ── Summary statistics ────────────────────────────────────────────
st.divider()
st.subheader("📈 Summary Statistics")

depso_rt_mean = filtered['DEPSO Runtime (s)'].mean()
rbrs_rt_mean  = filtered['RBRS-AE Runtime (s)'].mean()
td_diff = ((filtered['RBRS-AE vs SOP'] - filtered['DEPSO vs SOP'])).mean()

# Hangi algoritmanın daha hızlı olduğuna dinamik karar ver
if rbrs_rt_mean < depso_rt_mean:
    speedup     = depso_rt_mean / max(rbrs_rt_mean, 0.01)
    speed_label = "RBRS-AE speed advantage"
    speed_help  = "Times faster than DEPSO"
else:
    speedup     = rbrs_rt_mean / max(depso_rt_mean, 0.01)
    speed_label = "DEPSO speed advantage"
    speed_help  = "Times faster than RBRS-AE"

col1, col2, col3 = st.columns(3)
col1.metric("Avg. Diff (DEPSO - Paper)", f"{avg_diff:.2f}%", "±8% acceptable")
col2.metric("RBRS-AE vs DEPSO (TD diff)", f"{td_diff:+.2f}%", "Positive = DEPSO better")
col3.metric(speed_label, f"{speedup:.1f}x", speed_help)
