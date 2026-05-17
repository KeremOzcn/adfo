"""
run_paper_scenarios.py
=======================
Paper Appendix H'deki 35 senaryoyu koşturur.

Önce: python generate_all_scenarios.py  (dataset üretimi)
Sonra: python run_paper_scenarios.py    (koşum)

Çalıştır:
    python run_paper_scenarios.py --quick        # 5 inst, sadece *_2_6 (~15 dk)
    python run_paper_scenarios.py --n 40         # tam 35 senaryo (~4-20 saat)
    python run_paper_scenarios.py --combo 2_6    # sadece N_maxol=2, A_maxol=6
"""

import argparse
import json
import math
import time
import random
import sys
from pathlib import Path
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent))

from core.data_loader import DataLoader
from core.warehouse import Warehouse
from benchmarks.sop import SOP
from benchmarks.fcfs import FCFS
from algorithms.depso import DEPSO
from algorithms.rbrs_ae import RBRS_AE


# ════════════════════════════════════════════════════════════════════════════
# PAPER APPENDIX H REFERANS DEĞERLERİ (Tüm 35 senaryo)
# ════════════════════════════════════════════════════════════════════════════

PAPER_RESULTS = {
    # 50 sipariş
    '50_2_6':   {'vs_sop': -88.52, 'vs_fcfs': -38.98, 'vs_savings': -30.03, 'runtime': 23.96},
    '50_2_10':  {'vs_sop': -87.13, 'vs_fcfs': -44.00, 'vs_savings': -33.36, 'runtime': 21.28},
    '50_6_2':   {'vs_sop': -87.36, 'vs_fcfs': -30.74, 'vs_savings': -28.35, 'runtime': 74.15},
    '50_6_6':   {'vs_sop': -81.54, 'vs_fcfs': -41.09, 'vs_savings': -35.92, 'runtime': 42.79},
    '50_6_10':  {'vs_sop': -77.49, 'vs_fcfs': -44.20, 'vs_savings': -36.31, 'runtime': 38.25},
    '50_10_2':  {'vs_sop': -84.83, 'vs_fcfs': -28.61, 'vs_savings': -25.90, 'runtime': 108.77},
    '50_10_6':  {'vs_sop': -76.61, 'vs_fcfs': -38.75, 'vs_savings': -32.60, 'runtime': 63.93},
    '50_10_10': {'vs_sop': -70.60, 'vs_fcfs': -42.37, 'vs_savings': -33.87, 'runtime': 57.21},
    # 100 sipariş
    '100_2_2':  {'vs_sop': -92.74, 'vs_fcfs': -36.46, 'vs_savings': -26.29, 'runtime': 59.56},
    '100_2_6':  {'vs_sop': -90.79, 'vs_fcfs': -47.77, 'vs_savings': -34.77, 'runtime': 35.69},
    '100_2_10': {'vs_sop': -88.63, 'vs_fcfs': -51.33, 'vs_savings': -38.24, 'runtime': 30.50},
    '100_6_2':  {'vs_sop': -89.20, 'vs_fcfs': -30.78, 'vs_savings': -26.55, 'runtime': 107.80},
    '100_6_6':  {'vs_sop': -82.77, 'vs_fcfs': -42.66, 'vs_savings': -35.36, 'runtime': 63.73},
    '100_6_10': {'vs_sop': -78.51, 'vs_fcfs': -45.74, 'vs_savings': -36.43, 'runtime': 58.80},
    '100_10_2': {'vs_sop': -86.23, 'vs_fcfs': -29.22, 'vs_savings': -26.40, 'runtime': 146.50},
    '100_10_6': {'vs_sop': -77.36, 'vs_fcfs': -41.29, 'vs_savings': -33.56, 'runtime': 91.49},
    '100_10_10':{'vs_sop': -71.25, 'vs_fcfs': -44.12, 'vs_savings': -33.65, 'runtime': 88.89},
    # 150 sipariş
    '150_2_2':  {'vs_sop': -94.22, 'vs_fcfs': -34.15, 'vs_savings': -24.76, 'runtime': 78.85},
    '150_2_6':  {'vs_sop': -91.23, 'vs_fcfs': -50.26, 'vs_savings': -34.75, 'runtime': 44.98},
    '150_2_10': {'vs_sop': -89.25, 'vs_fcfs': -51.97, 'vs_savings': -35.80, 'runtime': 40.96},
    '150_6_2':  {'vs_sop': -89.34, 'vs_fcfs': -32.23, 'vs_savings': -28.04, 'runtime': 117.91},
    '150_6_6':  {'vs_sop': -82.89, 'vs_fcfs': -43.43, 'vs_savings': -35.08, 'runtime': 79.13},
    '150_6_10': {'vs_sop': -78.45, 'vs_fcfs': -46.16, 'vs_savings': -35.84, 'runtime': 71.21},
    '150_10_2': {'vs_sop': -86.22, 'vs_fcfs': -29.21, 'vs_savings': -24.83, 'runtime': 185.54},
    '150_10_6': {'vs_sop': -77.32, 'vs_fcfs': -40.74, 'vs_savings': -32.25, 'runtime': 114.83},
    '150_10_10':{'vs_sop': -71.41, 'vs_fcfs': -44.38, 'vs_savings': -32.15, 'runtime': 117.10},
    # 200 sipariş
    '200_2_2':  {'vs_sop': -94.26, 'vs_fcfs': -41.36, 'vs_savings': -26.89, 'runtime': 82.87},
    '200_2_6':  {'vs_sop': -91.54, 'vs_fcfs': -51.42, 'vs_savings': -33.72, 'runtime': 52.11},
    '200_2_10': {'vs_sop': -89.26, 'vs_fcfs': -53.33, 'vs_savings': -35.29, 'runtime': 50.53},
    '200_6_2':  {'vs_sop': -89.61, 'vs_fcfs': -31.43, 'vs_savings': -26.41, 'runtime': 138.78},
    '200_6_6':  {'vs_sop': -82.58, 'vs_fcfs': -41.96, 'vs_savings': -33.17, 'runtime': 97.02},
    '200_6_10': {'vs_sop': -78.35, 'vs_fcfs': -45.24, 'vs_savings': -34.01, 'runtime': 91.46},
    '200_10_2': {'vs_sop': -86.11, 'vs_fcfs': -28.26, 'vs_savings': -24.02, 'runtime': 226.18},
    '200_10_6': {'vs_sop': -77.21, 'vs_fcfs': -40.34, 'vs_savings': -31.02, 'runtime': 138.90},
    '200_10_10':{'vs_sop': -71.57, 'vs_fcfs': -43.94, 'vs_savings': -31.79, 'runtime': 138.01},
}

