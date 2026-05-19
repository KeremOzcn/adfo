"""tests/test_batching.py — Batching modül testleri."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_loader import DataLoader, Order, OrderLine
from core.warehouse import Warehouse
from algorithms.batching.first_fit import first_fit_batching
from algorithms.batching.savings import savings_batching


def make_order(oid, weight, location=100):
    ol = OrderLine(item=oid, quantity=1, location=location, weight=weight)
    return Order(order_id=oid, num_orderlines=1,
                 total_weight=weight, orderlines=[ol])


def test_first_fit_capacity():
    """Hiçbir batch kapasiteyi aşmamalı."""
    orders = [make_order(i, 30.0) for i in range(10)]
    batches = first_fit_batching(orders, capacity=100.0)
    for b in batches:
        assert b.total_weight <= 100.0 + 1e-9


def test_first_fit_all_assigned():
    """Tüm siparişler bir batch'e atanmalı."""
    orders = [make_order(i, 20.0) for i in range(8)]
    batches = first_fit_batching(orders, capacity=100.0)
    total_orders = sum(len(b.orders) for b in batches)
    assert total_orders == 8


def test_first_fit_paper_example():
    """Paper supplement Part 1 — birebir doğrulama."""
    sequence = [4, 7, 2, 9, 1, 3, 5, 10, 6]
    weights  = [25, 70, 10, 60, 40, 35, 20, 80, 5]
    orders   = [make_order(oid, w) for oid, w in zip(sequence, weights)]
    batches  = first_fit_batching(orders, capacity=100.0)
    actual   = {b.batch_id: [o.order_id for o in b.orders] for b in batches}
    expected = {0: [4, 7, 6], 1: [2, 9, 5], 2: [1, 3], 3: [10]}
    assert actual == expected


def test_first_fit_single_order():
    orders = [make_order(0, 99.0)]
    batches = first_fit_batching(orders, capacity=100.0)
    assert len(batches) == 1
    assert batches[0].total_weight == 99.0


def test_savings_capacity():
    """Savings: hiçbir batch kapasiteyi aşmamalı."""
    wh = Warehouse()
    orders = [make_order(i, 20.0, location=i * 200) for i in range(8)]
    batches = savings_batching(orders, wh, capacity=100.0)
    for b in batches:
        assert b.total_weight <= 100.0 + 1e-9


def test_savings_all_assigned():
    """Savings: tüm siparişler atanmalı."""
    wh = Warehouse()
    orders = [make_order(i, 20.0, location=i * 100) for i in range(6)]
    batches = savings_batching(orders, wh, capacity=100.0)
    total = sum(len(b.orders) for b in batches)
    assert total == 6


def test_savings_fewer_batches_than_sop():
    """Savings, SOP'tan daha az batch üretmeli."""
    wh = Warehouse()
    orders = [make_order(i, 15.0, location=i * 100) for i in range(10)]
    batches = savings_batching(orders, wh, capacity=100.0)
    # 10 sipariş × 15 WU → en fazla 2 batch (10*15/100 = 1.5)
    assert len(batches) < 10


def test_first_fit_real_data():
    """Gerçek dataset ile first-fit çalışıyor mu?"""
    loader = DataLoader()
    orders = loader.load_orders(1, 1, 20).orders[:30]
    batches = first_fit_batching(orders)
    assert len(batches) > 0
    assert len(batches) < len(orders)
    for b in batches:
        assert b.total_weight <= 100.0 + 1e-9


if __name__ == "__main__":
    test_first_fit_capacity()
    test_first_fit_all_assigned()
    test_first_fit_paper_example()
    test_first_fit_single_order()
    test_savings_capacity()
    test_savings_all_assigned()
    test_savings_fewer_batches_than_sop()
    test_first_fit_real_data()
    print("✅ test_batching: tüm testler geçti")
