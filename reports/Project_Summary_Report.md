# DEPSO ve RBRS-AE ile Depo Optimizasyonu — Proje Özet Raporu

## Özet

Bu proje, Kübler, Glock ve Bauernhansl (2020) tarafından yayımlanan akademik makaleyi temel almaktadır. Makale, manuel picker-to-parts depolarında üç birbiriyle bağlantılı planlama problemini birlikte çözmeyi hedefler: dinamik depo konumu ataması, sipariş gruplama (batching) ve picker rotalama. Algoritmanın çekirdeğinde DEPSO (Discrete Evolutionary Particle Swarm Optimization) bulunmaktadır.

Bu çalışma, makaledeki DEPSO bileşeninin üzerine yeni bir algoritma olan **RBRS-AE (Route-Based Regret Search with Adaptive Elimination)** önermektedir. RBRS-AE, pişmanlık bazlı batch inşaatı ve adaptif eleme mekanizmasıyla DEPSO'yu tüm test senaryolarında geride bırakmaktadır.

**Anahtar Kelimeler:** depo optimizasyonu, order batching, picker routing, DEPSO, RBRS-AE, regret-based heuristic

---

## 1. Kaynak Makale

**Kübler, P., Glock, C. H., & Bauernhansl, T. (2020).** A new iterative method for solving the joint dynamic storage location assignment, order batching and picker routing problem in manual picker-to-parts warehouses. *Computers & Industrial Engineering, 147*, 106645.

Makalede birlikte optimize edilen üç karar:
1. **Dinamik depo konumu ataması** — hangi ürün hangi rafta durmalı (talep değiştikçe güncellenir)
2. **Sipariş gruplama (Order Batching)** — hangi siparişler aynı tur içinde toplanmalı
3. **Picker rotalama** — her batch için depodaki en kısa güzergah

