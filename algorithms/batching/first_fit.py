"""
algorithms/batching/first_fit.py
=================================
First-Fit batching rule - Paper Section 5.2.2.

Paper'ın açıklaması:
"We assign orders to batches in the sequence of the particle's permutation and
open a new batch in case an order does not fit into the current batch anymore.
We then continue in the permutation and assign the remaining orders to the
batch with the smallest number into which they fit."

Yani iki aşama:
1) Permutasyon sırasıyla sığdırarak yeni batch'ler aç
2) Kalan siparişleri var olan EN KÜÇÜK ID'li batch'e ata (kapasiteye sığarsa)
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.data_loader import Order
from algorithms.base import Batch
from config import ITEMS


def first_fit_batching(
    orders: list[Order],
    capacity: float = None,
) -> list[Batch]:
    """
    First-fit kuralıyla batching.

    orders: belirli bir SIRADA gelen siparişler (DEPSO'da bu sıra particle permutasyonu)
    capacity: picker kapasitesi (default: config'ten)

    Döndürür: Batch listesi
    """
    if capacity is None:
        capacity = ITEMS['picker_capacity_WU']

    batches: list[Batch] = []
    unassigned: list[Order] = []

    # Aşama 1: Sıraya göre, sığdığı ilk batch'e ekle, yoksa yeni batch aç
    for order in orders:
        placed = False
        for batch in batches:
            if batch.total_weight + order.total_weight <= capacity:
                batch.orders.append(order)
                batch.total_weight += order.total_weight
                placed = True
                break

        if not placed:
            # Bu siparişin tek başına bile sığması gerekiyor
            if order.total_weight > capacity:
                # Edge case: tek sipariş kapasiteyi aşıyor — atla veya hata
                # Paper'a göre bu olmamalı (Assumption 6)
                unassigned.append(order)
                continue

            # Yeni batch aç
            new_batch = Batch(
                batch_id=len(batches),
                orders=[order],
                total_weight=order.total_weight,
            )
            batches.append(new_batch)

    if unassigned:
        # Pratik düşünce: paper Assumption 6'ya göre bu olmamalı
        # ama gerçekleşirse her birini ayrı batch'e at
        for o in unassigned:
            batches.append(Batch(
                batch_id=len(batches),
                orders=[o],
                total_weight=o.total_weight,
            ))

    return batches


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from core.data_loader import DataLoader

    loader = DataLoader()

    # Senaryo 1, periyot 1, alt-periyot 5'i test et (yönetilebilir boyut)
    sub = loader.load_orders(1, 1, 5)
    print(f"Test: S1 P1 sub5 → {sub.num_orders} sipariş, {sub.total_orderlines} orderline")

    batches = first_fit_batching(sub.orders)
    print(f"Batch sayısı: {len(batches)}")
    print(f"İlk 5 batch:")
    for b in batches[:5]:
        print(f"  Batch {b.batch_id}: {len(b.orders)} sipariş, "
              f"{b.total_weight:.2f}/{ITEMS['picker_capacity_WU']} WU "
              f"({b.total_weight / ITEMS['picker_capacity_WU'] * 100:.1f}% dolu), "
              f"{b.num_orderlines} orderline")

    avg_util = sum(b.total_weight for b in batches) / (len(batches) * ITEMS['picker_capacity_WU'])
    print(f"\nOrtalama doluluk oranı: {avg_util:.3f}")
