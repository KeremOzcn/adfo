"""
benchmarks/multi_instance.py
============================
Paper Tab.1-10 tarzı çoklu instance koşumu.

40 farklı seed → her biri için aynı problem boyutunda
SOP / FCFS / DEPSO / RBRS-AE koşturulur.
Ortalama, std dev, min, max raporlanır.

Çalıştır:
    python -m benchmarks.multi_instance
    python -m benchmarks.multi_instance --n 10 --orders 50 --depso-iter 200
"""

from __future__ import annotations

import argparse
import json
import time
import sys
import math
from pathlib import Path
from dataclasses import dataclass, field, asdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_loader import DataLoader
from core.warehouse import Warehouse
from benchmarks.sop import SOP
from benchmarks.fcfs import FCFS
from algorithms.depso import DEPSO
from algorithms.rbrs_ae import RBRS_AE


# ════════════════════════════════════════════════════════════════════════════
# VERİ SINIFLARI
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class InstanceResult:
    instance_id: int
    seed: int
    scenario: int
    num_orders: int
    algorithm: str
    travel_distance: float
    runtime_seconds: float
    iterations_used: int


@dataclass
class AlgorithmStats:
    algorithm: str
    n: int
    mean_td: float
    std_td: float
    min_td: float
    max_td: float
    mean_runtime: float
    vs_sop_pct: float      # ortalama % fark vs SOP
    vs_fcfs_pct: float     # ortalama % fark vs FCFS


# ════════════════════════════════════════════════════════════════════════════
# YARDIMCILAR
# ════════════════════════════════════════════════════════════════════════════

def _mean(vals): return sum(vals) / len(vals) if vals else 0.0
def _std(vals):
    if len(vals) < 2: return 0.0
    m = _mean(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))


def _print_stats(stats_list: list[AlgorithmStats], baseline_name: str = "SOP"):
    header = (f"{'Algoritma':<12} {'Ort TD':>10} {'Std TD':>8} "
              f"{'Min TD':>8} {'Max TD':>8} {'Ort Süre':>10} "
              f"{'vs SOP':>8} {'vs FCFS':>8}")
    print(header)
    print("-" * len(header))
    for s in stats_list:
        vs_sop  = f"{s.vs_sop_pct:+.1f}%"  if s.vs_sop_pct  != 0 else "—"
        vs_fcfs = f"{s.vs_fcfs_pct:+.1f}%"  if s.vs_fcfs_pct != 0 else "—"
        print(f"{s.algorithm:<12} {s.mean_td:>10.1f} {s.std_td:>8.1f} "
              f"{s.min_td:>8.1f} {s.max_td:>8.1f} {s.mean_runtime:>10.2f}s "
              f"{vs_sop:>8} {vs_fcfs:>8}")


# ════════════════════════════════════════════════════════════════════════════
# ANA KOŞUM FONKSİYONU
# ════════════════════════════════════════════════════════════════════════════

