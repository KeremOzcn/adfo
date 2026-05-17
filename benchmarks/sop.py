"""
benchmarks/sop.py
=================
Single Order Picking (SOP) baseline.

En basit yaklaşım: her sipariş tek başına picked.
Hiç batching yok.

Bu, paper'ın en kötü benchmark'ı — DEPSO buna göre %83 iyileşme sağlıyor.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.data_loader import Order
from algorithms.base import BatchingRoutingAlgorithm, Batch, Solution
from algorithms.routing.s_shape import s_shape_route


class SOP(BatchingRoutingAlgorithm):
    """
    Single Order Picking + S-Shape routing.
    Her siparişi tek başına S-Shape ile gez.
    """

    def __init__(self, routing: str = "s_shape"):
        self.routing = routing

    @property
    def name(self) -> str:
        return f"SOP+{self.routing.upper()}"

    def _solve_impl(self, orders: list[Order], warehouse) -> Solution:
        batches: list[Batch] = []
        total_distance = 0.0

        for i, order in enumerate(orders):
            # Her sipariş kendi batch'i
            if self.routing == "s_shape":
                route, dist = s_shape_route(order.locations, warehouse)
            else:
                from algorithms.routing.two_opt import nn_then_2opt
                route, dist = nn_then_2opt(order.locations, warehouse)

            batch = Batch(
                batch_id=i,
                orders=[order],
                total_weight=order.total_weight,
                route=route,
                travel_distance=dist,
            )
            batches.append(batch)
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

    algo = SOP()
    solution = algo.solve(test_orders, wh)

    print(f"SOP sonucu:")
    for k, v in solution.summary().items():
        print(f"  {k}: {v}")
