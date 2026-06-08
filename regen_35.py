"""
regen_35.py
============
Regenerate results/paper_35_scenarios.md and results/paper_35_scenarios.json.

Strategy:
  - DEPSO:  run fresh from data dirs with fixed seed (inst_id * 7 + 42 + num_orders)
            -> different results across k values for the same n_maxol/a_maxol combo
  - RBRS-AE for 50-order scenarios: run fresh (~4s per instance)
  - RBRS-AE for 100/150/200-order scenarios: read from results/batch_*.json
            (RBRS init is O(n^2); 100 orders ~32s/instance, 200 orders ~95s/instance)

Run:
    python regen_35.py
"""

import json
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.data_loader import DataLoader
from core.warehouse import Warehouse
from benchmarks.sop import SOP
from benchmarks.fcfs import FCFS
from algorithms.depso import DEPSO
from algorithms.rbrs_ae import RBRS_AE

# ── paper reference values ─────────────────────────────────────────────────
PAPER = {
    '50_2_6':    -88.52, '50_2_10':   -87.13, '50_6_2':    -87.36,
    '50_6_6':    -81.54, '50_6_10':   -77.49, '50_10_2':   -84.83,
    '50_10_6':   -76.61, '50_10_10':  -70.60,
    '100_2_2':   -92.74, '100_2_6':   -90.79, '100_2_10':  -88.63,
    '100_6_2':   -89.20, '100_6_6':   -82.77, '100_6_10':  -78.51,
    '100_10_2':  -86.23, '100_10_6':  -77.36, '100_10_10': -71.25,
    '150_2_2':   -94.22, '150_2_6':   -91.23, '150_2_10':  -89.25,
    '150_6_2':   -89.34, '150_6_6':   -82.89, '150_6_10':  -78.45,
    '150_10_2':  -86.22, '150_10_6':  -77.32, '150_10_10': -71.41,
    '200_2_2':   -94.26, '200_2_6':   -91.54, '200_2_10':  -89.26,
    '200_6_2':   -89.61, '200_6_6':   -82.58, '200_6_10':  -78.35,
    '200_10_2':  -86.11, '200_10_6':  -77.21, '200_10_10': -71.57,
}

DATA_DIR_MAP = {
    (2,  2): 'data_2_2',  (2,  6): 'data',     (2, 10): 'data_2_10',
    (6,  2): 'data_6_2',  (6,  6): 'data_6_6', (6, 10): 'data_6_10',
    (10, 2): 'data_10_2', (10, 6): 'data_10_6', (10, 10): 'data_10_10',
}

ALL_35 = []
for k in [50, 100, 150, 200]:
    for n_maxol in [2, 6, 10]:
        for a_maxol in [2, 6, 10]:
            if k == 50 and n_maxol == 2 and a_maxol == 2:
                continue
            ALL_35.append({
                'name': f'{k}_{n_maxol}_{a_maxol}',
                'k': k, 'n': n_maxol, 'a': a_maxol,
                'data_dir': DATA_DIR_MAP[(n_maxol, a_maxol)],
            })

N_INST  = 2   # instances per scenario
D_ITER  = 20  # DEPSO iterations (quick mode)
R_ITER  = 15  # RBRS max_iterations for 50-order scenarios


def _mean(v):
    return sum(v) / len(v) if v else 0.0


def load_pool(data_dir: str) -> list:
    loader = DataLoader(Path(data_dir))
    pool = []
    for sub in range(1, 21):
        try:
            pool.extend(loader.load_orders(1, 1, sub).orders)
        except FileNotFoundError:
            pass
    return pool


def load_batch_rbrs() -> dict:
    """Read RBRS-AE vs_sop_mean from existing batch JSON files (pre-computed)."""
    rbrs = {}
    for i in range(1, 8):
        p = Path(f'results/batch_{i}.json')
        if not p.exists():
            continue
        data = json.load(open(p))
        for r in data.get('results', []):
            name = r.get('scenario')
            val  = r.get('stats', {}).get('RBRS-AE', {}).get('vs_sop_mean')
            if name and val is not None:
                rbrs[name] = val
    return rbrs


