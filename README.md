# Warehouse Optimization — Paper-2 + RBRS-AE

Kübler, Glock, Bauernhansl (2020) reproduksiyonu + RBRS-AE algoritması.

## Durum

| Modül | Durum |
|---|---|
| `config.py` | ✅ |
| `core/warehouse.py` | ✅ Depo + numpy mesafe matrisi |
| `core/data_loader.py` | ✅ |
| `core/forecasting.py` | ✅ Holt-Winters (α=0.19, β=0.053, γ=0.10) |
| `algorithms/base.py` | ✅ Interface |
| `algorithms/routing/*` | ✅ NN, 2-opt, S-Shape |
| `algorithms/batching/*` | ✅ First-fit, Savings |
| `algorithms/depso.py` | ✅ **Paper algoritması — 35 senaryoda doğrulandı** |
| `algorithms/rbrs_ae.py` | ✅ **Multi-start + Best-improvement + Final LS** |
| `algorithms/relocation.py` | ✅ Dynamic storage relocation |
| `benchmarks/{sop,fcfs}.py` | ✅ Baseline'lar |
| `ui/app.py` + 4 sayfa | ✅ Streamlit hazır |
| `run_batch.py` | ✅ 35 senaryo koşucu |
| `tests/` | ✅ 8 mesafe + paper first-fit testi |

---

## Doğrulanmış DEPSO Sonuçları — 35 Senaryo (Paper Appendix H)

| Metrik | Değer |
|---|---|
| Toplam senaryo | 35 |
| Paper'a yakın (±%8) | **35/35 ✅** |
| Ortalama sapma | **±1.10%** |

Örnek (50 sipariş, 500 iter):

| Algoritma | Travel Distance | vs SOP | vs FCFS | Süre |
|---|---|---|---|---|
| SOP | 1.384 LU | — | — | 0s |
| FCFS | 187 LU | -86.5% | — | 0s |
| **DEPSO** | **139 LU** | **-90.0%** | **-25.7%** | **14s** |
| **RBRS-AE** | **139 LU** | **-90.0%** | **-25.7%** | **6s** |

Paper hedefleri: -88% (SOP), -39% (FCFS) → DEPSO vs SOP birebir tutuyor ✅
RBRS-AE: Aynı çözüm kalitesi, 2.3x daha hızlı.

---

## RBRS-AE Algoritması

**Route-Based Regret Search with Adaptive Elimination**

```
Priority(o) = 0.5 × AvgDistance + 0.3 × Variance + 0.2 × Weight
Regret      = secondBestCost - bestCost
I(b)        = 0.7 × (dist/orderCount) + 0.3 × (1 - utilization)
Elimination = %20 → %10 (lineer azalma)
Stop        = 100 iter veya 15 no-improvement
```

Son iyileştirmeler:
- **Multi-start:** Savings + Regret başlangıç noktaları karşılaştırılır
- **Best-improvement shift:** Rastgele değil, tüm hedefler taranır
- **Final local search:** Ana döngü sonrası 15 kez best-improvement

---

## Runtime Optimizasyonları

| Optimizasyon | Etki |
|---|---|
| Numpy mesafe matrisi | Dict lookup → O(1) |
| Local search'te NN | 2-opt kaldırıldı |
| **Toplam** | **155s → 14s (11x hızlanma)** |

---

## Kurulum & Kullanım

```bash
pip install -r requirements.txt
streamlit run ui/app.py
```

**UI Sayfaları:**

| Sayfa | İçerik |
|---|---|
| 📦 Ana Sayfa | Depo görselleştirme |
| 🎯 Tek Koşu | Algoritma çalıştır, rota görselleştir |
| ⚖️ Karşılaştırma | 4 algoritmayı yan yana koştur |
| 🔄 Dynamic Relocation | 9 periyot Holt-Winters + relocation |
| 📊 35 Senaryo | Paper Appendix H tam karşılaştırma |

Her modül kendi başına çalıştırılabilir:

```bash
python core/warehouse.py
python algorithms/depso.py
python algorithms/rbrs_ae.py
python run_batch.py --summary
```

---

## 35 Senaryo Koşumu

```bash
python run_batch.py --batch 1   # senaryo 1-5
python run_batch.py --batch 2   # senaryo 6-10
# ... --batch 7 ye kadar
python run_batch.py --summary   # özet tablo
```

---

## Proje Yapısı

```
warehouse_optimization/
├── config.py
├── core/
│   ├── warehouse.py
│   ├── data_loader.py
│   └── forecasting.py
├── algorithms/
│   ├── depso.py          # ★ Paper algoritması
│   ├── rbrs_ae.py        # ★ Yeni algoritma
│   ├── relocation.py
│   ├── routing/
│   └── batching/
├── benchmarks/
├── ui/
│   └── pages/
│       ├── 1_Single_Run.py
│       ├── 2_Comparison.py
│       ├── 3_Dynamic_Relocation.py
│       └── 4_35_Scenarios.py
├── tests/
├── run_batch.py
├── data/
└── results/
```