def run_multi_instance(
    n_instances: int = 40,
    num_orders: int = 50,
    scenario: int = 1,
    period: int = 1,
    depso_iter: int = 500,
    depso_particles: int = 5,
    rbrs_iter: int = 100,
    verbose: bool = True,
    save_results: bool = True,
    output_path: str = "results/multi_instance.json",
) -> list[AlgorithmStats]:
    """
    Paper '50_2_6' senaryosu gibi:
    - Aynı period/subperiod havuzundan siparişler çekilir
    - Her instance için farklı seed ile shuffle yapılır
    - num_orders kadar sipariş alınır
    - 40 instance × 4 algoritma
    """
    loader = DataLoader()
    wh     = Warehouse()

    all_results: list[InstanceResult] = []

    # Tüm periyot siparişlerini bir havuza topla (20 alt-periyot birleşik)
    all_orders_pool = []
    for sub in range(1, 21):
        try:
            orders = loader.load_orders(scenario, period, sub).orders
            all_orders_pool.extend(orders)
        except FileNotFoundError:
            pass

    if verbose:
        print(f"Havuz boyutu: {len(all_orders_pool)} sipariş")
        print(f"Her instance: {num_orders} sipariş (rastgele seçim)")

    t_start = time.perf_counter()

    for inst_id in range(n_instances):
        seed = inst_id * 7 + 42

        # Her instance için aynı havuzdan farklı şekilde karıştır
        import random
        rng_inst = random.Random(seed)
        shuffled = all_orders_pool[:]
        rng_inst.shuffle(shuffled)
        orders = shuffled[:num_orders]

        if len(orders) < 5:
            continue

        if verbose:
            elapsed = time.perf_counter() - t_start
            print(f"\nInstance {inst_id+1:2d}/{n_instances} "
                  f"(seed={seed}, {len(orders)} sipariş) "
                  f"[{elapsed:.0f}s geçti]")

        algos = [
            ("SOP",     SOP()),
            ("FCFS",    FCFS()),
            ("DEPSO",   DEPSO(num_iterations=depso_iter,
                              num_particles=depso_particles, seed=seed)),
            ("RBRS-AE", RBRS_AE(max_iterations=rbrs_iter, seed=seed)),
        ]

        for algo_name, algo in algos:
            sol = algo.solve(orders, wh)
            result = InstanceResult(
                instance_id=inst_id,
                seed=seed,
                scenario=scenario,
                num_orders=len(orders),
                algorithm=algo_name,
                travel_distance=sol.total_travel_distance,
                runtime_seconds=sol.runtime_seconds,
                iterations_used=sol.iterations_used,
            )
            all_results.append(result)

            if verbose:
                print(f"  {algo_name:<10}: {sol.total_travel_distance:7.1f} LU  "
                      f"{sol.runtime_seconds:5.1f}s")

    # ── İstatistik ────────────────────────────────────────────────
    algo_names = ["SOP", "FCFS", "DEPSO", "RBRS-AE"]
    stats_by_algo: dict[str, list[float]] = {a: [] for a in algo_names}
    runtimes: dict[str, list[float]]      = {a: [] for a in algo_names}

    instance_results: dict[int, dict[str, float]] = {}
    for r in all_results:
        instance_results.setdefault(r.instance_id, {})[r.algorithm] = r.travel_distance
        stats_by_algo[r.algorithm].append(r.travel_distance)
        runtimes[r.algorithm].append(r.runtime_seconds)

    vs_sop_by_algo:  dict[str, list[float]] = {a: [] for a in algo_names}
    vs_fcfs_by_algo: dict[str, list[float]] = {a: [] for a in algo_names}

    for inst_id, td_map in instance_results.items():
        sop_td  = td_map.get("SOP",  1.0)
        fcfs_td = td_map.get("FCFS", 1.0)
        for algo_name in algo_names:
            if algo_name not in td_map:
                continue
            td = td_map[algo_name]
            if sop_td > 0:
                vs_sop_by_algo[algo_name].append(
                    (td - sop_td) / sop_td * 100)
            if fcfs_td > 0:
                vs_fcfs_by_algo[algo_name].append(
                    (td - fcfs_td) / fcfs_td * 100)

    stats_list: list[AlgorithmStats] = []
    for algo_name in algo_names:
        tds = stats_by_algo[algo_name]
        if not tds:
            continue
        stats_list.append(AlgorithmStats(
            algorithm=algo_name,
            n=len(tds),
            mean_td=_mean(tds),
            std_td=_std(tds),
            min_td=min(tds),
            max_td=max(tds),
            mean_runtime=_mean(runtimes[algo_name]),
            vs_sop_pct=_mean(vs_sop_by_algo[algo_name])
                       if vs_sop_by_algo[algo_name] else 0.0,
            vs_fcfs_pct=_mean(vs_fcfs_by_algo[algo_name])
                        if vs_fcfs_by_algo[algo_name] else 0.0,
        ))

    # ── Kaydet ───────────────────────────────────────────────────
    if save_results:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        data = {
            'config': {
                'n_instances': n_instances,
                'num_orders': num_orders,
                'scenario': scenario,
                'period': period,
                'depso_iter': depso_iter,
                'depso_particles': depso_particles,
                'rbrs_iter': rbrs_iter,
                'paper_scenario': f"{num_orders}_2_6",
            },
            'stats': [asdict(s) for s in stats_list],
            'raw_results': [asdict(r) for r in all_results],
        }
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\n✓ Sonuçlar kaydedildi: {output_path}")

    return stats_list


# ════════════════════════════════════════════════════════════════════════════
# RAPOR YAZICI
# ════════════════════════════════════════════════════════════════════════════

def print_report(stats_list: list[AlgorithmStats],
                 n_instances: int, num_orders: int):
    print()
    print("=" * 75)
    print(f"ÇOKLU INSTANCE SONUÇLARI — {n_instances} instance, {num_orders} sipariş")
    print("=" * 75)
    _print_stats(stats_list)
    print()

    # Paper hedefleriyle karşılaştır
    depso = next((s for s in stats_list if s.algorithm == "DEPSO"), None)
    rbrs  = next((s for s in stats_list if s.algorithm == "RBRS-AE"), None)

    if depso:
        print("Paper Hedefleri vs Gerçekleşen:")
        print(f"  DEPSO vs SOP:  {depso.vs_sop_pct:+.2f}%  (paper: ~-88%)")
        print(f"  DEPSO vs FCFS: {depso.vs_fcfs_pct:+.2f}%  (paper: ~-40%)")

    if rbrs and depso:
        diff = (rbrs.mean_td - depso.mean_td) / depso.mean_td * 100
        speedup = depso.mean_runtime / max(rbrs.mean_runtime, 0.01)
        print()
        print(f"  RBRS-AE vs DEPSO: {diff:+.2f}% TD fark, {speedup:.1f}x daha hızlı")
    print("=" * 75)


# ════════════════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Çoklu instance koşumu")
    parser.add_argument("--n", type=int, default=40, help="Instance sayısı")
    parser.add_argument("--orders", type=int, default=50, help="Sipariş sayısı")
    parser.add_argument("--scenario", type=int, default=1, choices=[1, 2])
    parser.add_argument("--depso-iter", type=int, default=500)
    parser.add_argument("--rbrs-iter", type=int, default=100)
    parser.add_argument("--quick", action="store_true",
                        help="Hızlı test: 10 instance, 30 sipariş, 100 iter")
    args = parser.parse_args()

    if args.quick:
        n, orders, d_iter = 10, 30, 100
    else:
        n, orders, d_iter = args.n, args.orders, args.depso_iter

    print(f"Başlatılıyor: {n} instance × {orders} sipariş × DEPSO({d_iter} iter)")
    t0 = time.perf_counter()

    stats = run_multi_instance(
        n_instances=n,
        num_orders=orders,
        scenario=args.scenario,
        depso_iter=d_iter,
        rbrs_iter=args.rbrs_iter,
        verbose=True,
    )

    print_report(stats, n, orders)
    print(f"\nToplam süre: {time.perf_counter() - t0:.0f}s")