# Data dizini map: (n_maxol, a_maxol) → dizin adı
DATA_DIR_MAP = {
    (2,  2):  'data_2_2',
    (2,  6):  'data',        # mevcut
    (2,  10): 'data_2_10',
    (6,  2):  'data_6_2',
    (6,  6):  'data_6_6',
    (6,  10): 'data_6_10',
    (10, 2):  'data_10_2',
    (10, 6):  'data_10_6',
    (10, 10): 'data_10_10',
}

# Tüm 35 senaryo
ALL_SCENARIOS = []
for k in [50, 100, 150, 200]:
    for n_maxol in [2, 6, 10]:
        for a_maxol in [2, 6, 10]:
            name = f"{k}_{n_maxol}_{a_maxol}"
            if name == '50_2_2':
                continue  # paper'da yok
            ALL_SCENARIOS.append({
                'name':       name,
                'num_orders': k,
                'n_maxol':    n_maxol,
                'a_maxol':    a_maxol,
                'data_dir':   DATA_DIR_MAP[(n_maxol, a_maxol)],
            })


# ════════════════════════════════════════════════════════════════════════════
# YARDIMCILAR
# ════════════════════════════════════════════════════════════════════════════

def _mean(vals): return sum(vals) / len(vals) if vals else 0.0
def _std(vals):
    if len(vals) < 2: return 0.0
    m = _mean(vals)
    return math.sqrt(sum((v - m) ** 2 for v in vals) / len(vals))


