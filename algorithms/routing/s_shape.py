"""
algorithms/routing/s_shape.py
==============================
S-Shape heuristic - paper'ın benchmark routing yöntemi.

Çalışma prensibi:
- Picker, depot'tan ilk aisle'a gider
- Eğer aisle'da en az 1 pick varsa, aisle'ı **baştan sona** (S şekli) gezer
- Sonraki aisle'a geçer, ters yönde gezer, vb.
- Hiç pick olmayan aisle'lar atlanır
- Son aisle'dan sonra cross aisle üzerinden depot'a döner

Bu yöntem multi-block layout için biraz uyarlanmış: her blok için ayrı S-Shape uygulanır,
ama paper basitleştirmek için tek-blok S-Shape'i benchmark olarak kullanır.

Bu modül "klasik" S-Shape'i implement eder (tek blok mantığıyla).
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from core.warehouse import Warehouse


def s_shape_route(locations: list[int], warehouse: Warehouse) -> tuple[list[int], float]:
    """
    Verilen lokasyonlar için S-Shape rotası kurar.

    Strateji:
    1) Her aisle'da hangi lokasyonlar var, bul.
    2) Aisle'ları soldan sağa (veya yakından uzağa) sırala.
    3) Çift aisle indeksli olanı yukarı (x artan), tek olanı aşağı (x azalan) gez.
    4) Başta ve sonda depot.

    Döndürür: (route, total_distance)
    """
    if not locations:
        return [warehouse.DEPOT, warehouse.DEPOT], 0.0

    unique_locs = list(set(locations))

    # Aisle bazlı grupla
    aisles_with_picks: dict[int, list[int]] = {}
    for loc in unique_locs:
        a = warehouse._aisle_of(loc)
        if a is None:  # depot
            continue
        aisles_with_picks.setdefault(a, []).append(loc)

    if not aisles_with_picks:
        return [warehouse.DEPOT, warehouse.DEPOT], 0.0

    # Aisle'ları depot'a yakınlıkla sırala
    # Depot aisle 0'ın altında olduğu için aisle 0'a en yakın
    sorted_aisles = sorted(aisles_with_picks.keys())

    route = [warehouse.DEPOT]
    total_distance = 0.0
    current = warehouse.DEPOT

    for idx, aisle in enumerate(sorted_aisles):
        locs_in_aisle = aisles_with_picks[aisle]

        # Aisle içinde x'e göre sırala
        # Çift sıra: x artan (soldan sağa)
        # Tek sıra: x azalan (sağdan sola)
        locs_in_aisle.sort(key=lambda l: warehouse.coords(l)[0],
                          reverse=(idx % 2 == 1))

        # Tüm bu lokasyonları sırayla ziyaret et
        for loc in locs_in_aisle:
            d = warehouse.distance(current, loc)
            total_distance += d
            route.append(loc)
            current = loc

    # Depot'a dön
    total_distance += warehouse.distance(current, warehouse.DEPOT)
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
