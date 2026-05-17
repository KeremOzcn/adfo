"""
tests/test_distance.py
=======================
Manhattan distance ve rota mesafesi doğrulama testleri.

Arkadaşların önerisi: distance = |x1-x2| + |y1-y2| olmalı,
ayrıca rota toplamı Depot → item1 → item2 → ... → itemN → Depot
dönüş mesafesi dahil olmalı.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.warehouse import Warehouse


def test_manhattan_basic():
    """Aynı aisle içinde Manhattan."""
    wh = Warehouse()

    # loc 0: aisle 0, rack 0   → (0.5, 1.5)
    # loc 4: aisle 0, rack 1   → (1.5, 1.5)
    d = wh.distance(0, 4)
    expected = abs(0.5 - 1.5) + abs(1.5 - 1.5)
    assert abs(d - expected) < 1e-9, f"loc 0→4: beklenen {expected}, alındı {d}"
    print(f"  ✓ loc 0 → loc 4 (aynı aisle): {d:.2f} LU = |0.5-1.5| + |1.5-1.5|")


def test_different_aisle():
    """Farklı aisle'lar arası: cross aisle üzerinden gitmeli."""
    wh = Warehouse()

    # loc 0: aisle 0, x=0.5, y=1.5
    # loc 720: aisle 1, x=0.5, y=4.5
    # Beklenen: aisle 0'dan cross aisle (x=0)'a 0.5, oradan aisle 1'e |1.5-4.5|=3, geri 0.5
    # = 0.5 + 3 + 0.5 = 4 LU
    d = wh.distance(0, 720)
    print(f"  ✓ loc 0 → loc 720 (aisle 0 → aisle 1): {d:.2f} LU")
    assert d == 4.0, f"loc 0→720: beklenen 4.0, alındı {d}"


def test_depot_distance():
    """Depot'a mesafeler."""
    wh = Warehouse()

    # Depot: (96.0, 0.0)
    # loc 0: (0.5, 1.5)
    # Direkt: |96.0-0.5| + |0.0-1.5| = 95.5 + 1.5 = 97
    d = wh.distance(-1, 0)
    print(f"  ✓ depot → loc 0: {d:.2f} LU")
    assert d == 97.0, f"depot→loc 0: beklenen 97.0, alındı {d}"


def test_symmetric():
    """Mesafe simetrik olmalı: d(a,b) = d(b,a)."""
    wh = Warehouse()

    for a, b in [(0, 100), (-1, 5000), (3500, 6700), (1, 2000)]:
        d_ab = wh.distance(a, b)
        d_ba = wh.distance(b, a)
        assert d_ab == d_ba, f"Asimetri: {a}→{b}={d_ab}, {b}→{a}={d_ba}"
    print(f"  ✓ Mesafe simetrik (4 çift test edildi)")


def test_route_distance_with_depot_return():
    """
    Rota toplamı Depot → item1 → ... → itemN → Depot olmalı.
    Dönüş mesafesi dahil edilmeli.
    """
    from algorithms.routing.two_opt import _route_distance

    wh = Warehouse()
    # Basit rota: depot → loc 0 → loc 4 → depot
    route = [-1, 0, 4, -1]
    d = _route_distance(route, wh)

    # depot→loc0 = 97
    # loc0→loc4 = 1
    # loc4→depot = |1.5-96|+|1.5-0| = 94.5+1.5 = 96
    # toplam = 97 + 1 + 96 = 194
    expected = 97 + 1 + 96
    print(f"  ✓ Rota [depot, 0, 4, depot]: {d:.2f} LU (beklenen {expected})")
    assert abs(d - expected) < 1e-9, f"Rota mesafesi: beklenen {expected}, alındı {d}"


def test_route_distance_only_with_return():
    """Rota mutlaka depot'a dönüş içermeli."""
    from algorithms.routing.nearest_neighbor import nearest_neighbor_route

    wh = Warehouse()
    locs = [100, 200, 300]
    route, dist = nearest_neighbor_route(locs, wh)

    # Route depot ile başlamalı ve depot ile bitmeli
    assert route[0] == -1, f"Rota depot ile başlamalı: {route[0]}"
    assert route[-1] == -1, f"Rota depot ile bitmeli: {route[-1]}"
    print(f"  ✓ NN rotası: {route}, mesafe {dist:.2f} LU "
          f"(depot başta ve sonda ✓)")


def test_path_via_cross_aisle():
    """
    Multi-aisle test: aisle 0'dan aisle 9'a en kısa yol.

    Paper Fig.7 setup: cross aisle'lar yatay, picker bunlardan geçmeli.
    """
    wh = Warehouse()

    # aisle 0, rack 0 → aisle 9, rack 0
    # loc 0:    (0.5, 1.5)
    # loc 6480: aisle 9, side 0, rack 0, w 0 → (0.5, 28.5)
    # Aynı x, farklı y, en yakın cross aisle x=0 üzerinden:
    # |0.5-0| + |1.5-28.5| + |0.5-0| = 0.5 + 27 + 0.5 = 28
    d = wh.distance(0, 6480)
    print(f"  ✓ loc 0 (aisle 0) → loc 6480 (aisle 9): {d:.2f} LU")
    assert d == 28.0, f"Beklenen 28, alındı {d}"


def test_paper_warehouse_geometry():
    """Depo geometrisi paper'a uygun mu?"""
    wh = Warehouse()
    print(f"\n  Depo geometrisi:")
    print(f"    Aisle sayısı: {wh.num_aisles}")
    print(f"    Blok sayısı: {wh.num_blocks}")
    print(f"    Cross aisle sayısı: {len(wh.cross_aisle_x)}")  # iç+dış = 4
    print(f"    Cross aisle x: {wh.cross_aisle_x}")
    print(f"    Toplam lokasyon: {wh.total_locations}")
    print(f"    Depot: ({wh.depot_x}, {wh.depot_y})")
    assert wh.num_aisles == 10
    assert wh.num_blocks == 3
    assert wh.total_locations == 7200


if __name__ == "__main__":
    print("=" * 60)
    print("Manhattan Distance & Route Distance Doğrulama Testleri")
    print("=" * 60)

    test_manhattan_basic()
    test_different_aisle()
    test_depot_distance()
    test_symmetric()
    test_route_distance_with_depot_return()
    test_route_distance_only_with_return()
    test_path_via_cross_aisle()
    test_paper_warehouse_geometry()

    print()
    print("=" * 60)
    print("✓ TÜM TESTLER GEÇTİ")
    print("=" * 60)
