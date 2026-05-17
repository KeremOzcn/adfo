"""
core/data_loader.py
===================
Dataset'i JSON dosyalarından okur ve algoritmaların kullanabileceği
nesnelere dönüştürür.

Dataset, paper'ın parametrelerine göre Python ile üretilmiş.
(bkz. warehouse_dataset_generator.py)
"""

from dataclasses import dataclass, field
from pathlib import Path
import json
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DATA_DIR, TIME_SERIES


# ════════════════════════════════════════════════════════════════════════════
# VERİ SINIFLARI
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Item:
    """Bir ürünün metadata'sı."""
    item_id: int
    weight_WU: float
    class_period1: str          # 'A', 'B', 'C'
    orderlines_period1: int
    initial_location: int


@dataclass
class OrderLine:
    """Bir siparişteki tek satır."""
    item: int           # item ID
    quantity: int
    location: int       # lokasyon ID
    weight: float       # quantity × item_weight (toplam WU)


@dataclass
class Order:
    """Tek bir müşteri siparişi."""
    order_id: int
    num_orderlines: int
    total_weight: float
    orderlines: list[OrderLine] = field(default_factory=list)

    @property
    def locations(self) -> list[int]:
        """Bu siparişin ziyaret edeceği lokasyonlar."""
        return [ol.location for ol in self.orderlines]

    @property
    def items(self) -> list[int]:
        return [ol.item for ol in self.orderlines]


@dataclass
class SubPeriodOrders:
    """Bir alt-periyodun tüm siparişleri."""
    scenario: int
    period: int          # 1..9 (test periyotları)
    subperiod: int       # 1..20
    orders: list[Order] = field(default_factory=list)

    @property
    def num_orders(self) -> int:
        return len(self.orders)

    @property
    def total_orderlines(self) -> int:
        return sum(o.num_orderlines for o in self.orders)


# ════════════════════════════════════════════════════════════════════════════
# OKUMA FONKSİYONLARI
# ════════════════════════════════════════════════════════════════════════════

