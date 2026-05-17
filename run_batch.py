"""
run_batch.py
=============
5'er 5'er senaryo üret ve koştur.

Kullanım:
    python run_batch.py --batch 1   # senaryo 1-5
    python run_batch.py --batch 2   # senaryo 6-10
    ...
    python run_batch.py --batch 7   # senaryo 31-35

Her batch: dataset üretimi + 5 instance × 4 algoritma koşumu
Süre tahmini: ~3-5 dakika/batch (bu ortamda), ~30-60 dk (kendi makinende 40 inst)
"""

import sys
import json
import time
import random
import math
import argparse
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.warehouse import Warehouse
from core.data_loader import DataLoader
from benchmarks.sop import SOP
from benchmarks.fcfs import FCFS
from algorithms.depso import DEPSO
from algorithms.rbrs_ae import RBRS_AE


# ════════════════════════════════════════════════════════════════════════════
# 35 SENARYO LİSTESİ
# ════════════════════════════════════════════════════════════════════════════

ALL_35 = []
for k in [50, 100, 150, 200]:
    for n_maxol in [2, 6, 10]:
        for a_maxol in [2, 6, 10]:
            if k == 50 and n_maxol == 2 and a_maxol == 2:
                continue
            ALL_35.append({'k': k, 'n': n_maxol, 'a': a_maxol,
                           'name': f'{k}_{n_maxol}_{a_maxol}'})

# 7 batch × 5 senaryo = 35
BATCHES = [ALL_35[i:i+5] for i in range(0, 35, 5)]

# Paper referans değerleri (Appendix H)
PAPER = {
    '50_2_6':   -88.52, '50_2_10':  -87.13, '50_6_2':   -87.36,
    '50_6_6':   -81.54, '50_6_10':  -77.49, '50_10_2':  -84.83,
    '50_10_6':  -76.61, '50_10_10': -70.60,
    '100_2_2':  -92.74, '100_2_6':  -90.79, '100_2_10': -88.63,
    '100_6_2':  -89.20, '100_6_6':  -82.77, '100_6_10': -78.51,
    '100_10_2': -86.23, '100_10_6': -77.36, '100_10_10':-71.25,
    '150_2_2':  -94.22, '150_2_6':  -91.23, '150_2_10': -89.25,
    '150_6_2':  -89.34, '150_6_6':  -82.89, '150_6_10': -78.45,
    '150_10_2': -86.22, '150_10_6': -77.32, '150_10_10':-71.41,
    '200_2_2':  -94.26, '200_2_6':  -91.54, '200_2_10': -89.26,
    '200_6_2':  -89.61, '200_6_6':  -82.58, '200_6_10': -78.35,
    '200_10_2': -86.11, '200_10_6': -77.21, '200_10_10':-71.57,
}


# ════════════════════════════════════════════════════════════════════════════
# DATASET ÜRETİCİ (sadece sipariş dosyaları)
# ════════════════════════════════════════════════════════════════════════════

def generate_orders(n_maxol: int, a_maxol: int,
                    n_instances: int = 5,
                    seed: int = 42) -> list:
    """
    (n_maxol, a_maxol) kombinasyonu için n_instances instance üret.
    Her instance: 50 farklı sipariş seti (shuffle).
    Döndürür: [(orders_list, seed), ...] listesi
    """
    base_loader = DataLoader(Path(__file__).parent / 'data')
    items_data  = base_loader.load_items()
    item_weights  = np.array([it.weight_WU for it in items_data])
    item_locations= np.array([it.initial_location for it in items_data])
    num_items = len(item_weights)

    # Senaryo 1, periyot 1, alt-periyot 1 talebini kullan
    demand = base_loader.load_scenario_demand(1)
    item_ol = demand[:, 12]  # test periyodu 1

    picker_cap = 100.0

    all_instances = []
    for inst_id in range(n_instances):
        inst_seed = seed + inst_id * 7
        rng = np.random.default_rng(inst_seed)
        local_rng = random.Random(inst_seed)

        # Item havuzu oluştur
        item_pool = []
        for m in range(num_items):
            cnt = int(item_ol[m]) // 20  # alt-periyot payı
            item_pool.extend([m] * max(cnt, 0))
        rng.shuffle(item_pool)

        # Siparişler üret
        from core.data_loader import Order, OrderLine
        orders = []
        pool_copy = list(item_pool[:])

        while len(orders) < 500 and pool_copy:
            n_ol = local_rng.randint(1, n_maxol)
            orderlines = []
            used = set()
            total_w = 0.0

            for _ in range(n_ol * 3):
                if len(orderlines) >= n_ol or not pool_copy:
                    break
                m = pool_copy[0]
                if m not in used:
                    qty    = local_rng.randint(1, a_maxol)
                    weight = float(item_weights[m]) * qty
                    if total_w + weight <= picker_cap:
                        pool_copy.pop(0)
                        used.add(m)
                        ol = OrderLine(item=int(m), quantity=qty,
                                      location=int(item_locations[m]),
                                      weight=round(weight, 3))
                        orderlines.append(ol)
                        total_w += weight
                    else:
                        break
                else:
                    pool_copy.pop(0)

            if orderlines:
                o = Order(order_id=len(orders),
                          num_orderlines=len(orderlines),
                          total_weight=round(total_w, 3),
                          orderlines=orderlines)
                orders.append(o)

        # Shuffle
        local_rng.shuffle(orders)
        all_instances.append((orders, inst_seed))

    return all_instances


