"""
algorithms/routing/nearest_neighbor.py
=======================================
Nearest Neighbor (NN) heuristic - Paper Appendix B.

Bir batch'in lokasyon listesi verildiğinde, depot'tan başlayıp
her seferinde en yakın ziyaret edilmemiş düğüme giden bir tour kurar.
Sonunda depot'a döner.
"""

from typing import Iterable


def nearest_neighbor_route(locations: list[int], warehouse, start: int = None) -> tuple[list[int], float]:
    """
    NN ile bir picking tour'u kurar.
    warehouse.dist_m() kullanır (numpy matris varsa O(1) lookup).
    """
    if start is None:
        start = warehouse.DEPOT

    if not locations:
        return [start, start], 0.0

    # Unique lokasyonlar
    unique_locs = list(set(locations))
    df = warehouse.dist_m  # lokal referans — attribute lookup maliyetini azaltır

    route = [start]
    remaining = set(unique_locs)
    current = start
    total_distance = 0.0

    while remaining:
        nearest = min(remaining, key=lambda loc: df(current, loc))
        d = df(current, nearest)
        total_distance += d
        route.append(nearest)
        remaining.discard(nearest)
        current = nearest

    total_distance += df(current, start)
    route.append(start)

    return route, total_distance


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from core.warehouse import Warehouse

    wh = Warehouse()

    # Test: 5 rastgele lokasyon
    test_locs = [100, 1500, 3700, 5200, 6800]
    route, dist = nearest_neighbor_route(test_locs, wh)
    print(f"Lokasyonlar: {test_locs}")
    print(f"NN rotası:   {route}")
    print(f"Mesafe:      {dist:.2f} LU")

    # Tek lokasyon
    route, dist = nearest_neighbor_route([100], wh)
    print(f"\nTek lokasyon: {[100]}")
    print(f"NN rotası: {route}, mesafe: {dist:.2f} LU")
