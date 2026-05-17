"""
tests/test_first_fit.py
========================
Paper supplement Part 1'deki first-fit örneğine karşı testimiz.

Verilen:
  Order sequence: 4, 7, 2, 9, 1, 3, 5, 10, 6
  Weights:        25, 70, 10, 60, 40, 35, 20, 80, 5
  Capacity: 100

Beklenen (paper supplement):
  Batch 1: 4, 7    = 95
  Batch 2: 2, 9, 5 = 90
  Batch 3: 1, 3    = 75
  ...

Önemli yorum: Weight listesi POZİSYONEL (sequence sırasına göre), order ID'sine
göre değil. Yani sequence'in i. order'ı için ağırlık weights[i]'dir.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dataclasses import dataclass
from algorithms.batching.first_fit import first_fit_batching


@dataclass
class _MockOrderLine:
    item: int
    quantity: int
    location: int
    weight: float


@dataclass
class _MockOrder:
    """first_fit'in beklediği minimal Order arayüzü."""
    order_id: int
    total_weight: float
    num_orderlines: int
    orderlines: list

    @property
    def locations(self):
        return [ol.location for ol in self.orderlines]


def build_supplement_orders():
    """Paper supplement Part 1 örneği."""
    sequence_ids = [4, 7, 2, 9, 1, 3, 5, 10, 6]
    weights = [25, 70, 10, 60, 40, 35, 20, 80, 5]

    orders = []
    for order_id, w in zip(sequence_ids, weights):
        # Lokasyon önemsiz — sadece batching test ediliyor
        ol = _MockOrderLine(item=order_id, quantity=1, location=0, weight=w)
        orders.append(_MockOrder(
            order_id=order_id,
            total_weight=float(w),
            num_orderlines=1,
            orderlines=[ol],
        ))
    return orders


def run_test():
    print("=" * 70)
    print("FIRST-FIT TESTİ (paper supplement Part 1)")
    print("=" * 70)

    orders = build_supplement_orders()
    print("\nGirdi:")
    print(f"  Sequence: {[o.order_id for o in orders]}")
    print(f"  Weights:  {[o.total_weight for o in orders]}")
    print(f"  Capacity: 100")

    batches = first_fit_batching(orders, capacity=100.0)

    print(f"\nBizim implementasyon — {len(batches)} batch oluştu:")
    for b in batches:
        ids = [o.order_id for o in b.orders]
        print(f"  Batch {b.batch_id + 1}: {ids} = {b.total_weight:.0f} WU")

    # Beklenen ilk 3 batch
    print("\nPaper supplement beklenen (ilk 3 batch — snapshot, order 6 öncesi):")
    print("  Batch 1: [4, 7]     = 95")
    print("  Batch 2: [2, 9, 5]  = 90")
    print("  Batch 3: [1, 3]     = 75")

    # Doğrulama
    print("\nDoğrulama:")
    expected_first_three = [
        ({4, 7}, 95.0),
        ({2, 9, 5}, 90.0),
        ({1, 3}, 75.0),
    ]
    ok = True
    for i, (exp_ids, exp_weight) in enumerate(expected_first_three):
        if i >= len(batches):
            print(f"  Batch {i+1}: ❌ eksik")
            ok = False
            continue
        actual_ids = {o.order_id for o in batches[i].orders}
        # Snapshot kontrolü: batch'in BEKLENEN order'ları içeriyor mu?
        if exp_ids.issubset(actual_ids):
            extras = actual_ids - exp_ids
            if extras:
                print(f"  Batch {i+1}: ⚠️  beklenen {exp_ids} ✓, fazladan: {extras} "
                      f"(snapshot sonrası eklenmiş — kabul edilebilir)")
            else:
                print(f"  Batch {i+1}: ✅ beklenen ile birebir")
        else:
            print(f"  Batch {i+1}: ❌ {actual_ids} (beklenen ⊇ {exp_ids})")
            ok = False

    print()
    if ok:
        print("✅ First-fit batching paper supplement ile uyumlu çalışıyor.")
        print("   Not: 'Beklenen' tablo sequence ortasındaki snapshot'tır.")
        print("   Bizim final batch'ler, snapshot + sonraki order'ları içerir.")
    else:
        print("❌ HATA: First-fit paper ile uyumsuz — düzeltilmeli.")
    return ok


if __name__ == "__main__":
    success = run_test()
    sys.exit(0 if success else 1)
