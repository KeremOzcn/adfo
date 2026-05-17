"""
ui/pages/4_35_Scenarios.py
===========================
Paper Appendix H — 35 Senaryo Karşılaştırması
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import json
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="35 Senaryo", page_icon="📊", layout="wide")
st.title("📊 Paper Appendix H — 35 Senaryo Karşılaştırması")
st.markdown(
    "DEPSO ve RBRS-AE algoritmalarının paper'daki **35 problem senaryosunda** "
    "kıyaslaması. Her senaryo `K_Nmaxol_Amaxol` formatında adlandırılmıştır."
)


# ── Sonuçları yükle ──────────────────────────────────────────────
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
    st.error("Sonuç bulunamadı. Önce `run_batch.py` ile tüm batch'leri çalıştırın.")
    st.code("python run_batch.py --batch 1\n...\npython run_batch.py --batch 7")
    st.stop()

# ── DataFrame oluştur ─────────────────────────────────────────────
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
        'Senaryo':        r['scenario'],
        'K (Sipariş)':   k,
        'N_maxol':        n,
        'A_maxol':        a,
        'DEPSO vs SOP':   round(depso['vs_sop_mean'], 2),
        'RBRS-AE vs SOP': round(rbrs.get('vs_sop_mean', 0), 2),
        'Paper':          paper,
        'Fark (DEPSO-Paper)': diff,
        'DEPSO Süre (s)': round(depso['mean_rt'], 2),
        'RBRS-AE Süre (s)': round(rbrs.get('mean_rt', 0), 2),
        'Durum':          '✅' if abs(diff) < 8 else '⚠️',
    })

df = pd.DataFrame(rows)

# ── Üst metrikler ─────────────────────────────────────────────────
total      = len(df)
passed     = (df['Fark (DEPSO-Paper)'].abs() < 8).sum()
avg_diff   = df['Fark (DEPSO-Paper)'].abs().mean()
max_diff   = df['Fark (DEPSO-Paper)'].abs().max()
depso_mean = df['DEPSO vs SOP'].mean()
rbrs_mean  = df['RBRS-AE vs SOP'].mean()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Toplam Senaryo", f"{total}/35")
c2.metric("Paper'a Yakın", f"{passed}/{total} ✅")
c3.metric("Ort. Sapma", f"±{avg_diff:.2f}%")
c4.metric("DEPSO Ort. vs SOP", f"{depso_mean:.2f}%")
c5.metric("RBRS-AE Ort. vs SOP", f"{rbrs_mean:.2f}%")

st.divider()

# ── Filtreler ─────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    k_filter = st.multiselect("K (Sipariş sayısı)",
                               sorted(df['K (Sipariş)'].unique()),
                               default=sorted(df['K (Sipariş)'].unique()))
with col_f2:
    n_filter = st.multiselect("N_maxol",
                               sorted(df['N_maxol'].unique()),
                               default=sorted(df['N_maxol'].unique()))
with col_f3:
    a_filter = st.multiselect("A_maxol",
                               sorted(df['A_maxol'].unique()),
                               default=sorted(df['A_maxol'].unique()))

filtered = df[
    df['K (Sipariş)'].isin(k_filter) &
    df['N_maxol'].isin(n_filter) &
    df['A_maxol'].isin(a_filter)
]

st.divider()

# ── Ana tablo ─────────────────────────────────────────────────────
st.subheader(f"📋 Sonuç Tablosu ({len(filtered)} senaryo)")
st.dataframe(
    filtered[[
        'Senaryo', 'K (Sipariş)', 'N_maxol', 'A_maxol',
        'DEPSO vs SOP', 'RBRS-AE vs SOP', 'Paper',
        'Fark (DEPSO-Paper)', 'DEPSO Süre (s)', 'RBRS-AE Süre (s)', 'Durum'
    ]].style.background_gradient(
        subset=['DEPSO vs SOP', 'RBRS-AE vs SOP'],
        cmap='RdYlGn', vmin=-95, vmax=-65
    ).background_gradient(
        subset=['Fark (DEPSO-Paper)'],
        cmap='RdYlGn_r', vmin=-5, vmax=5
    ),
    use_container_width=True,
    hide_index=True,
)

st.divider()

# ── DEPSO vs Paper scatter ─────────────────────────────────────────
st.subheader("🎯 DEPSO vs Paper Karşılaştırması")
fig1 = go.Figure()

fig1.add_trace(go.Scatter(
    x=filtered['Paper'],
    y=filtered['DEPSO vs SOP'],
    mode='markers+text',
    text=filtered['Senaryo'],
    textposition='top center',
    textfont=dict(size=9),
    marker=dict(
        size=10,
        color=filtered['Fark (DEPSO-Paper)'].abs(),
        colorscale='RdYlGn_r',
        colorbar=dict(title='|Fark|%'),
        showscale=True,
    ),
    name='DEPSO',
    hovertemplate='<b>%{text}</b><br>Paper: %{x:.2f}%<br>Bizim: %{y:.2f}%<extra></extra>',
))

# 45° ideal çizgisi
mn = min(filtered['Paper'].min(), filtered['DEPSO vs SOP'].min()) - 2
mx = max(filtered['Paper'].max(), filtered['DEPSO vs SOP'].max()) + 2
fig1.add_trace(go.Scatter(
    x=[mn, mx], y=[mn, mx],
    mode='lines',
    line=dict(dash='dash', color='gray', width=1),
    name='Mükemmel eşleşme',
    showlegend=True,
))

fig1.update_layout(
    xaxis_title="Paper DEPSO vs SOP (%)",
    yaxis_title="Bizim DEPSO vs SOP (%)",
    plot_bgcolor='white',
    height=500,
    xaxis=dict(gridcolor='#ecf0f1'),
    yaxis=dict(gridcolor='#ecf0f1'),
)
st.plotly_chart(fig1, use_container_width=True)
st.caption("Noktalar ideal çizgiye ne kadar yakınsa, paper'a o kadar yakın demektir.")

st.divider()

# ── DEPSO vs RBRS-AE bar ──────────────────────────────────────────
st.subheader("⚖️ DEPSO vs RBRS-AE — Senaryo Bazlı")

fig2 = go.Figure()
fig2.add_trace(go.Bar(
    x=filtered['Senaryo'],
    y=filtered['DEPSO vs SOP'],
    name='DEPSO vs SOP',
    marker_color='#e74c3c',
))
fig2.add_trace(go.Bar(
    x=filtered['Senaryo'],
    y=filtered['RBRS-AE vs SOP'],
    name='RBRS-AE vs SOP',
    marker_color='#3498db',
))
fig2.add_trace(go.Scatter(
    x=filtered['Senaryo'],
    y=filtered['Paper'],
    name='Paper (hedef)',
    mode='markers',
    marker=dict(symbol='diamond', size=8, color='black'),
))
fig2.update_layout(
    barmode='group',
    xaxis_title='Senaryo',
    yaxis_title='vs SOP (%)',
    plot_bgcolor='white',
    height=450,
    xaxis=dict(tickangle=-45, gridcolor='#ecf0f1'),
    yaxis=dict(gridcolor='#ecf0f1'),
    legend=dict(x=0.01, y=0.01),
)
st.plotly_chart(fig2, use_container_width=True)

st.divider()

# ── Süre karşılaştırması ──────────────────────────────────────────
st.subheader("⏱️ Runtime Karşılaştırması")
fig3 = go.Figure()
fig3.add_trace(go.Bar(
    x=filtered['Senaryo'],
    y=filtered['DEPSO Süre (s)'],
    name='DEPSO',
    marker_color='#e74c3c',
))
fig3.add_trace(go.Bar(
    x=filtered['Senaryo'],
    y=filtered['RBRS-AE Süre (s)'],
    name='RBRS-AE',
    marker_color='#3498db',
))
fig3.update_layout(
    barmode='group',
    xaxis_title='Senaryo',
    yaxis_title='Ortalama Süre (saniye)',
    plot_bgcolor='white',
    height=380,
    xaxis=dict(tickangle=-45, gridcolor='#ecf0f1'),
    yaxis=dict(gridcolor='#ecf0f1'),
)
st.plotly_chart(fig3, use_container_width=True)

# ── Özet istatistik ───────────────────────────────────────────────
st.divider()
st.subheader("📈 Özet İstatistik")

speedup = filtered['DEPSO Süre (s)'].mean() / max(filtered['RBRS-AE Süre (s)'].mean(), 0.01)
td_diff = ((filtered['RBRS-AE vs SOP'] - filtered['DEPSO vs SOP'])).mean()

col1, col2, col3 = st.columns(3)
col1.metric("Ortalama Fark (DEPSO - Paper)", f"{avg_diff:.2f}%", "±%8 kabul edilebilir")
col2.metric("RBRS-AE vs DEPSO (TD fark)", f"{td_diff:+.2f}%", "Pozitif = DEPSO daha iyi")
col3.metric("RBRS-AE hız avantajı", f"{speedup:.1f}x", "Daha hızlı")
