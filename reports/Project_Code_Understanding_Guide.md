# Projeyi Koddan Anlama Rehberi

Bu belge, projedeki dosyaları ve algoritmaları okuyup anlamak isteyen biri için hazırlandı. Amaç, sadece "hangi dosya ne yapıyor" sorusunu cevaplamak değil; aynı zamanda kodu hangi sırayla okuyacağını, hangi mantığın nerede uygulandığını ve sonuçları nasıl yorumlayacağını da göstermektir.

## 1. Bu Proje Ne Yapıyor?

Proje, depo içinde sipariş toplama problemini ele alıyor. Bu problemde iki karar birlikte verilmek zorunda:

1. Hangi siparişler aynı batch içine konacak?
2. Her batch içindeki ürünler depoda hangi rota ile toplanacak?

Bu iki karar birbiriyle bağlı olduğu için problem "joint order batching & picker routing" olarak geçiyor. Yani batch yapısı değişmeden rota aynı kalmaz; rota değişince toplam mesafe değişir. Kodun tüm ana fikri bu bağlılığı optimize etmek.

Kaynak makale: **Kübler, Glock ve Bauernhansl (2020)** — *A new iterative method for solving the joint dynamic storage location assignment, order batching and picker routing problem in manual picker-to-parts warehouses*, Computers & Industrial Engineering 147, 106645.

## 2. Kodu Okumaya Hangi Sırayla Başlamalı?

Eğer projeyi ilk defa okuyorsan şu sırayı takip et:

1. `warehouse.py` — depo geometrisi (temel veri yapısı)
2. `routing.py` — mesafe hesaplama heuristikleri
3. `instances.py` — test instance'larının üretimi
4. `baselines.py` — SOP ve FCFS referans yöntemleri
5. `depso.py` — DEPSO algoritması (Paper-2 baz yöntemi)
6. `rbrs_ae_algorithm.py` — RBRS-AE algoritması (önerilen yöntem)
7. `main.py` — benchmark pipeline'ı
8. `dashboard.py` — Streamlit arayüzü

## 3. Büyük Resim: Veri Kodda Nasıl Akıyor?

Proje tek bir unified depo modu üzerinde çalışır.

Akış şöyledir:
1. `instances.py` bir instance üretir.
2. Instance içindeki her siparişin `aisle`, `position` ve `weight` bilgisi vardır.
3. `depso.py` ve `rbrs_ae_algorithm.py` aynı instance üzerinde çalışır.
4. Her iki algoritma da `routing.py` içindeki `combined_plus_distance()` fonksiyonunu kullanır.
5. Toplam picker yürüyüş mesafesi fitness olarak kullanılır; daha az mesafe daha iyi.

## 4. Dosya Dosya Açıklama

### 4.1 `warehouse.py`
Depo geometrisini tanımlar: 10 aisle, 4 cross-aisle, aisle başına 45 raf konumu (toplam 450 konum), depot koordinatı.

**Temel sınıf:** `Warehouse`
- `get_depot_coords()` → depo giriş/çıkış noktası
- `get_location_coords(aisle, position)` → bir rafın x/y koordinatları
- `aisle_x`, `cross_aisle_y` → geometri verileri

### 4.2 `routing.py`
Rota mesafesi hesaplar. Dört klasik heuristik:
- `s_shape_distance` — tüm aisleleri sırayla geçer
- `return_distance` — her aisle'a girip en uzak ürüne gidip döner
- `midpoint_distance` — aisle'ı ortadan böler, her yarıyı ayrı taraftan erişir
- `largest_gap_distance` — en büyük boşluğu atlar, iki yönden erişir
- `combined_plus_distance` — dördünün minimumunu seçer (**tüm algoritmalar bunu kullanır**)

Ek olarak `nn_2opt_distance()` — NN inşaat + 2-opt iyileştirme — de tanımlıdır ancak mevcut benchmark'ta kullanılmaz.

### 4.3 `instances.py`
Test instance'ları üretir. ABC benzeri talep dağılımı:
- A ürünleri (%20) → depo girişine yakın aisle'lara atanır
- B ürünleri (%30) → orta aisle'lar
- C ürünleri (%50) → uzak aisle'lar

Her instance'da her siparişin `id`, `aisle`, `position`, `weight` alanları vardır. Senaryo formatı `N_L_A`: N sipariş, L maks satır/sipariş, A maks miktar.

### 4.4 `baselines.py`
İki basit referans yöntemi:
- `sop_distance(instance, warehouse)` — Single Order Picking: her sipariş ayrı bir batch, toplam bireysel rota mesafesi hesaplanır (en yüksek mesafe referansı).
- `fcfs_distance(instance, warehouse)` — First-Come-First-Served: siparişler ID sırasıyla first-fit ile batch'lere atanır; Combined+ ile route edilir.

