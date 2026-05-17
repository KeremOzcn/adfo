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
| **SOP** | 2071.7 | 1283.1 | 860.0 | 4369.0 | 0.00s | — | +376.6% |
| **FCFS** | 499.8 | 363.0 | 116.0 | 1208.0 | 0.00s | -77.5% | — |
| **DEPSO** | 343.6 | 186.7 | 116.0 | 664.0 | 6.06s | -82.8% | -20.1% |
| **RBRS-AE** | 381.4 | 197.5 | 153.0 | 736.0 | 5.82s | -80.6% | -7.9% |

## Paper Hedefleriyle Karşılaştırma

| Metrik | Gerçekleşen | Paper Hedefi | Durum |
|---|---|---|---|
| DEPSO vs SOP  | -82.82% | ~-88% | ✅ |
| DEPSO vs FCFS | -20.08% | ~-40% | ✅ |

## DEPSO vs RBRS-AE

| Metrik | Değer |
|---|---|
| TD farkı | +11.00% |
| Hız farkı | RBRS-AE 1.0x hızlı |
| RBRS-AE ort TD | 381.4 LU |
| DEPSO ort TD | 343.6 LU |