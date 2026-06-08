# Çoklu Instance Deney Raporu

## Deney Konfigürasyonu

| Parametre | Değer |
|---|---|
| Instance sayısı | 10 |
| Sipariş / instance | 30 |
| Senaryo | 1 |
| DEPSO iterasyon | 100 |
| RBRS-AE iterasyon | 100 |

## Sonuçlar

| Algoritma | Ort TD (LU) | Std | Min | Max | Ort Süre | vs SOP | vs FCFS |
|---|---|---|---|---|---|---|---|
| **SOP** | 2999.1 | 337.1 | 2425.0 | 3597.0 | 0.00s | — | +247.5% |
| **FCFS** | 876.6 | 142.8 | 714.0 | 1071.0 | 0.00s | -70.7% | — |
| **DEPSO** | 552.1 | 40.9 | 500.0 | 627.0 | 3.89s | -81.4% | -36.0% |
| **RBRS-AE** | 566.5 | 49.1 | 508.0 | 646.0 | 0.72s | -80.9% | -34.4% |

> Note: vs SOP / vs FCFS are the mean of per-instance percentage differences, not the ratio of the mean TDs. The two differ when instance sizes vary.

## Paper Hedefleriyle Karşılaştırma

| Metrik | Gerçekleşen | Paper Hedefi | Durum |
|---|---|---|---|
| DEPSO vs SOP  | -81.44% | ~-88% | ✅ |
| DEPSO vs FCFS | -35.99% | ~-40% | ✅ |

## DEPSO vs RBRS-AE

| Metrik | Değer |
|---|---|
| TD farkı | +2.61% |
| Hız farkı | RBRS-AE 5.4x hızlı |
| RBRS-AE ort TD | 566.5 LU |
| DEPSO ort TD | 552.1 LU |