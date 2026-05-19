"""
algorithms/routing/s_shape.py
==============================
S-Shape heuristic - paper'ın benchmark routing yöntemi.

Multi-block depo için doğru implementasyon:
- Picker, depot'tan başlar
- Her aisle'da pick varsa aisle'ı baştan sona (S şekli) gezer
- Aisle içinde hangi blokta pick var, o bloğu gezer
- Pick olmayan aisle'lar atlanır
- Depot'a döner
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.warehouse import Warehouse


def s_shape_route(locations: list[int], warehouse: Warehouse) -> tuple[list[int], float]:
    """
    Multi-block depo için S-Shape rotası.

    Her aisle için:
    - Çift indeks: cross-aisle'dan gir, aisle'ı x artan yönde gez
    - Tek indeks: aisle'ı x azalan yönde gez
    - warehouse.distance() kullanarak cross-aisle maliyetleri doğru hesaplanır.

    Döndürür: (route, total_distance)
    """
    if not locations:
        return [warehouse.DEPOT, warehouse.DEPOT], 0.0

    unique_locs = list(set(locations))

    # Aisle bazlı grupla
    aisles_with_picks: dict[int, list[int]] = {}
    for loc in unique_locs:
        a = warehouse._aisle_of(loc)
        if a is None:
            continue
        aisles_with_picks.setdefault(a, []).append(loc)

    if not aisles_with_picks:
        return [warehouse.DEPOT, warehouse.DEPOT], 0.0

    sorted_aisles = sorted(aisles_with_picks.keys())

    route = [warehouse.DEPOT]
    total_distance = 0.0
    current = warehouse.DEPOT
    df = warehouse.dist_m

    for idx, aisle in enumerate(sorted_aisles):
        locs_in_aisle = aisles_with_picks[aisle]

        # S-Shape: çift idx → x artan (depot tarafından uzağa)
        #           tek idx → x azalan (uzaktan depot'a doğru)
        reverse = (idx % 2 == 1)
        locs_in_aisle.sort(
            key=lambda l: warehouse.coords(l)[0],
            reverse=reverse
        )

        for loc in locs_in_aisle:
            d = df(current, loc)
            total_distance += d
            route.append(loc)
            current = loc

    # Depot'a dön
    total_distance += df(current, warehouse.DEPOT)
    route.append(warehouse.DEPOT)

    return route, total_distance


if __name__ == "__main__":
    wh = Warehouse()

    test_locs = [100, 1500, 3700, 5200, 6800, 800, 2400, 4100]
    route, dist = s_shape_route(test_locs, wh)
    print(f"S-Shape rotası: {route}")
    print(f"S-Shape mesafesi: {dist:.2f} LU")

    # Karşılaştırma: NN + 2-opt
    from algorithms.routing.two_opt import nn_then_2opt
    nn2opt_route, nn2opt_dist = nn_then_2opt(test_locs, wh)
    print(f"\nNN+2opt:        {nn2opt_dist:.2f} LU")
    print(f"S-Shape - NN+2opt fark: {(dist - nn2opt_dist) / nn2opt_dist * 100:+.1f}%")