class DataLoader:
    """Tüm dataset'i yükler ve sorgulanabilir hale getirir."""

    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"Veri dizini bulunamadı: {self.data_dir}")

        # Tembel yükleme (lazy loading): büyük dosyalar lazım olunca okunur
        self._items_cache: list[Item] | None = None
        self._location_classes_cache: dict | None = None
        self._scenario_demand_cache: dict[int, np.ndarray] = {}

    # ────────────────────────────────────────────────────────────
    # WAREHOUSE LAYOUT
    # ────────────────────────────────────────────────────────────

    def load_warehouse_layout(self) -> dict:
        """warehouse_layout.json"""
        with open(self.data_dir / "warehouse_layout.json") as f:
            return json.load(f)

    # ────────────────────────────────────────────────────────────
    # LOKASYON SINIFLARI
    # ────────────────────────────────────────────────────────────

    def load_location_classes(self) -> dict[str, list[int]]:
        """A, B, C sınıflarındaki tüm lokasyon ID'leri."""
        if self._location_classes_cache is not None:
            return self._location_classes_cache

        result = {}
        for cls in ['A', 'B', 'C']:
            with open(self.data_dir / f"location_class_{cls}.json") as f:
                result[cls] = json.load(f)

        self._location_classes_cache = result
        return result

    # ────────────────────────────────────────────────────────────
    # ÜRÜNLER
    # ────────────────────────────────────────────────────────────

    def load_items(self) -> list[Item]:
        """6000 ürünün metadata'sı."""
        if self._items_cache is not None:
            return self._items_cache

        with open(self.data_dir / "items_metadata.json") as f:
            data = json.load(f)

        items = [
            Item(
                item_id=item['item_id'],
                weight_WU=item['weight_WU'],
                class_period1=item['class_period1'],
                orderlines_period1=item['orderlines_period1'],
                initial_location=item['initial_location'],
            )
            for item in data['items']
        ]
        self._items_cache = items
        return items

    def item_weights_array(self) -> np.ndarray:
        """Hızlı erişim için: items[i].weight_WU dizisi."""
        return np.array([it.weight_WU for it in self.load_items()])

    def item_locations_array(self) -> np.ndarray:
        """items[i].initial_location dizisi."""
        return np.array([it.initial_location for it in self.load_items()])

    # ────────────────────────────────────────────────────────────
    # SENARYO TALEP MATRISI
    # ────────────────────────────────────────────────────────────

    def load_scenario_demand(self, scenario: int) -> np.ndarray:
        """
        Senaryo için (num_items × num_periods) talep matrisi.
        Senaryo 1 veya 2.
        """
        if scenario in self._scenario_demand_cache:
            return self._scenario_demand_cache[scenario]

        if scenario not in (1, 2):
            raise ValueError(f"Geçersiz senaryo: {scenario}")

        with open(self.data_dir / f"items_scenario{scenario}.json") as f:
            data = json.load(f)

        matrix = np.array(data['demand_matrix'], dtype=np.int32)
        self._scenario_demand_cache[scenario] = matrix
        return matrix

    def load_scenario_metadata(self, scenario: int) -> dict:
        """Senaryonun parametreleri (Tf, Sf, vb.)."""
        with open(self.data_dir / f"items_scenario{scenario}.json") as f:
            data = json.load(f)
        return data['parameters']

    # ────────────────────────────────────────────────────────────
    # SİPARİŞLER
    # ────────────────────────────────────────────────────────────

    def load_orders(self, scenario: int, period: int, subperiod: int) -> SubPeriodOrders:
        """
        Belirli bir senaryonun, periyodun, alt-periyodun siparişleri.

        scenario: 1 veya 2
        period: 1..9 (test periyotları)
        subperiod: 1..20
        """
        fname = (
            f"orders_s{scenario}_period{period:02d}_sub{subperiod:02d}.json"
        )
        path = self.data_dir / fname
        if not path.exists():
            raise FileNotFoundError(f"Sipariş dosyası yok: {path}")

        with open(path) as f:
            data = json.load(f)

        orders = []
        for o in data['orders']:
            orderlines = [
                OrderLine(
                    item=ol['item'],
                    quantity=ol['quantity'],
                    location=ol['location'],
                    weight=ol['weight'],
                )
                for ol in o['orderlines']
            ]
            orders.append(Order(
                order_id=o['order_id'],
                num_orderlines=o['num_orderlines'],
                total_weight=o['total_weight'],
                orderlines=orderlines,
            ))

        return SubPeriodOrders(
            scenario=data['scenario'],
            period=data['period'],
            subperiod=data['subperiod'],
            orders=orders,
        )

    def load_period_orders(self, scenario: int, period: int) -> list[SubPeriodOrders]:
        """Bir periyodun tüm alt-periyot siparişleri (20 tane)."""
        return [
            self.load_orders(scenario, period, sub)
            for sub in range(1, TIME_SERIES['num_subperiods'] + 1)
        ]

    def all_orders_in_period(self, scenario: int, period: int) -> list[Order]:
        """Bir periyodun tüm siparişlerini düz bir listede topla."""
        all_orders = []
        for sub_orders in self.load_period_orders(scenario, period):
            all_orders.extend(sub_orders.orders)
        # ID'leri yeniden numarala (global)
        for k, o in enumerate(all_orders):
            o.order_id = k
        return all_orders

    # ────────────────────────────────────────────────────────────
    # ÖZET
    # ────────────────────────────────────────────────────────────

    def summary(self) -> dict:
        items = self.load_items()
        classes = self.load_location_classes()
        scen1 = self.load_scenario_demand(1)
        scen2 = self.load_scenario_demand(2)

        return {
            'num_items': len(items),
            'item_class_distribution': {
                cls: sum(1 for it in items if it.class_period1 == cls)
                for cls in ['A', 'B', 'C']
            },
            'location_class_sizes': {cls: len(locs) for cls, locs in classes.items()},
            'scenario1_shape': scen1.shape,
            'scenario1_total_demand_per_period': scen1.sum(axis=0).tolist(),
            'scenario2_shape': scen2.shape,
            'scenario2_total_demand_per_period': scen2.sum(axis=0).tolist(),
        }


# ════════════════════════════════════════════════════════════════════════════
# HIZLI TEST
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    loader = DataLoader()

    print("Dataset özeti:")
    summary = loader.summary()
    print(f"  Ürün sayısı: {summary['num_items']}")
    print(f"  Ürün sınıf dağılımı: {summary['item_class_distribution']}")
    print(f"  Lokasyon sınıf boyutları: {summary['location_class_sizes']}")
    print(f"  Senaryo 1 matris: {summary['scenario1_shape']}")
    print(f"  Senaryo 1 periyot toplamları (ilk 5):")
    print(f"    {summary['scenario1_total_demand_per_period'][:5]}")
    print(f"  Senaryo 2 periyot toplamları (ilk 5):")
    print(f"    {summary['scenario2_total_demand_per_period'][:5]}")

    print()
    print("Örnek sipariş yükleme: Senaryo 1, Periyot 1, Alt-periyot 1")
    sub = loader.load_orders(scenario=1, period=1, subperiod=1)
    print(f"  Toplam sipariş: {sub.num_orders}")
    print(f"  Toplam orderline: {sub.total_orderlines}")
    print(f"  İlk siparişin orderline sayısı: {sub.orders[0].num_orderlines}")
    print(f"  İlk siparişin toplam ağırlığı: {sub.orders[0].total_weight} WU")
    if sub.orders[0].orderlines:
        ol = sub.orders[0].orderlines[0]
        print(f"  İlk orderline: item={ol.item}, lokasyon={ol.location}, qty={ol.quantity}")

    print()
    print("Periyot 1 toplam (S1):")
    all_p1 = loader.all_orders_in_period(scenario=1, period=1)
    print(f"  Toplam sipariş: {len(all_p1)}")
    print(f"  Toplam orderline: {sum(o.num_orderlines for o in all_p1)}")
    print(f"  Toplam ağırlık: {sum(o.total_weight for o in all_p1):.1f} WU")
