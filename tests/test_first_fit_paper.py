"""
tests/test_first_fit_paper.py
==============================
Paper supplement örneğiyle first-fit'i doğrula.

Test verisi (endüstrici arkadaşlardan):
  Order sequence: 4, 7, 2, 9, 1, 3, 5, 10, 6
  Weights:        25, 70, 10, 60, 40, 35, 20, 80, 5
  Capacity:       100

Beklenen batch'ler:
  Batch 1: 4, 7    → 25 + 70 = 95
  Batch 2: 2, 9, 5 → 10 + 60 + 20 = 90
  Batch 3: 1, 3    → 40 + 35 = 75
  (10 ve 6 da bir yere sığar)

Paper'ın "smallest batch number into which they fit" kuralı:
- Yeni gelen order ilk batch'e sığmıyorsa, açık batch'lerden en küçük numaralı
  olana (sığıyorsa) atanır. Sığmıyorsa yeni batch açılır.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_loader import Order, OrderLine
from algorithms.batching.first_fit import first_fit_batching


def make_order(order_id: int, weight: float) -> Order:
    """Tek orderline'lı, dummy lokasyonlu test siparişi."""
    ol = OrderLine(item=order_id, quantity=1, location=order_id * 100, weight=weight)
    return Order(
        order_id=order_id,
        num_orderlines=1,
        total_weight=weight,
        orderlines=[ol],
    )


def test_paper_first_fit():
    """Paper supplement Part 1 örneği."""
    sequence = [4, 7, 2, 9, 1, 3, 5, 10, 6]
    weights = [25, 70, 10, 60, 40, 35, 20, 80, 5]

    orders = [make_order(oid, w) for oid, w in zip(sequence, weights)]

    print("Test siparişleri (sıra ve ağırlıklar):")
    for o in orders:
        print(f"  Order {o.order_id}: {o.total_weight} WU")

    batches = first_fit_batching(orders, capacity=100.0)

    print(f"\nBatch sonuçları:")
    for b in batches:
        order_ids = [o.order_id for o in b.orders]
        print(f"  Batch {b.batch_id + 1}: orders={order_ids}, "
              f"total={b.total_weight} WU")

    # Beklenen sonuç:
    # Batch 1: order 4 (25) → batch 1 açılır
    # Batch 1: order 7 (70) → batch 1'e sığar (95)
    # Batch 2: order 2 (10) → batch 1'e sığmaz (95+10=105), batch 2 açılır
    # Batch 2: order 9 (60) → batch 1'e sığmaz, batch 2'ye sığar (70)
    # Batch 3: order 1 (40) → batch 1'e sığmaz (95+40), batch 2'ye sığmaz (70+40=110), batch 3 açılır
    # Batch 3: order 3 (35) → batch 1'e sığmaz (95+35), batch 2'ye sığmaz (70+35=105), batch 3'e sığar (75)
    # Batch 2: order 5 (20) → batch 1'e sığmaz (95+20=115), batch 2'ye sığar (70+20=90)
    # Batch 4: order 10 (80) → batch 1'e sığmaz, batch 2'ye sığmaz, batch 3'e sığmaz (75+80), batch 4 açılır
    # Batch 1: order 6 (5)   → batch 1'e SIĞAR (95+5=100)

    expected = {
        0: [4, 7, 6],      # batch 1: 4, 7 (95) → sonra 6 (5) eklenir → 100
        1: [2, 9, 5],      # batch 2: 2, 9 (70) → sonra 5 (20) eklenir → 90
        2: [1, 3],         # batch 3: 1, 3 (75)
        3: [10],           # batch 4: 10 (80)
    }

    print(f"\nBeklenen:")
    for bid, ords in expected.items():
        print(f"  Batch {bid + 1}: orders={ords}")

    # Doğrulama
    actual = {b.batch_id: [o.order_id for o in b.orders] for b in batches}
    if actual == expected:
        print("\n✓ first-fit paper örneğiyle UYUMLU")
        return True
    else:
        print("\n✗ first-fit paper örneğiyle UYUŞMUYOR")
        print(f"  Beklenen: {expected}")
        print(f"  Bizim:    {actual}")
        return False


if __name__ == "__main__":
    test_paper_first_fit()