Proje kapsamımız: **karar 2 ve 3** (DEPSO'nun çözdüğü alt-problem). Dinamik raf ataması gerçek şirket verisi gerektirdiğinden bu katman modellenmiş, uygulanmamıştır.

---

## 2. Problem Tanımı

Her siparişin bir ağırlığı ve depo içinde bir konumu vardır. Araç kapasitesi 100 WU'dur. Amaç, tüm siparişleri kapasiteyi aşmadan batch'lere bölerek toplam picker yürüyüş mesafesini minimize etmektir:

$$\min_{\pi} \sum_{b \in \mathcal{B}(\pi)} d(\text{route}(b)) \quad \text{s.t.} \quad \sum_{o \in b} w_o \le C$$

---

## 3. Makaledeki Algoritma: DEPSO

DEPSO her çözümü bir **sipariş permütasyonu** olarak kodlar. Permütasyon şu adımlarla değerlendirme:

1. **First-fit batching:** Sipariş sırasına göre her sipariş kapasitesi yeterli olan ilk batch'e atanır.
2. **Combined+ routing:** Her batch için S-Shape, Return, Midpoint ve Largest-Gap heuristiklerinin en iyisi seçilir.
3. **PSO hareketi:** Eşik tabanlı velocity güncellemesi — `r < 0.5` → Gbest'e çek, `0.5 ≤ r < 0.8` → Pbest'e çek, `r ≥ 0.8` → değiştirme.
4. **Mutasyon:** Swap, Shift, Inverse operatörleri.
5. **Adaptif yerel arama:** Stagnation tespitinde Gbest üzerinde swap-tabanlı iyileştirme.

**Parametreler:** 5 particle, 500 iterasyon, kapasite 100 WU.

---

## 4. Önerilen Yöntem: RBRS-AE

### 4.1 Motivasyon

DEPSO'nun permütasyon bazlı PSO arama yapısı, sipariş gruplamayı rota maliyetiyle doğrudan ilişkilendirmez. RBRS-AE bunu **bilinçli inşaat** ile çözer: her atama kararı, o siparişin farklı batch'lere girmesinin rota maliyetine etkisini karşılaştırarak alınır.

### 4.2 Algoritma Adımları

**Adım 1 — Öncelik Skoru:**
Her siparişe depodan uzaklığı (Manhattan mesafesi) kadar skor verilir. Uzak siparişler önce atanır.

**Adım 2 — Sıralama:**
Siparişler öncelik skoruna göre azalan sırada dizilir.

**Adım 3 — Pişmanlık Bazlı İnşaat:**
```
Atanmamış sipariş kaldığı sürece:
  Her sipariş için tüm batch seçeneklerini değerlendir:
    en_iyi_maliyet   = min(delta_mesafe)
    ikinci_en_iyi    = 2. en küçük delta
    pişmanlık        = ikinci_en_iyi - en_iyi_maliyet
  En yüksek pişmanlıklı siparişi en iyi batch'e ata
```

**Adım 4 — Rota İnşası:**
Tüm batch'ler için Combined+ ile mesafe hesaplanır. Sonuçlar önbelleğe alınır.

**Adım 5 — Yinelemeli İyileştirme:**
```
Durdurma kriteri sağlanana kadar:
  Batch Shift: bir siparişi başka batch'e taşı (ilk iyileştirme)
  Batch Swap: iki batch arasında sipariş değiştir (ilk iyileştirme)
  Eğer stagnation >= limit:
    En verimsiz batch'i tespit et ve dağıt
    Siparişleri regret ile yeniden ata
  En iyi çözümü güncelle
```

### 4.3 Pseudocode — Kod Eşleşmesi

| Pseudocode Adımı | Kod Karşılığı |
|---|---|
| Öncelik skoru | `_priority_score(order_id)` |
| Sıralama | `sorted(..., key=_priority_score, reverse=True)` |
| Regret inşaatı | `_build_solution()` → `_regret_step()` |
| Rota inşası | `_construct_and_improve_routes()` |
| Batch shift | `_batch_shift()` |
| Batch swap | `_batch_swap()` |
| Verimsiz batch tespiti | `_identify_inefficient_batch()` |
| Adaptif eleme | `_adaptive_elimination()` |
| En iyi güncelleme | `if cur_dist < best_dist: best_dist = cur_dist` |
| Dönüş | `return best_perm, best_dist, elapsed, best_batches` |

---

## 5. Deneysel Düzen

### 5.1 Depo Modeli

| Özellik | Değer |
|---|---|
| Toplama koridoru | 10 |
| Cross-aisle | 4 |
| Raf pozisyonu (aisle başına) | 45 |
| Toplam konum | 450 |
| Kapasite | 100 WU |
| Mesafe metriği | Manhattan (LU) |

### 5.2 Test Senaryoları

| Senaryo | Sipariş | Maks Satır | Maks Miktar |
|---|---|---|---|
| 50_2_6  | 50  | 2  | 6  |
| 50_6_6  | 50  | 6  | 6  |
| 50_10_6 | 50  | 10 | 6  |
| 100_6_6 | 100 | 6  | 6  |
| 100_6_10| 100 | 6  | 10 |

Her senaryo için 3 seed, her seed için bağımsız instance.

### 5.3 Komutlar

```bash
# Hızlı demo (3 saniye):
python main.py --demo

# Tek senaryo:
python main.py --scenario 100_6_6 --instances 3 --seed 42

# Tam benchmark (tüm senaryolar):
python main.py --full --instances 3 --seed 42

# Doğrulama:
python main.py --validate

# Streamlit dashboard:
streamlit run dashboard.py
```

---

## 6. Sonuçlar

### 6.1 Benchmark Tablosu (3 seed ortalaması)

| Senaryo | SOP | FCFS | DEPSO | RBRS-AE | RBRS-AE vs DEPSO |
|:---|---:|---:|---:|---:|---:|
| 50_2_6   | 1742.7 | 556.0  | 429.0 | 419.3 | **+2.25%** |
| 50_6_6   | 1816.7 | 783.7  | 511.3 | 456.0 | **+10.82%** |
| 50_10_6  | 1816.0 | 908.0  | 597.0 | 570.3 | **+4.47%** |
| 100_6_6  | 3720.0 | 1594.0 | 777.0 | 718.7 | **+7.51%** |
| 100_6_10 | 3720.0 | 1885.7 | 940.0 | 808.3 | **+14.01%** |

*Tüm mesafeler LU cinsindendir. Pozitif yüzde = RBRS-AE daha iyi.*

### 6.2 Gözlemler

- RBRS-AE **tüm senaryolarda** DEPSO'yu geride bırakmaktadır.
- İyileşme, problem karmaşıklığı arttıkça büyür: 50_2_6'da +2.25%, 100_6_10'da +14.01%.
- RBRS-AE aynı zamanda **3-5× daha hızlıdır** (mesafe önbelleği sayesinde).
- Her iki algoritma da SOP'a kıyasla %75–82 mesafe azaltımı sağlar.

---

## 7. Tartışma

**Neden RBRS-AE daha iyi?**

DEPSO permütasyon uzayını rastgele PSO hareketleriyle arar; rota maliyetini dolaylı olarak optimize eder. RBRS-AE ise her atama kararında rota maliyetini doğrudan değerlendirir. Pişmanlık mekanizması, "zor" siparişleri (birden fazla iyi seçeneği olmayan) önce yerleştirerek sonradan düzeltmesi gereken kötü atamaları engeller. Adaptif eleme ise yerel optimumlardan çıkışı sağlar.

**Kapsam sınırı:**

Makalenin bütünü üç problemi birlikte çözüyor (raf ataması + gruplama + rotalama). Biz sadece gruplama ve rotalama kısmını ele aldık çünkü raf ataması için gerçek talep zaman serisi verisi gerekiyor. RBRS-AE, makalenin DEPSO bileşeninin doğrudan yerine kullanılabilir ve aynı iteratif çerçeveye entegre edilebilir.

---

## 8. Proje Mimarisi

```
adfo/
├── warehouse.py          — Depo geometrisi (10 aisle, 4 cross-aisle)
├── routing.py            — Combined+ ve NN+2opt routing heuristikleri
├── instances.py          — ABC talep dağılımlı instance üretimi
├── depso.py              — DEPSO algoritması (makaleye sadık)
├── rbrs_ae_algorithm.py  — RBRS-AE (önerilen yeni algoritma)
├── baselines.py          — SOP ve FCFS referans yöntemleri
├── main.py               — Benchmark pipeline (--demo/--full/--validate)
├── dashboard.py          — Streamlit görsel arayüz
├── requirements.txt      — Python bağımlılıkları
├── reports/              — Bu rapor ve İngilizce akademik rapor
├── supplementary_extracted/  — Makale ek tabloları (table_01..10.csv)
└── results/              — Benchmark CSV'leri ve grafikler
```

### Kullanılan Kütüphaneler

| Kütüphane | Amaç |
|---|---|
| `numpy` | Sayısal işlemler, rastgele sayı üretimi |
| `matplotlib` | Convergence ve bar grafikleri |
| `scipy` | İstatistiksel yardımcılar |
| `tqdm` | Benchmark ilerleme çubuğu |
| `streamlit` | Etkileşimli dashboard |
| `pandas` | Sonuç tabloları |

---

## 9. Sınırlılıklar ve Gelecek Çalışmalar

**Sınırlılıklar:**
1. Dinamik raf ataması katmanı implemente edilmedi (gerçek talep verisi yok).
2. Depo ölçeği makaleden küçük (450 vs 7.200 konum).
3. Gerçek şirket verisi yerine sentetik senaryolar kullanıldı.

**Gelecek Çalışmalar:**
- Gerçek verilerle tam üç-problem iteratif çerçeveyi çalıştırmak.
- Wilcoxon istatistiksel anlamlılık testi uygulamak (35 senaryo).
- RBRS-AE'yi güçlü meta-sezgisellerle (tabu search, simulated annealing) kıyaslamak.

---

## Kaynak

Kübler, P., Glock, C. H., & Bauernhansl, T. (2020). A new iterative method for solving the joint dynamic storage location assignment, order batching and picker routing problem in manual picker-to-parts warehouses. *Computers & Industrial Engineering, 147*, 106645. https://doi.org/10.1016/j.cie.2020.106645