# ════════════════════════════════════════════════════════════════════════════
# TEK SENARYO KOŞUMU
# ════════════════════════════════════════════════════════════════════════════

def _mean(v): return sum(v)/len(v) if v else 0.0

def run_one_scenario(scenario: dict, n_instances: int,
                     depso_iter: int, wh: Warehouse) -> dict:
    k      = scenario['k']
    n      = scenario['n']
    a      = scenario['a']
    name   = scenario['name']
    paper  = PAPER.get(name, '?')

    print(f"\n  [{name}]  K={k}, N_maxol={n}, A_maxol={a}  "
          f"(paper DEPSO vs SOP: {paper}%)")

    # Instance'ları üret
    instances = generate_orders(n, a, n_instances)

    results = {alg: {'td': [], 'rt': []}
               for alg in ['SOP', 'FCFS', 'DEPSO', 'RBRS-AE']}

    for inst_id, (all_orders, inst_seed) in enumerate(instances):
        orders = all_orders[:k]
        if len(orders) < 5:
            continue

        algos = [
            ('SOP',     SOP()),
            ('FCFS',    FCFS()),
            ('DEPSO',   DEPSO(num_iterations=depso_iter,
                              num_particles=5, seed=inst_seed)),
            ('RBRS-AE', RBRS_AE(max_iterations=100,
                                shift_attempts=150, swap_attempts=150,
                                seed=inst_seed)),
        ]

        line_parts = []
        for alg_name, algo in algos:
            sol = algo.solve(orders, wh)
            results[alg_name]['td'].append(sol.total_travel_distance)
            results[alg_name]['rt'].append(sol.runtime_seconds)
            line_parts.append(f"{alg_name}={sol.total_travel_distance:.0f}")

        print(f"    inst {inst_id+1}: {' '.join(line_parts)}")

    # İstatistik
    sop_tds  = results['SOP']['td']
    fcfs_tds = results['FCFS']['td']
    stats = {}
    for alg in ['SOP', 'FCFS', 'DEPSO', 'RBRS-AE']:
        tds = results[alg]['td']
        rts = results[alg]['rt']
        if not tds:
            continue
        vs_sop  = [((t-s)/s*100) for t,s in zip(tds, sop_tds) if s > 0]
        vs_fcfs = [((t-f)/f*100) for t,f in zip(tds, fcfs_tds) if f > 0]
        stats[alg] = {
            'mean_td':      round(_mean(tds), 1),
            'mean_rt':      round(_mean(rts), 2),
            'vs_sop_mean':  round(_mean(vs_sop), 2),
            'vs_fcfs_mean': round(_mean(vs_fcfs), 2),
        }

    depso_vs_sop  = stats.get('DEPSO', {}).get('vs_sop_mean', 0)
    rbrs_vs_sop   = stats.get('RBRS-AE', {}).get('vs_sop_mean', 0)
    diff          = round(depso_vs_sop - paper, 2) if isinstance(paper, float) else '?'
    ok            = "✅" if isinstance(diff, float) and abs(diff) < 8 else "⚠️"

    print(f"    → DEPSO vs SOP: {depso_vs_sop:.2f}%  "
          f"(paper: {paper}%  fark: {diff}%  {ok})")
    print(f"    → RBRS-AE vs SOP: {rbrs_vs_sop:.2f}%")

    return {'scenario': name, 'k': k, 'n_maxol': n, 'a_maxol': a,
            'paper_vs_sop': paper, 'n_instances': len(instances),
            'stats': stats}


