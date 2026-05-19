"""tests/test_depso.py — DEPSO algoritması testleri."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_loader import DataLoader
from core.warehouse import Warehouse
from algorithms.depso import DEPSO
from benchmarks.sop import SOP
from benchmarks.fcfs import FCFS


def get_orders(n=20):
    loader = DataLoader()
    return loader.load_orders(1, 1, 20).orders[:n]


def test_depso_returns_solution():
    wh = Warehouse()
    orders = get_orders(15)
    sol = DEPSO(num_iterations=10, seed=42).solve(orders, wh)
    assert sol is not None
    assert sol.total_travel_distance > 0
    assert sol.num_batches > 0


def test_depso_convergence_history_length():
    """convergence_history uzunluğu num_iterations'a eşit olmalı."""
    wh = Warehouse()
    orders = get_orders(10)
    depso = DEPSO(num_iterations=20, seed=42)
    sol = depso.solve(orders, wh)
    assert len(sol.convergence_history) == 20


def test_depso_convergence_history_resets():
    """Aynı instance ikinci kez çağrıldığında history sıfırlanmalı."""
    wh = Warehouse()
    orders = get_orders(10)
    depso = DEPSO(num_iterations=15, seed=42)
    sol1 = depso.solve(orders, wh)
    sol2 = depso.solve(orders, wh)
    assert len(sol1.convergence_history) == 15
    assert len(sol2.convergence_history) == 15  # birikmemeli


def test_depso_non_increasing_convergence():
    """Gbest monoton azalmalı veya sabit kalmalı."""
    wh = Warehouse()
    orders = get_orders(15)
    sol = DEPSO(num_iterations=30, seed=42).solve(orders, wh)
    history = sol.convergence_history
    for i in range(1, len(history)):
        assert history[i] <= history[i-1] + 1e-6


def test_depso_better_than_sop():
    """DEPSO, SOP'tan daha iyi olmalı."""
    wh = Warehouse()
    orders = get_orders(20)
    sop_sol  = SOP().solve(orders, wh)
    depso_sol = DEPSO(num_iterations=50, seed=42).solve(orders, wh)
    assert depso_sol.total_travel_distance < sop_sol.total_travel_distance


def test_depso_capacity_respected():
    """Hiçbir batch kapasiteyi aşmamalı."""
    wh = Warehouse()
    orders = get_orders(20)
    sol = DEPSO(num_iterations=20, seed=42).solve(orders, wh)
    for b in sol.batches:
        assert b.total_weight <= 100.0 + 1e-9


def test_depso_all_orders_assigned():
    """Tüm siparişler bir batch'e atanmalı."""
    wh = Warehouse()
    orders = get_orders(20)
    sol = DEPSO(num_iterations=20, seed=42).solve(orders, wh)
    assigned = sum(len(b.orders) for b in sol.batches)
    assert assigned == len(orders)


def test_depso_deterministic_with_seed():
    """Aynı seed → aynı sonuç."""
    wh = Warehouse()
    orders = get_orders(15)
    sol1 = DEPSO(num_iterations=20, seed=123).solve(orders, wh)
    sol2 = DEPSO(num_iterations=20, seed=123).solve(orders, wh)
    assert sol1.total_travel_distance == sol2.total_travel_distance


def test_depso_scenario2():
    """Senaryo 2 verileriyle de çalışmalı."""
    loader = DataLoader()
    wh = Warehouse()
    orders = loader.load_orders(2, 1, 1).orders[:15]
    sol = DEPSO(num_iterations=10, seed=42).solve(orders, wh)
    assert sol.total_travel_distance > 0


if __name__ == "__main__":
    test_depso_returns_solution()
    test_depso_convergence_history_length()
    test_depso_convergence_history_resets()
    test_depso_non_increasing_convergence()
    test_depso_better_than_sop()
    test_depso_capacity_respected()
    test_depso_all_orders_assigned()
    test_depso_deterministic_with_seed()
    test_depso_scenario2()
    print("✅ test_depso: tüm testler geçti")
