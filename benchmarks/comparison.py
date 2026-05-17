"""
benchmarks/comparison.py
========================
Tüm algoritmaları aynı problem instance üzerinde koştur ve karşılaştır.

Kullanım:
    python -m benchmarks.comparison
veya
    from benchmarks.comparison import run_comparison
    results = run_comparison(orders, warehouse, algos=[...])
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_loader import Order
from algorithms.base import BatchingRoutingAlgorithm, Solution


@dataclass
class ComparisonRow:
    algorithm: str
    travel_distance_LU: float
    num_batches: int
    avg_utilization: float
    runtime_seconds: float
    vs_baseline_pct: float | None = None  # baseline'a göre fark


def run_comparison(
    orders: list[Order],
    warehouse,
    algorithms: list[BatchingRoutingAlgorithm],
    baseline_idx: int = 0,
) -> list[ComparisonRow]:
    """
    Verilen algoritmaları sırayla çalıştırır ve karşılaştırma tablosu döner.

    baseline_idx: hangi algoritmanın baseline kabul edileceği (vs_pct hesabı için)
    """
    solutions: list[Solution] = []
    rows: list[ComparisonRow] = []

    for algo in algorithms:
        print(f"  Çalıştırılıyor: {algo.name}...", end=' ', flush=True)
        t0 = time.perf_counter()
        sol = algo.solve(orders, warehouse)
        elapsed = time.perf_counter() - t0
        print(f"({elapsed:.1f}s, {sol.total_travel_distance:.1f} LU)")
        solutions.append(sol)

    baseline_td = solutions[baseline_idx].total_travel_distance

    for sol in solutions:
        pct = None
        if baseline_td > 0 and sol is not solutions[baseline_idx]:
            pct = (sol.total_travel_distance - baseline_td) / baseline_td * 100
        rows.append(ComparisonRow(
            algorithm=sol.algorithm_name,
            travel_distance_LU=sol.total_travel_distance,
            num_batches=sol.num_batches,
            avg_utilization=sol.avg_capacity_utilization,
            runtime_seconds=sol.runtime_seconds,
            vs_baseline_pct=pct,
        ))

    return rows


def print_comparison(rows: list[ComparisonRow], baseline_name: str = "baseline") -> None:
    """Karşılaştırma tablosunu güzel bas."""
    print()
    print(f"{'Algoritma':<20} {'Mesafe (LU)':>12} {'Batch':>7} "
          f"{'Doluluk':>8} {'Süre (s)':>10} {'vs ' + baseline_name:>14}")
    print("-" * 75)
    for row in rows:
        vs = f"{row.vs_baseline_pct:+.2f}%" if row.vs_baseline_pct is not None else "—"
        print(
            f"{row.algorithm:<20} "
            f"{row.travel_distance_LU:>12.1f} "
            f"{row.num_batches:>7d} "
            f"{row.avg_utilization:>8.2f} "
            f"{row.runtime_seconds:>10.2f} "
            f"{vs:>14}"
        )
    print()


if __name__ == "__main__":
    from core.data_loader import DataLoader
    from core.warehouse import Warehouse
    from benchmarks.sop import SOP
    from benchmarks.fcfs import FCFS
    from algorithms.depso import DEPSO

    loader = DataLoader()
    wh = Warehouse()

    print("=" * 75)
    print("Algoritma karşılaştırması: Senaryo 1, Periyot 1, Alt-periyot 20 (109 sipariş)")
    print("=" * 75)

    sub = loader.load_orders(1, 1, 20)
    orders = sub.orders  # 109 sipariş

    algos = [
        SOP(),
        FCFS(),
        DEPSO(num_iterations=200, seed=42),  # kısaltılmış
    ]

    rows = run_comparison(orders, wh, algos, baseline_idx=0)
    print_comparison(rows, baseline_name="SOP")

    # FCFS'e göre de göster
    print("FCFS'e göre karşılaştırma:")
    rows2 = run_comparison(orders, wh, algos, baseline_idx=1)
    print_comparison(rows2, baseline_name="FCFS")