# ════════════════════════════════════════════════════════════════════════════
# RAPOR
# ════════════════════════════════════════════════════════════════════════════

def print_summary(results: list):
    print("\n" + "="*72)
    print("ÖZET TABLO — Paper Appendix H vs Bizim Sonuçlarımız")
    print("="*72)
    print(f"{'Senaryo':<12} {'DEPSO/SOP':>10} {'Paper':>10} {'Fark':>8} "
          f"{'RBRS/SOP':>10} {'Durum':>6}")
    print("-"*72)

    for r in results:
        if 'stats' not in r or 'DEPSO' not in r.get('stats', {}):
            print(f"{r['scenario']:<12} {'HATA':>10}")
            continue
        depso = r['stats']['DEPSO']['vs_sop_mean']
        rbrs  = r['stats']['RBRS-AE']['vs_sop_mean']
        paper = r['paper_vs_sop']
        diff  = round(depso - paper, 2) if isinstance(paper, float) else 0
        ok    = "✅" if abs(diff) < 8 else "⚠️"
        print(f"{r['scenario']:<12} {depso:>10.2f}% {paper:>10.2f}% "
              f"{diff:>+8.2f}% {rbrs:>10.2f}%  {ok}")

    print("="*72)


def load_all_results() -> list:
    """Tüm batch sonuçlarını birleştir."""
    all_results = []
    results_dir = Path("results")
    for i in range(1, 8):
        path = results_dir / f"batch_{i}.json"
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            all_results.extend(data.get('results', []))
    return all_results


# ════════════════════════════════════════════════════════════════════════════
# ANA
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, required=False,
                        help="Hangi batch? (1-7). Belirtilmezse özet gösterir.")
    parser.add_argument("--n", type=int, default=5,
                        help="Instance sayısı (default: 5)")
    parser.add_argument("--depso-iter", type=int, default=100,
                        help="DEPSO iterasyon (default: 100)")
    parser.add_argument("--summary", action="store_true",
                        help="Tüm batch sonuçlarını özetler")
    args = parser.parse_args()

    if args.summary or args.batch is None:
        all_res = load_all_results()
        if all_res:
            print_summary(all_res)
        else:
            print("Henüz sonuç yok. Önce batch'leri çalıştırın:")
            for i, batch in enumerate(BATCHES, 1):
                names = [s['name'] for s in batch]
                print(f"  python run_batch.py --batch {i}  "
                      f"# {', '.join(names)}")
        sys.exit(0)

    batch_idx = args.batch
    if batch_idx < 1 or batch_idx > 7:
        print("Batch 1-7 arasında olmalı!")
        sys.exit(1)

    batch = BATCHES[batch_idx - 1]
    names = [s['name'] for s in batch]

    print(f"{'='*60}")
    print(f"BATCH {batch_idx}/7: {', '.join(names)}")
    print(f"Instance: {args.n}, DEPSO iter: {args.depso_iter}")
    print(f"{'='*60}")

    wh = Warehouse()
    t0 = time.perf_counter()

    batch_results = []
    for scenario in batch:
        result = run_one_scenario(scenario, args.n, args.depso_iter, wh)
        batch_results.append(result)

    # Kaydet
    Path("results").mkdir(exist_ok=True)
    out = Path("results") / f"batch_{batch_idx}.json"
    with open(out, 'w') as f:
        json.dump({'batch': batch_idx, 'scenarios': names,
                   'n_instances': args.n, 'depso_iter': args.depso_iter,
                   'results': batch_results}, f, indent=2)

    elapsed = time.perf_counter() - t0
    print(f"\n✓ Batch {batch_idx} tamamlandı ({elapsed:.0f}s)")
    print(f"  Kayıt: {out}")

    # Özet
    print_summary(batch_results)

    # Tüm batch'ler bitti mi?
    all_res = load_all_results()
    print(f"\nToplam tamamlanan senaryo: {len(all_res)}/35")
    if len(all_res) == 35:
        print("\n🎉 35 senaryo TAMAMLANDI! Tam özet:")
        print_summary(all_res)