def run_scenario(scenario: dict, pool: list, wh: Warehouse,
                 run_rbrs: bool) -> dict:
    name = scenario['name']
    k    = scenario['k']
    sop_tds, fcfs_tds, depso_tds, rbrs_tds = [], [], [], []
    depso_rts, rbrs_rts = [], []

    for inst_id in range(N_INST):
        seed = inst_id * 7 + 42 + k          # fixed: vary by order count
        rng  = random.Random(seed)
        shuffled = pool[:]
        rng.shuffle(shuffled)
        orders = shuffled[:k]

        sop_tds.append(SOP().solve(orders, wh).total_travel_distance)
        fcfs_tds.append(FCFS().solve(orders, wh).total_travel_distance)

        depso = DEPSO(num_iterations=D_ITER, num_particles=5, seed=seed)
        d_sol = depso.solve(orders, wh)
        depso_tds.append(d_sol.total_travel_distance)
        depso_rts.append(d_sol.runtime_seconds)

        if run_rbrs:
            rbrs = RBRS_AE(max_iterations=R_ITER, seed=seed)
            r_sol = rbrs.solve(orders, wh)
            rbrs_tds.append(r_sol.total_travel_distance)
            rbrs_rts.append(r_sol.runtime_seconds)

    def pct(tds, ref):
        return _mean([(t - r) / r * 100 for t, r in zip(tds, ref) if r > 0])

    return {
        'scenario':      name,
        'num_orders':    k,
        'n_instances':   N_INST,
        'depso_vs_sop':  round(pct(depso_tds, sop_tds), 2),
        'depso_vs_fcfs': round(pct(depso_tds, fcfs_tds), 2),
        'depso_mean_rt': round(_mean(depso_rts), 2),
        'depso_mean_td': round(_mean(depso_tds), 1),
        'sop_mean_td':   round(_mean(sop_tds), 1),
        'fcfs_mean_td':  round(_mean(fcfs_tds), 1),
        'rbrs_vs_sop':   round(pct(rbrs_tds, sop_tds), 2) if rbrs_tds else None,
        'rbrs_mean_rt':  round(_mean(rbrs_rts), 2) if rbrs_rts else None,
        'rbrs_source':   'live' if rbrs_tds else None,
    }


def write_md(all_results: list, batch_rbrs: dict, elapsed: float) -> str:
    lines = []
    lines.append("# Paper Appendix H — 35 Senaryo Karşılaştırması")
    lines.append("")
    lines.append(f"**{N_INST} instance, {D_ITER} DEPSO iterasyon** "
                 "(sabit seed: inst_id×7+42+num_orders)")
    lines.append("")
    lines.append("| Senaryo | DEPSO vs SOP | Paper | Fark | RBRS-AE vs SOP | Durum |")
    lines.append("|---|---|---|---|---|---|")

    close_count = 0
    for r in all_results:
        name      = r['scenario']
        dpct      = r['depso_vs_sop']
        ppct      = PAPER.get(name, 0.0)
        diff      = round(dpct - ppct, 2)
        ok        = "✅" if abs(diff) < 8 else "⚠️"
        if abs(diff) < 8:
            close_count += 1

        if r['rbrs_vs_sop'] is not None:
            rbrs_str = f"{r['rbrs_vs_sop']:.2f}%"
        elif name in batch_rbrs:
            rbrs_str = f"{batch_rbrs[name]:.2f}%†"
        else:
            rbrs_str = "—"

        lines.append(f"| {name} | {dpct:.2f}% | {ppct:.2f}% "
                     f"| {diff:+.2f}% | {rbrs_str} | {ok} |")

    lines.append("")
    diffs = [abs(r['depso_vs_sop'] - PAPER.get(r['scenario'], 0.0)) for r in all_results]
    lines.append(f"**Ortalama sapma: ±{_mean(diffs):.2f}%**  ")
    lines.append(f"**Maks sapma: ±{max(diffs):.2f}%**  ")
    lines.append(f"**{close_count}/35 ✅**")
    lines.append("")
    lines.append(
        f"> Süre: {elapsed:.0f}s — DEPSO: gerçek sipariş havuzu, sabit seed "
        f"({N_INST} inst, {D_ITER} iter). "
        "RBRS-AE†: `results/batch_*.json` kaynaklı (sentetik siparişler, 5 inst, 100 DEPSO iter). "
        "RBRS-AE 100+ sipariş için O(n²) başlatma maliyeti nedeniyle canlı hesap yapılmamıştır."
    )
    return "\n".join(lines)