def run_scenario(scenario: dict, n_instances: int,
                 depso_iter: int, rbrs_iter: int,
                 wh: Warehouse,
                 verbose: bool = True) -> dict:
    """Tek bir senaryoyu n_instances kez koştur."""

    name       = scenario['name']
    num_orders = scenario['num_orders']
    data_dir   = scenario.get('data_dir', 'data')

    # Bu senaryo için DataLoader oluştur
    data_path = Path(__file__).parent / data_dir
    if not data_path.exists():
        print(f"  ⚠ {data_dir}/ dizini yok — önce generate_all_scenarios.py çalıştırın")
        return {'scenario': name, 'num_orders': num_orders,
                'n_instances': 0, 'stats': {}, 'skipped': True}

    loader = DataLoader(data_path)

    # Tüm periyot siparişlerini havuza topla
    pool = []
    for sub in range(1, 21):
        try:
            pool.extend(loader.load_orders(1, 1, sub).orders)
        except FileNotFoundError:
            pass

    if len(pool) < num_orders:
        print(f"  ⚠ {name}: havuzda yeterli sipariş yok ({len(pool)} < {num_orders})")
        return {'scenario': name, 'num_orders': num_orders,
                'n_instances': 0, 'stats': {}, 'skipped': True}

    if verbose:
        print(f"\n{'='*60}")
        print(f"Senaryo: {name}  ({num_orders} sipariş, {n_instances} instance)")
        if name in PAPER_RESULTS:
            print(f"Paper hedefi: DEPSO vs SOP = {PAPER_RESULTS[name]['vs_sop']}%")
        print(f"{'='*60}")

    results = {a: {'td': [], 'rt': []} for a in ['SOP', 'FCFS', 'DEPSO', 'RBRS-AE']}
    t_start = time.perf_counter()

    for inst_id in range(n_instances):
        seed = inst_id * 7 + 42
        rng  = random.Random(seed)
        shuffled = pool[:]
        rng.shuffle(shuffled)
        orders = shuffled[:num_orders]

        if len(orders) < 5:
            continue

        if verbose:
            elapsed = time.perf_counter() - t_start
            print(f"  Instance {inst_id+1:2d}/{n_instances} "
                  f"[{elapsed:.0f}s]  ", end='', flush=True)

        algos = [
            ('SOP',     SOP()),
            ('FCFS',    FCFS()),
            ('DEPSO',   DEPSO(num_iterations=depso_iter,
                              num_particles=5, seed=seed)),
            ('RBRS-AE', RBRS_AE(max_iterations=rbrs_iter, seed=seed)),
        ]

        line = ""
        for algo_name, algo in algos:
            sol = algo.solve(orders, wh)
            results[algo_name]['td'].append(sol.total_travel_distance)
            results[algo_name]['rt'].append(sol.runtime_seconds)
            line += f"{algo_name}={sol.total_travel_distance:.0f} "

        if verbose:
            print(line)

    # İstatistik
    sop_tds  = results['SOP']['td']
    fcfs_tds = results['FCFS']['td']

    stats = {}
    for algo_name in ['SOP', 'FCFS', 'DEPSO', 'RBRS-AE']:
        tds = results[algo_name]['td']
        rts = results[algo_name]['rt']

        vs_sop_list  = [(t - s) / s * 100 for t, s in zip(tds, sop_tds)  if s > 0]
        vs_fcfs_list = [(t - f) / f * 100 for t, f in zip(tds, fcfs_tds) if f > 0]

        stats[algo_name] = {
            'mean_td':      _mean(tds),
            'std_td':       _std(tds),
            'min_td':       min(tds) if tds else 0,
            'max_td':       max(tds) if tds else 0,
            'mean_rt':      _mean(rts),
            'vs_sop_mean':  _mean(vs_sop_list),
            'vs_sop_min':   min(vs_sop_list)  if vs_sop_list  else 0,
            'vs_sop_max':   max(vs_sop_list)  if vs_sop_list  else 0,
            'vs_fcfs_mean': _mean(vs_fcfs_list),
        }

    return {'scenario': name, 'num_orders': num_orders,
            'n_instances': n_instances, 'stats': stats}


# ════════════════════════════════════════════════════════════════════════════
# RAPOR
# ════════════════════════════════════════════════════════════════════════════

def print_report(all_scenario_results: list[dict]) -> str:
    lines = []
    lines.append("\n" + "="*75)
    lines.append("PAPER APPENDIX H KARŞILAŞTIRMASI")
    lines.append("="*75)

    # DEPSO vs SOP tablosu (paper formatı)
    lines.append("\nDEPSO vs SOP (Ø %):")
    lines.append(f"{'Senaryo':<12} {'Bizim':>10} {'Paper':>10} {'Fark':>8} {'RBRS-AE':>10}")
    lines.append("-" * 55)

    for res in all_scenario_results:
        name   = res['scenario']
        depso  = res['stats']['DEPSO']['vs_sop_mean']
        rbrs   = res['stats']['RBRS-AE']['vs_sop_mean']
        paper  = PAPER_RESULTS[name]['vs_sop']
        diff   = depso - paper
        ok     = "✅" if abs(diff) < 5 else "⚠️"
        lines.append(f"{name:<12} {depso:>10.2f}% {paper:>10.2f}% "
                     f"{diff:>+8.2f}% {rbrs:>10.2f}%  {ok}")

    lines.append("\nDEPSO vs FCFS (Ø %):")
    lines.append(f"{'Senaryo':<12} {'Bizim':>10} {'Paper':>10} {'Fark':>8} {'RBRS-AE':>10}")
    lines.append("-" * 55)

    for res in all_scenario_results:
        name  = res['scenario']
        depso = res['stats']['DEPSO']['vs_fcfs_mean']
        rbrs  = res['stats']['RBRS-AE']['vs_fcfs_mean']
        paper = PAPER_RESULTS[name]['vs_fcfs']
        diff  = depso - paper
        ok    = "✅" if abs(diff) < 8 else "⚠️"
        lines.append(f"{name:<12} {depso:>10.2f}% {paper:>10.2f}% "
                     f"{diff:>+8.2f}% {rbrs:>10.2f}%  {ok}")

    lines.append("\nRuntime (saniye):")
    lines.append(f"{'Senaryo':<12} {'DEPSO':>10} {'Paper':>10} {'RBRS-AE':>10}")
    lines.append("-" * 45)

    for res in all_scenario_results:
        name  = res['scenario']
        depso = res['stats']['DEPSO']['mean_rt']
        rbrs  = res['stats']['RBRS-AE']['mean_rt']
        paper = PAPER_RESULTS[name]['runtime']
        lines.append(f"{name:<12} {depso:>10.2f}s {paper:>10.2f}s {rbrs:>10.2f}s")

    lines.append("="*75)
    report = "\n".join(lines)
    print(report)
    return report


