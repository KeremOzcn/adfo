"""
benchmarks/fcfs.py
==================
First-Come-First-Served (FCFS) baseline.

Siparişleri geliş sırasında alır, first-fit ile batchler, sonra S-Shape ile gezer.
DEPSO'nun en doğrudan rakibi.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.data_loader import Order
from algorithms.base import BatchingRoutingAlgorithm, Batch, Solution
from algorithms.batching.first_fit import first_fit_batching
from algorithms.routing.s_shape import s_shape_route


class FCFS(BatchingRoutingAlgorithm):
    """
    FCFS batching + S-Shape routing.
    Siparişleri verilen sırada, first-fit ile batchle.
    """

    def __init__(self, routing: str = "s_shape"):
        self.routing = routing

    @property
    def name(self) -> str:
        return f"FCFS+{self.routing.upper()}"

    def _solve_impl(self, orders: list[Order], warehouse) -> Solution:
        # Batching: first-fit
        batches = first_fit_batching(orders)

        # Routing: her batch için
        total_distance = 0.0
        for batch in batches:
            if self.routing == "s_shape":
                route, dist = s_shape_route(batch.locations, warehouse)
            else:
                from algorithms.routing.two_opt import nn_then_2opt
                route, dist = nn_then_2opt(batch.locations, warehouse)
            batch.route = route
            batch.travel_distance = dist
            total_distance += dist

        return Solution(
            algorithm_name=self.name,
            batches=batches,
            total_travel_distance=total_distance,
        )


if __name__ == "__main__":
    from core.data_loader import DataLoader
    from core.warehouse import Warehouse

    loader = DataLoader()
    wh = Warehouse()

    sub = loader.load_orders(1, 1, 20)
    test_orders = sub.orders[:50]

    algo = FCFS()
    solution = algo.solve(test_orders, wh)

    print(f"FCFS sonucu:")
    for k, v in solution.summary().items():
        print(f"  {k}: {v}")
