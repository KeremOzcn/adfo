"""tests/test_warehouse.py — Warehouse modül testleri."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.warehouse import Warehouse
from core.data_loader import DataLoader


def test_total_locations():
    wh = Warehouse()
    assert wh.total_locations == 7200


def test_depot_coords():
    wh = Warehouse()
    x, y = wh.coords(wh.DEPOT)
    assert x == wh.depot_x
    assert y == wh.depot_y


def test_distance_self_zero():
    wh = Warehouse()
    assert wh.distance(0, 0) == 0.0
    assert wh.distance(-1, -1) == 0.0


def test_distance_symmetric():
    wh = Warehouse()
    for a, b in [(0, 100), (-1, 500), (3500, 6700)]:
        assert wh.distance(a, b) == wh.distance(b, a)


def test_depot_distance_positive():
    wh = Warehouse()
    assert wh.distance(-1, 0) > 0
    assert wh.distance(-1, 7199) > 0


def test_same_aisle_distance():
    wh = Warehouse()
    # loc 0 ve loc 4 aynı aisle → direkt mesafe
    d = wh.distance(0, 4)
    assert d > 0
    assert d < 10  # aynı aisle içinde küçük olmalı


def test_build_problem_matrix():
    wh = Warehouse()
    loader = DataLoader()
    orders = loader.load_orders(1, 1, 20).orders[:10]
    wh.build_problem_matrix(orders)
    assert wh._matrix is not None
    n = len(wh._matrix_locs)
    assert wh._matrix.shape == (n, n)


def test_dist_m_equals_distance():
    wh = Warehouse()
    loader = DataLoader()
    orders = loader.load_orders(1, 1, 20).orders[:10]
    wh.build_problem_matrix(orders)
    # dist_m ve distance aynı sonucu vermeli
    for loc in list(wh._matrix_locs)[:5]:
        for loc2 in list(wh._matrix_locs)[:5]:
            assert abs(wh.dist_m(loc, loc2) - wh.distance(loc, loc2)) < 1e-3


def test_location_classes():
    wh = Warehouse()
    classes = wh.assign_locations_to_classes()
    assert len(classes['A']) == int(7200 * 0.05)
    assert len(classes['B']) == int(7200 * 0.15)
    assert len(classes['A']) + len(classes['B']) + len(classes['C']) == 7200


def test_warehouse_layout_loadable():
    loader = DataLoader()
    layout = loader.load_warehouse_layout()
    assert layout['num_aisles'] == 10
    assert layout['total_locations'] == 7200


if __name__ == "__main__":
    test_total_locations()
    test_depot_coords()
    test_distance_self_zero()
    test_distance_symmetric()
    test_depot_distance_positive()
    test_same_aisle_distance()
    test_build_problem_matrix()
    test_dist_m_equals_distance()
    test_location_classes()
    test_warehouse_layout_loadable()
    print("✅ test_warehouse: tüm testler geçti")