# ════════════════════════════════════════════════════════════════════════════
# ANA
# ════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true",
                        help="5 instance, sadece *_2_6 senaryoları (~30 dk)")
    parser.add_argument("--n", type=int, default=40,
                        help="Instance sayısı (default: 40)")
    parser.add_argument("--depso-iter", type=int, default=500)
    parser.add_argument("--rbrs-iter",  type=int, default=100)
    parser.add_argument("--combo", type=str, default="all",
                        help="'all', '2_6' veya '2_6,6_6' gibi N_maxol_A_maxol")
    args = parser.parse_args()

    if args.quick:
        n_inst, d_iter = 5, 100
        # Sadece _2_6 senaryoları (elimizde var)
        scenarios = [s for s in ALL_SCENARIOS if s['data_dir'] == 'data']
    else:
        n_inst, d_iter = args.n, args.depso_iter
        if args.combo == "all":
            scenarios = ALL_SCENARIOS
        else:
            combos = args.combo.split(",")
            scenarios = [s for s in ALL_SCENARIOS
                        if f"{s['n_maxol']}_{s['a_maxol']}" in combos]

    wh = Warehouse()

    print(f"Koşulacak senaryo sayısı: {len(scenarios)}")
    print(f"Instance sayısı: {n_inst}")
    print(f"DEPSO iterasyon: {d_iter}")

    # Tahmini süre
    time_per_order = 0.028
    est = sum(s['num_orders'] * time_per_order * d_iter * n_inst / 60
              for s in scenarios)
    print(f"Tahmini süre: ~{est:.0f} dakika ({est/60:.1f} saat)")
    print()

    # Dataset kontrolü
    missing = set()
    for s in scenarios:
        if not Path(s['data_dir']).exists():
            missing.add(s['data_dir'])
    if missing:
        print(f"⚠ Eksik dataset dizinleri: {missing}")
        print("  Önce: python generate_all_scenarios.py")
        scenarios = [s for s in scenarios if Path(s['data_dir']).exists()]
        print(f"  Mevcut {len(scenarios)} senaryo ile devam ediliyor...")
    print()

    t0 = time.perf_counter()
    all_results = []

    for scenario in scenarios:
        result = run_scenario(
            scenario, n_inst, d_iter, args.rbrs_iter,
            wh, verbose=True
        )
        all_results.append(result)

        # Ara rapor kaydet (uzun koşumda kayıp olmasın)
        Path("results").mkdir(exist_ok=True)
        with open("results/paper_scenarios_partial.json", 'w') as f:
            json.dump({'scenarios': all_results,
                       'paper_reference': PAPER_RESULTS}, f, indent=2)

    # Final rapor
    report_text = print_report(all_results)

    Path("results").mkdir(exist_ok=True)
    out_json = "results/paper_scenarios.json"
    out_md   = "results/paper_scenarios.md"

    with open(out_json, 'w') as f:
        json.dump({'scenarios': all_results,
                   'paper_reference': PAPER_RESULTS}, f, indent=2)

    with open(out_md, 'w') as f:
        f.write("# Paper Appendix H Karşılaştırması\n\n")
        f.write(f"**Instance sayısı:** {n_inst}  \n")
        f.write(f"**DEPSO iterasyon:** {d_iter}  \n")
        f.write(f"**Senaryo sayısı:**  {len(all_results)}  \n\n")
        f.write("```\n" + report_text + "\n```\n")

    total = (time.perf_counter() - t0) / 60
    print(f"\nToplam süre: {total:.1f} dakika")
    print(f"JSON: {out_json}")
    print(f"MD:   {out_md}")

    with open(out_md, 'w') as f:
        f.write("# Paper Appendix H Karşılaştırması\n\n")
        f.write(f"**Instance sayısı:** {n_inst}  \n")
        f.write(f"**DEPSO iterasyon:** {d_iter}  \n\n")
        f.write("```\n" + report_text + "\n```\n")

    total = (time.perf_counter() - t0) / 60
    print(f"\nToplam süre: {total:.1f} dakika")
    print(f"JSON: {out_json}")
    print(f"MD:   {out_md}")


if __name__ == "__main__":
    main()
