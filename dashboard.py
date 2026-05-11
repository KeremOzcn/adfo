from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
TARGET = ROOT / "bin" / "app"


st.set_page_config(page_title="DEPSO Dashboard", layout="wide")


def load_summary() -> list[dict]:
    summary_file = RESULTS_DIR / "summary_full.json"
    if summary_file.exists():
        return json.loads(summary_file.read_text(encoding="utf-8"))
    return []


def load_results_csv() -> pd.DataFrame:
    csv_files = sorted(RESULTS_DIR.glob("benchmark_results_*.csv"))
    if not csv_files:
        return pd.DataFrame()
    frames = [pd.read_csv(path) for path in csv_files]
    return pd.concat(frames, ignore_index=True)


def run_c_demo() -> tuple[int, str]:
    if not TARGET.exists():
        build = subprocess.run(["make"], cwd=ROOT, capture_output=True, text=True)
        if build.returncode != 0:
            return build.returncode, build.stdout + build.stderr

    completed = subprocess.run([str(TARGET)], cwd=ROOT, capture_output=True, text=True)
    return completed.returncode, completed.stdout + completed.stderr


st.title("DEPSO / RBRS-AE Dashboard")
st.caption("C demosunu çalıştırır ve mevcut benchmark sonuçlarını görselleştirir.")

summary = load_summary()
results = load_results_csv()

col_a, col_b, col_c = st.columns(3)
col_a.metric("Senaryo sayısı", len(summary) or results["scenario_id"].nunique() if not results.empty else 0)
col_b.metric("Sonuç dosyası", "summary_full.json" if summary else "Yok")
col_c.metric("C ikilisi", "bin/app" if TARGET.exists() else "Derlenmemiş")

st.divider()

tab_home, tab_compare, tab_results, tab_details = st.tabs(
    ["Ana Sayfa", "Algoritma Karşılaştırması", "Benchmark Sonuçları", "Algoritma Detayları"]
)


with tab_home:
    st.subheader("Programı çalıştır")
    st.write("Aşağıdaki buton C programını derler, sonra `bin/app` çıktısını gösterir.")
    if st.button("C demo çalıştır", type="primary"):
        code, output = run_c_demo()
        if code == 0:
            st.success("C demo başarıyla çalıştı")
        else:
            st.error(f"C demo hata kodu: {code}")
        st.code(output or "Çıktı yok", language="text")

    st.subheader("Ne yapıyor?")
    st.markdown(
        """
        Bu proje depo içi sipariş gruplama ve rotalama için DEPSO ve RBRS-AE benzeri çözümleri karşılaştırır.
        C tarafında şu an bir demo akışı var: depo oluşturma, örnek instance üretimi ve algoritmayı çalıştırıp
        en iyi skoru yazdırma.
        """
    )


with tab_compare:
    st.subheader("Özet karşılaştırma")
    if summary:
        summary_df = pd.DataFrame(summary)
        st.dataframe(
            summary_df[
                [
                    "scenario_id",
                    "sop_mean",
                    "fcfs_mean",
                    "depso_mean",
                    "rbrs_mean",
                    "rbrs_vs_depso_mean_pct",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("summary_full.json bulunamadı.")


with tab_results:
    st.subheader("Benchmark sonuçları")
    if results.empty:
        st.info("results/ altında benchmark_results_*.csv bulunamadı.")
    else:
        scenarios = sorted(results["scenario_id"].unique())
        selected = st.selectbox("Senaryo seç", scenarios)
        filtered = results[results["scenario_id"] == selected].copy()
        st.dataframe(filtered, use_container_width=True, hide_index=True)

        metric_cols = ["sop_distance", "fcfs_distance", "depso_distance", "rbrs_distance"]
        if all(col in filtered.columns for col in metric_cols):
            chart_df = filtered[["seed", *metric_cols]].set_index("seed")
            st.bar_chart(chart_df)

        figure = FIGURES_DIR / f"convergence_{selected}.png"
        if figure.exists():
            st.image(str(figure), caption=f"Convergence: {selected}", use_container_width=True)


with tab_details:
    st.subheader("Algoritma detayları")
    st.markdown(
        """
        - **DEPSO**: permütasyon uzayında particle tabanlı arama yapar.
        - **RBRS-AE**: regret temelli yerleştirme ve adaptif iyileştirme uygular.
        - **SOP / FCFS**: karşılaştırma için referans baz çizgileri.
        """
    )
    if FIGURES_DIR.exists():
        available = sorted(FIGURES_DIR.glob("*.png"))
        if available:
            choice = st.selectbox("Grafik seç", [path.name for path in available])
            st.image(str(FIGURES_DIR / choice), use_container_width=True)