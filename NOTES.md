# Bilinen Sorunlar / Notlar

## 1. Alt-periyot sipariş dağılımı dengesiz

**Durum:** Bizim generator, alt-periyotlar arasında siparişleri eşit dağıtmıyor.
Periyot 1, S1'de alt-periyot 1'de 2932 sipariş, alt-periyot 20'de 109 sipariş var.

**Sebep:** `warehouse_dataset_generator.py` içinde `subperiod_item_ol` hesaplaması:
```python
base = total_ol // num_subperiods
extra = total_ol % num_subperiods
subperiod_item_ol[m] = base + (1 if subperiod_idx < extra else 0)
```
Çoğu item için `total_ol < num_subperiods` (örneğin 3 orderline, 20 alt-periyot),
bu durumda `base=0`, `extra=3` → sadece alt-periyot 0, 1, 2'ye 1'er orderline düşüyor,
diğerlerine 0. Bu nedenle baş alt-periyotlar şişiyor.

**Etki:** Paper alt-periyotları "günler" olarak yorumluyor. Bir günün siparişi
algoritmaya tek seferde verilir. Yoğun günlerde DEPSO daha çok iş yapar, sorun yok.

**Çözüm (sonra yapılacak):** Item'lar yerine **toplam orderline pool**'unu doğrudan
alt-periyotlara eşit dağıt; item-orderline eşleşmesi tüm pool üzerinde shuffle ile.

## 2. Mesafe matrisi tüm 7200 lokasyon için pre-compute edilmiyor

**Sebep:** 7200×7200 = 51M float64 = ~400 MB RAM. Aşırı.
**Çözüm:** Sadece kullanılan lokasyonlar için on-demand hesap (warehouse.distance_matrix()).
