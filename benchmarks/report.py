"""
benchmarks/report.py
=====================
JSON sonuç dosyasından MD raporu oluştur.

    python -m benchmarks.report results/multi_instance.json
"""

import json
import sys
import math
from pathlib import Path


def generate_report(json_path: str) -> str:
    with open(json_path) as f:
        data = json.load(f)

    cfg   = data['config']
    stats = data['stats']

    lines = []
    lines.append("# Çoklu Instance Deney Raporu")
    lines.append("")
    lines.append("## Deney Konfigürasyonu")
    lines.append("")
    lines.append(f"| Parametre | Değer |")
    lines.append(f"|---|---|")
    lines.append(f"| Instance sayısı | {cfg['n_instances']} |")
    lines.append(f"| Sipariş / instance | {cfg['num_orders']} |")
    lines.append(f"| Senaryo | {cfg['scenario']} |")
    lines.append(f"| DEPSO iterasyon | {cfg['depso_iter']} |")
    lines.append(f"| RBRS-AE iterasyon | {cfg['rbrs_iter']} |")
    lines.append("")

    lines.append("## Sonuçlar")
    lines.append("")
    lines.append("| Algoritma | Ort TD (LU) | Std | Min | Max | Ort Süre | vs SOP | vs FCFS |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for s in stats:
        vs_sop  = f"{s['vs_sop_pct']:+.1f}%"  if s['vs_sop_pct']  != 0 else "—"
        vs_fcfs = f"{s['vs_fcfs_pct']:+.1f}%"  if s['vs_fcfs_pct'] != 0 else "—"
        lines.append(
            f"| **{s['algorithm']}** "
            f"| {s['mean_td']:.1f} "
            f"| {s['std_td']:.1f} "
            f"| {s['min_td']:.1f} "
            f"| {s['max_td']:.1f} "
            f"| {s['mean_runtime']:.2f}s "
            f"| {vs_sop} "
            f"| {vs_fcfs} |"
        )
    lines.append("")
    lines.append("> Note: vs SOP / vs FCFS are the mean of per-instance percentage differences, "
                 "not the ratio of the mean TDs. The two differ when instance sizes vary.")

    lines.append("")
    lines.append("## Paper Hedefleriyle Karşılaştırma")
    lines.append("")

    depso = next((s for s in stats if s['algorithm'] == 'DEPSO'), None)
    rbrs  = next((s for s in stats if s['algorithm'] == 'RBRS-AE'), None)

    if depso:
        lines.append(f"| Metrik | Gerçekleşen | Paper Hedefi | Durum |")
        lines.append(f"|---|---|---|---|")
        sop_ok  = "✅" if abs(depso['vs_sop_pct']  + 88) < 15 else "⚠️"
        fcfs_ok = "✅" if abs(depso['vs_fcfs_pct'] + 40) < 20 else "⚠️"
        lines.append(f"| DEPSO vs SOP  | {depso['vs_sop_pct']:+.2f}% | ~-88% | {sop_ok} |")
        lines.append(f"| DEPSO vs FCFS | {depso['vs_fcfs_pct']:+.2f}% | ~-40% | {fcfs_ok} |")

    if rbrs and depso:
        diff    = (rbrs['mean_td'] - depso['mean_td']) / depso['mean_td'] * 100
        speedup = depso['mean_runtime'] / max(rbrs['mean_runtime'], 0.01)
        lines.append("")
        lines.append("## DEPSO vs RBRS-AE")
        lines.append("")
        lines.append(f"| Metrik | Değer |")
        lines.append(f"|---|---|")
        lines.append(f"| TD farkı | {diff:+.2f}% |")
        lines.append(f"| Hız farkı | RBRS-AE {speedup:.1f}x {'hızlı' if speedup > 1 else 'yavaş'} |")
        lines.append(f"| RBRS-AE ort TD | {rbrs['mean_td']:.1f} LU |")
        lines.append(f"| DEPSO ort TD | {depso['mean_td']:.1f} LU |")

    return "\n".join(lines)


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "results/multi_instance.json"
    report = generate_report(path)
    print(report)

    # MD dosyasına da kaydet
    out = Path(path).with_suffix('.md')
    out.write_text(report)
    print(f"\n✓ Rapor kaydedildi: {out}")
