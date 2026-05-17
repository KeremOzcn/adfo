"""
tests/test_smoke.py
====================
QA raporundan sonra eklenen smoke testler.
Tüm ana modüllerin temel fonksiyonalitesini doğrular.

Çalıştır: pytest tests/
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from core.data_loader import DataLoader, Order, OrderLine
from core.warehouse import Warehouse


# ── Fixture'lar ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def wh():
    return Warehouse()


@pytest.fixture(scope="module")
def loader():
    return DataLoader()


@pytest.fixture(scope="module")
def small_orders(loader):
    return loader.load_orders(1, 1, 20).orders[:20]


def make_order(oid, weight, location=100):
    ol = OrderLine(item=oid, quantity=1, location=location, weight=weight)
    return Order(order_id=oid, num_orderlines=1,
                 total_weight=weight, orderlines=[ol])


# ── Warehouse testleri ────────────────────────────────────────────

def test_warehouse_total_locations(wh):
    assert wh.total_locations == 7200


def test_warehouse_distance_zero_self(wh):
    assert wh.distance(0, 0) == 0.0


def test_warehouse_distance_symmetric(wh):
    assert wh.distance(100, 500) == wh.distance(500, 100)


def test_warehouse_depot_distance(wh):
    d = wh.distance(-1, 0)
    assert d > 0


def test_build_problem_matrix(wh, small_orders):
    wh.build_problem_matrix(small_orders)
    assert wh._matrix is not None
    assert wh._matrix.shape[0] > 0


# ── Routing testleri ─────────────────────────────────────────────

def test_nearest_neighbor(wh):
    from algorithms.routing.nearest_neighbor import nearest_neighbor_route
    locs = [100, 200, 300]
    route, dist = nearest_neighbor_route(locs, wh)
    assert route[0] == wh.DEPOT
    assert route[-1] == wh.DEPOT
    assert dist > 0


def test_two_opt(wh):
    from algorithms.routing.nearest_neighbor import nearest_neighbor_route
    from algorithms.routing.two_opt import two_opt_improve
    locs = [100, 500, 1000, 2000, 3000]
    route, dist_nn = nearest_neighbor_route(locs, wh)
    route_opt, dist_opt = two_opt_improve(route, wh)
    assert dist_opt <= dist_nn + 1e-6


def test_s_shape(wh):
    from algorithms.routing.s_shape import s_shape_route
    locs = [100, 800, 1500]
    route, dist = s_shape_route(locs, wh)
    assert route[0] == wh.DEPOT
    assert route[-1] == wh.DEPOT
    assert dist > 0


# ── Batching testleri ────────────────────────────────────────────

def test_first_fit_basic():
    from algorithms.batching.first_fit import first_fit_batching
    orders = [make_order(i, 30.0) for i in range(5)]
    batches = first_fit_batching(orders, capacity=100.0)
    # 5 × 30 WU, kapasite 100 → 3 batch (30+30+30=90, 30+30=60 → 2 batch)
    assert len(batches) >= 2
    for b in batches:
        assert b.total_weight <= 100.0


def test_first_fit_paper_example():
    """Paper supplement Part 1 — QA raporu doğrulama."""
    from algorithms.batching.first_fit import first_fit_batching
    sequence = [4, 7, 2, 9, 1, 3, 5, 10, 6]
    weights  = [25, 70, 10, 60, 40, 35, 20, 80, 5]
    orders   = [make_order(oid, w) for oid, w in zip(sequence, weights)]
    batches  = first_fit_batching(orders, capacity=100.0)
    actual   = {b.batch_id: [o.order_id for o in b.orders] for b in batches}
    expected = {0: [4, 7, 6], 1: [2, 9, 5], 2: [1, 3], 3: [10]}
    assert actual == expected


# ── DEPSO smoke testi ─────────────────────────────────────────────

def test_depso_smoke(small_orders, wh):
    from algorithms.depso import DEPSO
    sol = DEPSO(num_iterations=10, seed=42).solve(small_orders, wh)
    assert sol.total_travel_distance > 0
    assert sol.num_batches > 0
    assert len(sol.convergence_history) == 10


# ── RBRS-AE smoke testi ───────────────────────────────────────────

def test_rbrs_ae_smoke(small_orders, wh):
    from algorithms.rbrs_ae import RBRS_AE
    sol = RBRS_AE(max_iterations=5, seed=42).solve(small_orders, wh)
    assert sol.total_travel_distance > 0
    assert sol.num_batches > 0


# ── Holt-Winters smoke testi ─────────────────────────────────────

def test_holt_winters_fit_predict():
    from core.forecasting import HoltWinters
    history = [100 + i * 2 for i in range(12)]
    hw = HoltWinters()
    hw.fit(history)
    pred = hw.predict(tau=1)
    assert pred >= 0


def test_holt_winters_update():
    from core.forecasting import HoltWinters
    history = [50.0] * 12
    hw = HoltWinters()
    hw.fit(history)
    hw.update(55.0)
    pred = hw.predict(tau=1)
    assert pred >= 0


# ── Savings smoke testi ───────────────────────────────────────────

def test_savings_smoke(wh):
    from algorithms.batching.savings import savings_batching
    orders = [make_order(i, 20.0, location=i * 100) for i in range(10)]
    batches = savings_batching(orders, wh, capacity=100.0)
    assert len(batches) > 0
    for b in batches:
        assert b.total_weight <= 100.0


# ── SOP / FCFS smoke testleri ────────────────────────────────────

def test_sop_smoke(small_orders, wh):
    from benchmarks.sop import SOP
    sol = SOP().solve(small_orders, wh)
    assert sol.num_batches == len(small_orders)  # her sipariş kendi batch'i


def test_fcfs_smoke(small_orders, wh):
    from benchmarks.fcfs import FCFS
    sol = FCFS().solve(small_orders, wh)
    assert sol.num_batches < len(small_orders)  # batching yapılmalı
    assert sol.total_travel_distance > 0
