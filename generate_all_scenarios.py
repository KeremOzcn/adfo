"""
generate_all_scenarios.py
==========================
Paper Appendix H'deki 35 senaryonun hepsini üretir.

Her (N_maxol, A_maxol) kombinasyonu için ayrı sipariş dosyaları üretilir.
Depo düzeni ve item metadata tüm kombinasyonlar için ortaktır.

Çalıştır:
    python generate_all_scenarios.py

Çıktı dizinleri:
    data/                    # mevcut (N_maxol=2, A_maxol=6)
    data_2_2/                # N_maxol=2, A_maxol=2
    data_2_10/               # N_maxol=2, A_maxol=10
    data_6_2/                # N_maxol=6, A_maxol=2
    ...
"""

import sys
import os
import json
import shutil
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Generator fonksiyonlarını import et
sys.path.insert(0, str(Path(__file__).parent.parent))

import importlib.util

def load_generator():
    spec = importlib.util.spec_from_file_location(
        "generator",
        str(Path(__file__).parent.parent / "warehouse_dataset_generator.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ════════════════════════════════════════════════════════════════════════════
# SENARYO LİSTESİ
# ════════════════════════════════════════════════════════════════════════════

# (N_maxol, A_maxol) kombinasyonları
OL_COMBOS = [
    (2,  2),   # 50_2_2 hariç ama diğer K'lar için üretelim
    (2,  6),   # elimizde var
    (2,  10),
    (6,  2),
    (6,  6),
    (6,  10),
    (10, 2),
    (10, 6),
    (10, 10),
]

# Paper'daki K değerleri (sipariş sayısı)
K_VALUES = [50, 100, 150, 200]

# Hariç tutulan senaryo (paper'da yok)
EXCLUDED = {(50, 2, 2)}

SEED = 42


# ════════════════════════════════════════════════════════════════════════════
# TEK (N_maxol, A_maxol) KOMBİNASYONU İÇİN SİPARİŞ ÜRETİCİ
# ════════════════════════════════════════════════════════════════════════════

def generate_orders_for_combo(n_maxol: int, a_maxol: int,
                               data_dir: str,
                               base_data_dir: str = "data") -> None:
    """
    Belirli bir (N_maxol, A_maxol) kombinasyonu için sipariş dosyaları üret.
    Depo düzeni ve item metadata base_data_dir'den kopyalanır.
    """
    import random

    Path(data_dir).mkdir(exist_ok=True)

    # Ortak dosyaları kopyala (depo + item metadata)
    for fname in ['warehouse_layout.json', 'items_metadata.json',
                  'items_scenario1.json', 'items_scenario2.json',
                  'location_class_A.json', 'location_class_B.json',
                  'location_class_C.json', 'summary.json']:
        src = Path(base_data_dir) / fname
        dst = Path(data_dir) / fname
        if src.exists() and not dst.exists():
            shutil.copy(src, dst)

    # Item ağırlıklarını yükle
    with open(Path(base_data_dir) / 'items_metadata.json') as f:
        items_data = json.load(f)
    item_weights = np.array([it['weight_WU'] for it in items_data['items']])
    item_locations = np.array([it['initial_location'] for it in items_data['items']])
    num_items = len(item_weights)

    # Her iki senaryo, her test periyodu, her alt-periyot için sipariş üret
    num_warmup = 12
    num_test   = 9
    num_sub    = 20
    picker_cap = 100.0

    for scenario in [1, 2]:
        with open(Path(base_data_dir) / f'items_scenario{scenario}.json') as f:
            scen_data = json.load(f)
        demand_matrix = np.array(scen_data['demand_matrix'])

        for t_idx in range(num_warmup, num_warmup + num_test):
            period = t_idx - num_warmup + 1
            item_ol = demand_matrix[:, t_idx]

            for sub in range(num_sub):
                out_path = (Path(data_dir) /
                           f"orders_s{scenario}_period{period:02d}_sub{sub+1:02d}.json")
                if out_path.exists():
                    continue

                rng = np.random.default_rng(SEED + scenario * 10000 + t_idx * 100 + sub)
                local_random = random.Random(SEED + scenario * 10000 + t_idx * 100 + sub)

                # Bu alt-periyoda düşen orderline sayıları
                subperiod_item_ol = np.zeros(num_items, dtype=int)
                for m in range(num_items):
                    total = int(item_ol[m])
                    if total <= 0:
                        continue
                    base  = total // num_sub
                    extra = total % num_sub
                    subperiod_item_ol[m] = base + (1 if sub < extra else 0)

                total_ol = int(subperiod_item_ol.sum())
                if total_ol == 0:
                    order_data = {
                        'scenario': scenario, 'period': period,
                        'subperiod': sub + 1, 'num_orders': 0, 'orders': []
                    }
                    with open(out_path, 'w') as f:
                        json.dump(order_data, f)
                    continue

                # Item havuzu
                item_pool = []
                for m in range(num_items):
                    item_pool.extend([m] * int(subperiod_item_ol[m]))
                rng.shuffle(item_pool)

                # Siparişler oluştur
                orders = []
                remaining = total_ol

                while remaining > 0:
                    n_ol = local_random.randint(1, n_maxol)
                    n_ol = min(n_ol, remaining)

                    order_items = set()
                    orderlines  = []
                    total_weight = 0.0
                    added = 0

                    for _ in range(n_ol * 3):  # fazladan deneme
                        if added >= n_ol or not item_pool:
                            break
                        m = item_pool[0] if item_pool else None
                        if m is None:
                            break
                        if m not in order_items:
                            qty    = local_random.randint(1, a_maxol)
                            weight = float(item_weights[m]) * qty
                            if total_weight + weight <= picker_cap:
                                item_pool.pop(0)
                                order_items.add(m)
                                orderlines.append({
                                    'item': int(m),
                                    'quantity': qty,
                                    'location': int(item_locations[m]),
                                    'weight': round(weight, 3)
                                })
                                total_weight += weight
                                added += 1
                        else:
                            # Aynı item → sona at
                            item_pool.pop(0)
                            item_pool.append(m)

                    if orderlines:
                        orders.append({
                            'order_id':      len(orders),
                            'num_orderlines': len(orderlines),
                            'total_weight':   round(total_weight, 3),
                            'orderlines':     orderlines
                        })
                    remaining -= n_ol

                order_data = {
                    'scenario':    scenario,
                    'period':      period,
                    'subperiod':   sub + 1,
                    'num_orders':  len(orders),
                    'orders':      orders
                }
                with open(out_path, 'w') as f:
                    json.dump(order_data, f)

    print(f"  ✓ {data_dir} tamamlandı")


# ════════════════════════════════════════════════════════════════════════════
# ANA
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import time

    base = "data"  # mevcut dataset dizini

    if not Path(base).exists():
        print(f"HATA: {base}/ dizini bulunamadı.")
        print("Önce warehouse_dataset_generator.py çalıştırın.")
        sys.exit(1)

    # (2,6) zaten var, diğerlerini üret
    combos_to_generate = [c for c in OL_COMBOS if c != (2, 6)]

    print(f"Üretilecek kombinasyon: {len(combos_to_generate)}")
    print(f"Her biri: 2 senaryo × 9 periyot × 20 alt-periyot = 360 dosya")
    est_min = len(combos_to_generate) * 360 * 0.05 / 60
    print(f"Tahmini süre: ~{est_min:.0f} dakika")
    print()

    t0 = time.perf_counter()

    for n_maxol, a_maxol in combos_to_generate:
        dir_name = f"data_{n_maxol}_{a_maxol}"
        print(f"Üretiliyor: N_maxol={n_maxol}, A_maxol={a_maxol} → {dir_name}/")
        generate_orders_for_combo(n_maxol, a_maxol, dir_name, base)

    elapsed = (time.perf_counter() - t0) / 60
    print(f"\nToplam süre: {elapsed:.1f} dakika")
    print(f"Üretilen dizinler: {[f'data_{n}_{a}' for n,a in combos_to_generate]}")
    print()
    print("Şimdi run_paper_scenarios.py ile 35 senaryoyu koşturabilirsiniz:")
    print("  python run_paper_scenarios.py --n 40")
