"""
ui/app.py  —  Ana sayfa
Çalıştır: streamlit run ui/app.py
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

# ── Başlık ────────────────────────────────────────────────────────
st.title("📦 Warehouse Optimization")
st.markdown(
    "**Paper:** Kübler, Glock, Bauernhansl (2020) · "
    "*Computers & Industrial Engineering 147, 106645*"
)
st.divider()

# ── İki kolon: açıklama + metrikler ──────────────────────────────
col_left, col_right = st.columns([3, 1])

with col_left:
    st.subheader("Proje Özeti")
    st.markdown("""
Bu uygulama, bir **picker-to-parts manuel depo** ortamında üç problemi birlikte çözer:

- **Order Batching** — siparişleri grupla, picker daha az yol yürüsün
- **Picker Routing** — her batch için en kısa tur
- **Dynamic Storage Assignment** — ürünleri doğru rafta tut

İki algoritma karşılaştırılmaktadır:

| Algoritma | Yöntem | Avantaj |
|---|---|---|
| **DEPSO** | Discrete PSO (paper) | Yüksek kalite, iyi arama |
| **RBRS-AE** | Regret Search + LNS (yeni) | Hızlı, deterministik yakınsama |

**Menüden:**
- 🎯 **Tek Koşu** — bir algoritmayı çalıştır, rota görselleştir
- ⚖️ **Karşılaştırma** — 4 algoritmayı yan yana koştur
""")

with col_right:
    st.subheader("Dataset")
    st.metric("Lokasyon", f"{wh.total_locations:,}")
    st.metric("Ürün", "6,000")
    st.metric("Senaryo", "2")
    st.metric("Test periyodu", "9 × 20 alt-periyot")
    st.metric("Picker kapasitesi", "100 WU")

st.divider()

# ── Depo görselleştirme ───────────────────────────────────────────
st.subheader("Depo Düzeni")
st.caption(
    f"{wh.num_aisles} picking aisle · {wh.num_blocks} blok · "
    f"{wh.total_locations:,} lokasyon · "
    f"Depot: ({wh.depot_x:.0f}, {wh.depot_y:.0f}) LU"
)

show_cls = st.checkbox("ABC sınıf lokasyonlarını göster (örnek)",
                       help="A=kırmızı (depot'a yakın), B=turuncu, C=mavi")

fig = plot_warehouse_layout(wh, show_class_locations=show_cls)
st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Gri bloklar rafları temsil eder. "
    "Yatay boşluklar cross aisle (geçiş koridoru). "
    "Depot sağ altta (siyah kare)."
)

# ── Paper sonuçları (referans) ────────────────────────────────────
st.divider()
st.subheader("Doğrulama Sonuçları (50 sipariş, Senaryo 1)")
r1, r2, r3, r4 = st.columns(4)
r1.metric("SOP",     "1,384 LU", "baseline")
r2.metric("FCFS",    "187 LU",   "-86%")
r3.metric("RBRS-AE", "157 LU",   "-89%")
r4.metric("DEPSO",   "139 LU",   "-90% (paper hedef -88%)")