def main():
    wh = Warehouse()
    batch_rbrs = load_batch_rbrs()
    print(f"Batch RBRS loaded: {len(batch_rbrs)} entries")

    pools: dict = {}
    for combo, ddir in DATA_DIR_MAP.items():
        if Path(ddir).exists():
            pools[combo] = load_pool(ddir)
            print(f"  Pool {ddir}: {len(pools[combo])} orders")

    t0 = time.perf_counter()
    all_results = []

    for i, sc in enumerate(ALL_35):
        combo = (sc['n'], sc['a'])
        pool  = pools.get(combo, [])
        if len(pool) < sc['k']:
            print(f"  SKIP {sc['name']}: pool={len(pool)} < k={sc['k']}")
            continue

        run_rbrs = (sc['k'] == 50)
        print(f"  [{i+1:2d}/35] {sc['name']:12s}  k={sc['k']:3d}  "
              f"RBRS={'live' if run_rbrs else 'batch'}  ", end='', flush=True)

        t1 = time.perf_counter()
        r  = run_scenario(sc, pool, wh, run_rbrs)
        dt = time.perf_counter() - t1

        if r['rbrs_vs_sop'] is None and sc['name'] in batch_rbrs:
            r['rbrs_vs_sop'] = batch_rbrs[sc['name']]
            r['rbrs_source'] = 'batch'

        all_results.append(r)
        ppct = PAPER.get(sc['name'], 0.0)
        diff = r['depso_vs_sop'] - ppct
        print(f"DEPSO={r['depso_vs_sop']:+.2f}%  paper={ppct:.2f}%  "
              f"Δ={diff:+.2f}%  {dt:.0f}s")

    elapsed = time.perf_counter() - t0
    print(f"\nTotal: {elapsed:.0f}s")

    # Verification: DEPSO must differ across k values for the same combo
    print("\n=== Verification: DEPSO differs across k values ===")
    by_combo: dict = defaultdict(list)
    for r in all_results:
        parts = r['scenario'].split('_')
        combo = '_'.join(parts[1:])
        by_combo[combo].append((parts[0], r['depso_vs_sop']))
    all_differ = True
    for combo, vals in sorted(by_combo.items()):
        vals.sort()
        unique = len(set(v for _, v in vals))
        status = "DIFFER ✅" if unique > 1 else "SAME ⚠️"
        if unique <= 1:
            all_differ = False
        print(f"  {combo}: {', '.join(f'{k}→{v:.2f}%' for k, v in vals)}  [{status}]")
    print(f"\nAll k values produce different DEPSO results: {all_differ}")

    Path("results").mkdir(exist_ok=True)
    md_text = write_md(all_results, batch_rbrs, elapsed)
    Path("results/paper_35_scenarios.md").write_text(md_text)
    print(f"\n✓ results/paper_35_scenarios.md written")

    json_data = {
        'meta': {
            'n_instances': N_INST,
            'depso_iter': D_ITER,
            'rbrs_iter_50orders': R_ITER,
            'seed_formula': 'inst_id * 7 + 42 + num_orders',
            'depso_source': 'live (data dirs, fixed seed)',
            'rbrs_source_50': 'live',
            'rbrs_source_100plus': 'batch_*.json (synthetic orders)',
        },
        'results': all_results,
        'paper_reference': PAPER,
    }
    Path("results/paper_35_scenarios.json").write_text(
        json.dumps(json_data, indent=2))
    print(f"✓ results/paper_35_scenarios.json written")


if __name__ == "__main__":
    main()
