"""
run_experiment.py
==================
Kendi makinenizde çalıştırın:

    # Hızlı test (5 dakika)
    python run_experiment.py --quick

    # Tam koşum — paper gibi (20-40 dakika)
    python run_experiment.py --full

    # Özel
    python run_experiment.py --n 40 --orders 50 --depso-iter 500

Sonuçlar results/ klasörüne kaydedilir.
"""

import argparse
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from benchmarks.multi_instance import run_multi_instance, print_report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true",
                        help="Hızlı test: 5 instance, 30 sipariş, 100 iter (~2 dk)")
    parser.add_argument("--full", action="store_true",
                        help="Tam koşum: 40 instance, 50 sipariş, 500 iter (~40 dk)")
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--orders", type=int, default=50)
    parser.add_argument("--depso-iter", type=int, default=300)
    parser.add_argument("--rbrs-iter", type=int, default=100)
    parser.add_argument("--scenario", type=int, default=1, choices=[1, 2])
    args = parser.parse_args()

    if args.quick:
        cfg = dict(n_instances=5, num_orders=30, depso_iter=100, rbrs_iter=50)
        label = "Hızlı test"
    elif args.full:
        cfg = dict(n_instances=40, num_orders=50, depso_iter=500, rbrs_iter=100)
        label = "Tam koşum — paper '50_2_6' senaryosu (40 instance)"
    else:
        cfg = dict(n_instances=args.n, num_orders=args.orders,
                   depso_iter=args.depso_iter, rbrs_iter=args.rbrs_iter)
        label = f"Özel koşum — '{args.orders}_2_6' senaryosu"

    cfg['scenario'] = args.scenario

    print(f"\n{'='*60}")
    print(f"WAREHOUSE OPTIMIZATION — {label}")
    print(f"{'='*60}")
    print(f"  Instance sayısı:  {cfg['n_instances']}")
    print(f"  Sipariş / inst.:  {cfg['num_orders']}")
    print(f"  Senaryo:          {cfg['scenario']}")
    print(f"  DEPSO iterasyon:  {cfg['depso_iter']}")
    print(f"  RBRS-AE iterasyon:{cfg['rbrs_iter']}")
    tahmini = cfg['n_instances'] * (cfg['depso_iter'] * 0.028 + 5)
    print(f"  Tahmini süre:     ~{tahmini/60:.0f} dakika")
    print()

    t0 = time.perf_counter()
    output = f"results/experiment_s{cfg['scenario']}_{cfg['n_instances']}inst.json"

    stats = run_multi_instance(
        **cfg,
        verbose=True,
        save_results=True,
        output_path=output,
    )

    print_report(stats, cfg['n_instances'], cfg['num_orders'])
    print(f"Toplam süre: {(time.perf_counter()-t0)/60:.1f} dakika")
    print(f"Sonuçlar: {output}")


if __name__ == "__main__":
    main()
