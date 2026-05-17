"""
algorithms/base.py
==================
Tüm batching+routing algoritmaları için ortak interface ve sonuç tipleri.

DEPSO, RBRS-AE, baseline'lar — hepsi aynı arayüzü kullanır:
    algorithm.solve(orders, warehouse) → Solution

Bu, karşılaştırma sayfasında tek satırlık kıyaslama yapabilmeyi sağlar.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Protocol
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.data_loader import Order


# ════════════════════════════════════════════════════════════════════════════
# SONUÇ VERİ TİPLERİ
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Batch:
    """Bir picking batch'i: kapasiteye uyan siparişler topluluğu."""
    batch_id: int
    orders: list[Order] = field(default_factory=list)
    total_weight: float = 0.0
    route: list[int] = field(default_factory=list)  # depot dahil lokasyon dizisi
    travel_distance: float = 0.0

    @property
    def locations(self) -> list[int]:
        """Bu batch'in ziyaret etmesi gereken benzersiz lokasyonlar."""
        locs = set()
        for o in self.orders:
            locs.update(o.locations)
        return sorted(locs)

    @property
    def num_orderlines(self) -> int:
        return sum(o.num_orderlines for o in self.orders)


@dataclass
class Solution:
    """Bir algoritmanın bir problem instance'ına verdiği tam çözüm."""
    algorithm_name: str
    batches: list[Batch] = field(default_factory=list)
    total_travel_distance: float = 0.0
    runtime_seconds: float = 0.0

    # Opsiyonel metrikler (algoritma bazlı)
    iterations_used: int = 0
    convergence_history: list[float] = field(default_factory=list)
    extra_info: dict = field(default_factory=dict)

    @property
    def num_batches(self) -> int:
        return len(self.batches)

    @property
    def num_orders(self) -> int:
        return sum(len(b.orders) for b in self.batches)

    @property
    def num_orderlines(self) -> int:
        return sum(b.num_orderlines for b in self.batches)

    @property
    def avg_distance_per_batch(self) -> float:
        if not self.batches:
            return 0.0
        return self.total_travel_distance / len(self.batches)

    @property
    def avg_capacity_utilization(self) -> float:
        """Ortalama batch doluluk oranı (0-1)."""
        from config import ITEMS
        cap = ITEMS['picker_capacity_WU']
        if not self.batches:
            return 0.0
        return sum(b.total_weight for b in self.batches) / (cap * len(self.batches))

    def summary(self) -> dict:
        return {
            'algorithm': self.algorithm_name,
            'total_distance_LU': round(self.total_travel_distance, 2),
            'num_batches': self.num_batches,
            'num_orders': self.num_orders,
            'num_orderlines': self.num_orderlines,
            'avg_distance_per_batch': round(self.avg_distance_per_batch, 2),
            'avg_capacity_utilization': round(self.avg_capacity_utilization, 3),
            'runtime_sec': round(self.runtime_seconds, 2),
            'iterations_used': self.iterations_used,
        }

    def __repr__(self) -> str:
        return (f"Solution({self.algorithm_name}: "
                f"dist={self.total_travel_distance:.1f}, "
                f"batches={self.num_batches}, runtime={self.runtime_seconds:.2f}s)")


# ════════════════════════════════════════════════════════════════════════════
# INTERFACE
# ════════════════════════════════════════════════════════════════════════════

class BatchingRoutingAlgorithm(ABC):
    """
    Tüm batching+routing algoritmalarının uygulayacağı soyut sınıf.

    Kullanım:
        algo = DEPSO(num_particles=5, num_iterations=500)
        solution = algo.solve(orders, warehouse)
        print(solution.total_travel_distance)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Algoritmanın görünür adı (örn. 'DEPSO', 'RBRS-AE', 'SOP+S-Shape')."""
        ...

    @abstractmethod
    def _solve_impl(self, orders: list[Order], warehouse) -> Solution:
        """
        Asıl çözüm mantığı. Alt sınıflar bunu implement eder.
        runtime ölçümü solve() içinde yapılır.
        """
        ...

    def solve(self, orders: list[Order], warehouse) -> Solution:
        """
        Ana giriş noktası. Runtime'ı otomatik ölçer.

        orders: çözülecek siparişler
        warehouse: Warehouse nesnesi (mesafe için)

        Döndürür: Solution
        """
        t0 = time.perf_counter()
        solution = self._solve_impl(orders, warehouse)
        solution.runtime_seconds = time.perf_counter() - t0
        solution.algorithm_name = self.name
        return solution


# ════════════════════════════════════════════════════════════════════════════
# YARDIMCI FONKSİYON: TOUR DISTANCE
# ════════════════════════════════════════════════════════════════════════════

def compute_route_distance(route: list[int], warehouse) -> float:
    """
    Bir rotanın toplam mesafesini hesaplar.
    route: [depot, loc1, loc2, ..., depot] gibi lokasyon dizisi.
    """
    if len(route) < 2:
        return 0.0
    total = 0.0
    for i in range(len(route) - 1):
        total += warehouse.distance(route[i], route[i + 1])
    return total