### 4.5 `depso.py`
**Paper-2 baz algoritması: DEPSO** (Discrete Evolutionary Particle Swarm Optimization)

Makaledeki §6.2'deki yöntemi uygular:
- Her çözüm bir **sipariş permütasyonu** olarak kodlanır.
- **First-fit batching:** Permütasyon sırasıyla her sipariş kapasitesi yeten ilk batch'e atanır.
- **Combined+ routing:** Her batch için dört heuristiğin minimumu alınır.
- **Threshold velocity güncellemesi:** `r < 0.5` → gbest'e çek, `0.5 ≤ r < 0.8` → pbest'e çek, `r ≥ 0.8` → değişme.
- **Mutasyon:** Swap, Shift, Inverse operatörleri.
- **Adaptif lokal arama:** Durgunluk tespitinde gbest üzerinde swap tabanlı iyileştirme.

**Parametreler:** 5 particle, 500 iterasyon, kapasite 100 WU.

**Dönüş değerleri:** `(best_permutation, best_distance, elapsed, convergence_history)`

### 4.6 `rbrs_ae_algorithm.py`
**Önerilen yöntem: RBRS-AE** (Route-Based Regret Search with Adaptive Elimination)

**Pseudocode adımlarının kodla eşleşmesi:**

| Pseudocode Adımı | Kod Karşılığı |
|---|---|
| Öncelik skoru | `_priority_score(order_id)` |
| Sıralama | `sorted(order_ids, key=_priority_score, reverse=True)` |
| Regret inşaatı | `_build_solution()` → `_regret_step()` |
| Rota inşası | `_construct_and_improve_routes()` |
| Batch shift | `_batch_shift()` |
| Batch swap | `_batch_swap()` |
| Verimsiz batch tespiti | `_identify_inefficient_batch()` |
| Adaptif eleme | `_adaptive_elimination()` |
| En iyi güncelleme | `if cur_dist < best_dist: best_dist = cur_dist` |
| Dönüş | `return best_perm, best_dist, elapsed, best_batches` |

**Kritik detaylar:**
- `_batch_distance()`: Her batch için `combined_plus_distance()` çağırır; sonuçları `_dist_cache` sözlüğünde önbellekler (aynı batch için tekrar hesap yapmaz). Cache anahtarı: `tuple(sorted(order_ids))`.
- `_regret_step()`: `regret = 2. en iyi maliyet - en iyi maliyet`; en yüksek pişmanlıklı sipariş önce en iyi batch'e atanır.
- `_adaptive_elimination()`: En yüksek per-order maliyetli batch bulunur, dağıtılır, siparişler regret mekanizmasıyla yeniden atanır.
- Stagnation kontrolü: `stagnation_limit` kadar iyileşme olmazsa AE tetiklenir.

**`run()` dönüş değerleri:**
```python
best_perm, best_distance, elapsed, best_batches = rbrs.run()
```
- `best_perm`: DEPSO ile arayüz uyumluluğu için düzleştirilmiş sipariş ID listesi
- `best_distance`: bulunan minimum toplam rota mesafesi
- `elapsed`: saniye cinsinden çalışma süresi
- `best_batches`: en iyi çözümün batch yapısı

### 4.7 `main.py`
Benchmark pipeline'ının tek giriş noktası. Dört mod:

```bash
python main.py --demo                          # ~3 saniye, 2 senaryo
python main.py --scenario 100_6_6 --instances 3 --seed 42   # tek senaryo
python main.py --full --instances 3 --seed 42  # tüm 5 senaryo
python main.py --validate                      # tutarlılık kontrolü
```

Her çalıştırmada:
- SOP, FCFS, DEPSO ve RBRS-AE her instance üzerinde koşturulur.
- Sonuçlar `results/benchmark_results_<scenario>.csv` dosyasına kaydedilir.
- `results/figures/convergence_<scenario>.png` ve `results/figures/bar_<scenario>.png` grafikleri üretilir.
- `--full` modunda `results/summary_full.json` oluşturulur.

### 4.8 `dashboard.py`
Streamlit arayüzü. Çalıştırma:
```bash
streamlit run dashboard.py
```
Sayfalar: Ana sayfa, Algoritma Karşılaştırması, Benchmark Sonuçları, Algoritma Detayları.

## 5. Algoritmaların Adım Adım Çalışma Mantığı

### 5.1 DEPSO

