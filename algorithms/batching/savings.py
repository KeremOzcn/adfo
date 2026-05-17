"""
algorithms/batching/savings.py
===============================
Clarke-Wright Savings algorithm - Paper Appendix D.

İki sipariş k1 ve k2'yi aynı batch'te birleştirmenin "kazancı":
    Sav(k1, k2) = Td(k1) + Td(k2) - Td(k1 + k2)

Burada Td(x) = x siparişinin TEK BAŞINA travel distance'ı.

Yüksek savings → bu iki siparişi birleştirmek mantıklı (mesafeleri yakın).

Algoritma:
1) Tüm sipariş çiftleri için savings hesapla
2) Savings'i azalan sıraya koy
3) Sırayla:
   - Hiçbiri batch'te değil → yeni batch aç, ikisini koy
   - Biri batch'te, diğeri değil → kapasite sığarsa o batch'e ekle
   - İkisi de batch'te → atla
4) Atanmamış sipariş kaldıysa kendi batch'lerine koy
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.data_loader import Order
from algorithms.base import Batch
from algorithms.routing.two_opt import nn_then_2opt
from config import ITEMS


def savings_batching(
    orders: list[Order],
    warehouse,
    capacity: float = None,
    cache_distances: bool = True,
) -> list[Batch]:
    """
    Clarke-Wright Savings ile batching.

    orders: tüm siparişler
    warehouse: mesafe hesabı için
    capacity: picker kapasitesi

    Döndürür: Batch listesi
    """
    if capacity is None:
        capacity = ITEMS['picker_capacity_WU']

    n = len(orders)
    if n == 0:
        return []

    # Adım 1: Her sipariş için tek başına travel distance
    print(f"  [Savings] {n} sipariş için tek başına TD hesaplanıyor...")
    individual_td = []
    for i, o in enumerate(orders):
        _, dist = nn_then_2opt(o.locations, warehouse)
        individual_td.append(dist)

    # Adım 2: Sipariş çiftleri için savings (kapasiteye uyanlar)
    print(f"  [Savings] {n*(n-1)//2} çift için savings hesaplanıyor...")
    savings_list = []  # (sav, i, j)
    for i in range(n):
        for j in range(i + 1, n):
            # Kapasite kontrolü
            if orders[i].total_weight + orders[j].total_weight > capacity:
                continue
            # Birleşik travel distance
            combined_locs = orders[i].locations + orders[j].locations
            _, combined_td = nn_then_2opt(combined_locs, warehouse)
            sav = individual_td[i] + individual_td[j] - combined_td
            if sav > 0:  # sadece pozitif kazançlar
                savings_list.append((sav, i, j))

    # Adım 3: Savings azalan sırada işle
    savings_list.sort(reverse=True, key=lambda x: x[0])

    # Her sipariş için ait olduğu batch_id (-1 = henüz atanmamış)
    order_batch: list[int] = [-1] * n
    batches: list[Batch] = []

    for sav, i, j in savings_list:
        bi, bj = order_batch[i], order_batch[j]

        if bi == -1 and bj == -1:
            # İkisi de henüz batch'te değil → yeni batch
            new_batch = Batch(
                batch_id=len(batches),
                orders=[orders[i], orders[j]],
                total_weight=orders[i].total_weight + orders[j].total_weight,
            )
            batches.append(new_batch)
            order_batch[i] = new_batch.batch_id
            order_batch[j] = new_batch.batch_id

        elif bi != -1 and bj == -1:
            # i batch'te, j değil → eklemeyi dene
            b = batches[bi]
            if b.total_weight + orders[j].total_weight <= capacity:
                b.orders.append(orders[j])
                b.total_weight += orders[j].total_weight
                order_batch[j] = bi

        elif bi == -1 and bj != -1:
            b = batches[bj]
            if b.total_weight + orders[i].total_weight <= capacity:
                b.orders.append(orders[i])
                b.total_weight += orders[i].total_weight
                order_batch[i] = bj

        # bi != -1 and bj != -1 → ikisi de batch'te, atla

    # Adım 4: Hala atanmamış siparişleri tek başlarına batch'e koy
    for i, o in enumerate(orders):
        if order_batch[i] == -1:
            new_batch = Batch(
                batch_id=len(batches),
                orders=[o],
                total_weight=o.total_weight,
            )
            batches.append(new_batch)
            order_batch[i] = new_batch.batch_id

    return batches


if __name__ == "__main__":
    from core.data_loader import DataLoader
    from core.warehouse import Warehouse
    import time

    loader = DataLoader()
    wh = Warehouse()

    # Küçük bir test instance (savings O(n²) yavaş!)
    # En küçük alt-periyodu seçelim
    sub = loader.load_orders(1, 1, 20)
    print(f"Test: S1 P1 sub20 → {sub.num_orders} sipariş")

    # Limit ile (savings O(n²), büyük n'de patlar)
    test_orders = sub.orders[:50]
    print(f"İlk 50 sipariş üzerinde savings çalıştırılıyor...")

    t0 = time.perf_counter()
    batches = savings_batching(test_orders, wh)
    elapsed = time.perf_counter() - t0

    print(f"\nSüre: {elapsed:.2f}s")
    print(f"Batch sayısı: {len(batches)}")
    print(f"Ortalama doluluk: "
          f"{sum(b.total_weight for b in batches) / (len(batches) * ITEMS['picker_capacity_WU']):.3f}")
    print(f"İlk 3 batch:")
    for b in batches[:3]:
        print(f"  Batch {b.batch_id}: {len(b.orders)} sipariş, "
              f"{b.total_weight:.2f} WU, {b.num_orderlines} orderline")