1. 5 particle başlatılır; particle 0: savings-based seed, diğerleri rastgele permütasyon.
2. Her iterasyonda her particle için:
   a. Threshold velocity güncellenir (`r` rastgele, üç eşik bölgesi).
   b. Permütasyon güncellenir.
   c. Swap/Shift/Inverse mutasyonlarından biri uygulanır.
   d. Fitness hesaplanır: first-fit batching → Combined+ routing.
   e. pbest ve gbest güncellenir.
3. Durgunluk varsa gbest üzerinde swap tabanlı yerel arama çalışır.
4. `convergence_history` her iterasyonda kaydedilir.

### 5.2 RBRS-AE

1. **Öncelik skorla:** Depoya Manhattan mesafesi büyük olan siparişler yüksek öncelik alır; uzak siparişler önce yerleştirilir.
2. **Regret inşaatı:** Her adımda tüm atanmamış siparişler için her mevcut batch'e eklemenin delta maliyet artışı hesaplanır; en yüksek pişmanlığa sahip sipariş (= fırsatı kaybetmenin en pahalı olduğu sipariş) seçilir ve en iyi batch'e atanır.
3. **Rota inşası:** Tüm başlangıç batch'leri için Combined+ ile mesafe hesaplanır; sonuçlar önbelleğe alınır.
4. **İteratif iyileştirme** (stagnation_limit kadar):
   - **Batch Shift:** Bir siparişi başka batch'e taşı → mesafe azalıyorsa kabul et, dur.
   - **Batch Swap:** İki batch arasında birer sipariş değiştir → mesafe azalıyorsa kabul et, dur.
   - **Adaptive Elimination** (stagnation >= limit ise): En verimsiz batch'i dağıt → siparişleri regret ile yeniden ata.
5. **En iyi çözümü döndür.**

## 6. Sonuçları Nasıl Okumalıyız?

Benchmark çıktılarında şu değerler yer alır:
- `sop_distance`: tek tek toplama referansı (en yüksek mesafe)
- `fcfs_distance`: basit sıralı atama referansı
- `depso_distance` / `rbrs_distance`: algoritma sonuçları (LU birimi)
- `rbrs_vs_depso_pct`: pozitif = RBRS-AE daha iyi, negatif = DEPSO daha iyi

Benchmark sonuçları (3 seed ortalaması, DEPSO: 500 iter, RBRS-AE: 200 iter):

| Senaryo | SOP | FCFS | DEPSO | RBRS-AE | RBRS-AE kazancı |
|---|---:|---:|---:|---:|---:|
| 50_2_6  | 1742.7 | 556.0 | 429.0 | 419.3 | **+2.25%** |
| 50_6_6  | 1816.7 | 783.7 | 511.3 | 456.0 | **+10.82%** |
| 50_10_6 | 1816.0 | 908.0 | 597.0 | 570.3 | **+4.47%** |
| 100_6_6 | 3720.0 | 1594.0 | 777.0 | 718.7 | **+7.51%** |
| 100_6_10| 3720.0 | 1885.7 | 940.0 | 808.3 | **+14.01%** |

RBRS-AE tüm senaryolarda DEPSO'yu geride bırakır. Kazanç, problem karmaşıklığı arttıkça büyür.

## 7. Dikkat Edilecek Noktalar

1. **Tüm algoritmalar aynı routing fonksiyonunu kullanır:** `combined_plus_distance()`. Bu, karşılaştırmayı routing seçiminden bağımsız hale getirir; sadece batching stratejisi karşılaştırılır.
2. **Mesafe önbelleği:** RBRS-AE aynı batch için Combined+ hesabını tekrarlamaz. Bu nedenle DEPSO'dan 3–5× daha hızlıdır.
3. **Regret ≠ greedy:** Greedy ilk en iyi batch'e atar; regret, "Bu sipariş şimdi yanlış yere giderse sonradan ne kadar maliyeti artar?" sorusunu sorar. Uzak/zor siparişler önce atanır.
4. **İyileşme eğrisi:** `--demo` veya `--full` çalıştırıldıktan sonra `results/figures/convergence_*.png` dosyaları her iki algoritmanın iterasyon başına mesafe gelişimini gösterir.
5. **`main.py` tek giriş noktası:** Ayrı benchmark scripti yoktur; tüm modlar `main.py` üzerinden erişilir.

## 8. Kısa Özet

| Bileşen | Dosya |
|---|---|
| Depo modeli | `warehouse.py` |
| Rota hesapları | `routing.py` |
| Test instance üretimi | `instances.py` |
| Referans algoritmalar (SOP, FCFS) | `baselines.py` |
| DEPSO (makale baz yöntemi) | `depso.py` |
| RBRS-AE (önerilen yöntem) | `rbrs_ae_algorithm.py` |
| Benchmark pipeline | `main.py` |
| Streamlit arayüzü | `dashboard.py` |
