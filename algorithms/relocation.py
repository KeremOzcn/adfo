"""
algorithms/relocation.py
=========================
Dynamic Storage Location Assignment — Paper Section 5.3, 6.4

Her periyot sonunda:
1) Holt-Winters ile gelecek periyot tahmini yapılır
2) Tahmin bazlı ABC sınıflandırması yapılır
3) Yanlış sınıftaki itemler belirlenir (eşik o=2 periyot)
4) Relocation önerileri test edilir:
   - Relocation effort hesaplanır (Em_dis + Em_phy + Em_adm)
   - Taşıma sonrası travel distance azalması tahmin edilir
   - Azalma > effort ise taşı, değilse at
5) Max 50 öneri test edilir

Relocation effort bileşenleri:
  E_dis = depot ↔ current loc + current loc ↔ target loc mesafesi
  E_phy = t_phy × v_pick = 180 LU
  E_adm = t_adm × v_pick = 60 LU
  E_total = E_dis + E_phy + E_adm

Kabul kriteri (paper):
  TDR_rel > 0  (anlık azalma)
  VE_future > E_total - TDR_rel  (gelecek kazanç)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DYNAMIC_STORAGE, ITEMS, WAREHOUSE
from core.data_loader import Order


# ════════════════════════════════════════════════════════════════════════════
# VERİ SINIFLARI
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class ItemState:
    """Bir itemin mevcut durumu."""
    item_id: int
    location: int
    current_class: str       # 'A', 'B', 'C'
    forecast_class: str      # tahmin bazlı sınıf
    periods_in_wrong_class: int = 0
    periods_in_target_class: int = 0  # tahmin bazlı hedef sınıfta kalma


@dataclass
class RelocationResult:
    """Bir periyodun relocation sonuçları."""
    period: int
    num_suggestions_tested: int = 0
    num_accepted: int = 0
    num_rejected: int = 0
    total_relocation_effort_LU: float = 0.0
    travel_distance_before: float = 0.0
    travel_distance_after: float = 0.0

    @property
    def travel_distance_reduction(self) -> float:
        return self.travel_distance_before - self.travel_distance_after

    @property
    def reduction_pct(self) -> float:
        if self.travel_distance_before == 0:
            return 0.0
        return self.travel_distance_reduction / self.travel_distance_before * 100

    @property
    def relocation_effort_pct(self) -> float:
        if self.travel_distance_before == 0:
            return 0.0
        return self.total_relocation_effort_LU / self.travel_distance_before * 100

    @property
    def net_improvement_pct(self) -> float:
        return self.reduction_pct - self.relocation_effort_pct


# ════════════════════════════════════════════════════════════════════════════
# DYNAMIC RELOCATION ALGORİTMASI
# ════════════════════════════════════════════════════════════════════════════

class DynamicRelocation:
    """
    Paper Section 5.3 — Dynamic Storage Location Assignment.

    Kullanım:
        reloc = DynamicRelocation(warehouse, location_classes)
        reloc.initialize(item_locations, item_classes)

        for period in range(9):
            orders = load_orders(period)
            result = reloc.run_period(period, orders, forecaster, algorithm)
    """

    # Fiziksel + admin efor (paper Table 2)
    E_PHY = ITEMS['physical_effort_LU']   # 180 LU
    E_ADM = ITEMS['admin_effort_LU']      # 60 LU

    def __init__(self, warehouse, location_classes: dict[str, list[int]]):
        self.wh = warehouse
        self.location_classes = location_classes  # {'A': [...], 'B': [...], 'C': [...]}

        # Item durumları
        self.item_states: dict[int, ItemState] = {}

        # Lokasyon → item mapping (hangi lokasyonda hangi item var)
        self.loc_to_item: dict[int, int] = {}

        # Boş lokasyonlar (her sınıf için)
        self.empty_locs: dict[str, list[int]] = {'A': [], 'B': [], 'C': []}

        # Config
        self.o = DYNAMIC_STORAGE['min_periods_in_wrong_class_o']   # 2
        self.u = DYNAMIC_STORAGE['min_periods_in_target_class_u']  # 1
        self.max_suggestions = DYNAMIC_STORAGE['max_relocation_suggestions']  # 50

    # ──────────────────────────────────────────────────────────────
    # BAŞLANGIÇ
    # ──────────────────────────────────────────────────────────────

    def initialize(self, item_locations: list[int],
                   item_classes: list[str]) -> None:
        """
        Period 1 başlangıç durumunu ayarla.
        item_locations: her item için başlangıç lokasyonu
        item_classes: period 1 ABC sınıfları
        """
        self.item_states = {}
        self.loc_to_item = {}

        for item_id, (loc, cls) in enumerate(zip(item_locations, item_classes)):
            self.item_states[item_id] = ItemState(
                item_id=item_id,
                location=loc,
                current_class=cls,
                forecast_class=cls,
            )
            self.loc_to_item[loc] = item_id

        # Boş lokasyonlar
        occupied = set(item_locations)
        for cls, locs in self.location_classes.items():
            self.empty_locs[cls] = [l for l in locs if l not in occupied]

    # ──────────────────────────────────────────────────────────────
    # PERİYOT ÇALIŞMASI
    # ──────────────────────────────────────────────────────────────

    def run_period(self, period: int, orders: list[Order],
                   forecasts: list[float], algorithm) -> RelocationResult:
        """
        Bir periyodun relocation sürecini çalıştır.

        period: test periyot numarası (1-9)
        orders: bu periyodun siparişleri
        forecasts: Holt-Winters'tan gelen item başına orderline tahmini
        algorithm: BatchingRoutingAlgorithm (DEPSO veya RBRS-AE)

        Döndürür: RelocationResult
        """
        result = RelocationResult(period=period)

        # 1) Tahmin bazlı ABC sınıflandırması
        forecast_classes = self._classify_by_forecast(forecasts)
        self._update_class_tracking(forecast_classes)

        # 2) Relocation öncelik listesi (yanlış sınıftaki itemler)
        priority_list = self._build_priority_list()
        if not priority_list:
            return result

        # 3) Mevcut travel distance (relokasyon olmadan)
        td_before = self._compute_td(orders, algorithm)
        result.travel_distance_before = td_before
        td_comparison = td_before

        # 4) Relocation önerileri test et
        tested = 0
        while priority_list and tested < self.max_suggestions:
            # En yüksek öncelikli ascending item seç
            asc_item = priority_list.pop(0)
            target_cls = asc_item.forecast_class

            # Exchange senaryosu seç (1→4 öncelik sırasıyla)
            suggestion = self._find_exchange(asc_item, target_cls, priority_list)
            if suggestion is None:
                tested += 1
                continue

            # Relocation effort hesapla
            effort = self._compute_effort(suggestion)

            # Taşıma sonrası TD hesapla
            self._apply_suggestion(suggestion)
            td_after = self._compute_td(orders, algorithm)
            tdr = td_comparison - td_after   # anlık azalma

            if tdr <= 0:
                # Azalma yok → geri al
                self._undo_suggestion(suggestion)
                priority_list.append(asc_item)  # listeden çıkar
                tested += 1
                result.num_rejected += 1
                continue

            # Gelecek kazancı tahmin et (paper Section 5.3.5)
            future_gain = self._estimate_future_gain(suggestion, forecasts)

            if future_gain + tdr > effort:
                # Kabul
                td_comparison = td_after
                result.num_accepted += 1
                result.total_relocation_effort_LU += effort
            else:
                # Reddet → geri al
                self._undo_suggestion(suggestion)
                result.num_rejected += 1

            tested += 1
            result.num_suggestions_tested += 1

        result.travel_distance_after = td_comparison
        return result

    # ──────────────────────────────────────────────────────────────
    # SINIFLANDIRMA
    # ──────────────────────────────────────────────────────────────

    def _classify_by_forecast(self, forecasts: list[float]) -> dict[int, str]:
        """Tahmin değerlerine göre ABC sınıfı ata."""
        n = len(forecasts)
        n_a = int(n * WAREHOUSE['class_A_pct'])
        n_b = int(n * WAREHOUSE['class_B_pct'])

        sorted_items = sorted(range(n), key=lambda i: -forecasts[i])
        classes = {}
        for rank, item_id in enumerate(sorted_items):
            if rank < n_a:
                classes[item_id] = 'A'
            elif rank < n_a + n_b:
                classes[item_id] = 'B'
            else:
                classes[item_id] = 'C'
        return classes

    def _update_class_tracking(self, forecast_classes: dict[int, str]) -> None:
        """Her item için yanlış sınıfta geçirilen periyot sayısını güncelle."""
        for item_id, state in self.item_states.items():
            fc = forecast_classes.get(item_id, state.current_class)
            state.forecast_class = fc

            if fc != state.current_class:
                state.periods_in_wrong_class += 1
                state.periods_in_target_class = 0
            else:
                state.periods_in_wrong_class = 0
                state.periods_in_target_class += 1

    def _build_priority_list(self) -> list[ItemState]:
        """
        Relocation öncelik listesi: yanlış sınıfta >= o periyot olan itemler.
        Öncelik: forecast_class ile current_class farkı büyük olanlar önce.
        """
        class_order = {'A': 0, 'B': 1, 'C': 2}

        candidates = []
        for state in self.item_states.values():
            if (state.periods_in_wrong_class >= self.o and
                    state.periods_in_target_class >= 0):
                # Ascending (C→B, C→A, B→A) veya descending
                gap = (class_order[state.current_class] -
                       class_order[state.forecast_class])
                if gap > 0:  # ascending: daha üst sınıfa taşınmalı
                    candidates.append((gap, state))

        # Gap büyüklüğüne göre sırala (en büyük gap önce)
        candidates.sort(key=lambda x: -x[0])
        return [state for _, state in candidates]

    # ──────────────────────────────────────────────────────────────
    # EXCHANGE SENARYO
    # ──────────────────────────────────────────────────────────────

    def _find_exchange(self, asc_item: ItemState, target_cls: str,
                       priority_list: list[ItemState]) -> dict | None:
        """
        4 exchange senaryosundan en uygununu bul.
        Senaryo 1: Boş lokasyona taşı (en basit)
        Senaryo 2: Descending item ile doğrudan takas
        Senaryo 3: Dolaylı takas (üçüncü sınıf boş yer)
        Senaryo 4: Üç item rotasyonu
        """
        # Senaryo 1: boş lokasyon var mı?
        if self.empty_locs.get(target_cls):
            target_loc = self.empty_locs[target_cls][0]
            return {
                'type': 1,
                'asc_item': asc_item,
                'asc_new_loc': target_loc,
                'desc_item': None,
                'desc_new_loc': None,
            }

        # Senaryo 2: priority listesinde descending item var mı?
        asc_cls = asc_item.current_class
        for desc in priority_list:
            if (desc.current_class == target_cls and
                    desc.forecast_class == asc_cls):
                return {
                    'type': 2,
                    'asc_item': asc_item,
                    'asc_new_loc': desc.location,
                    'desc_item': desc,
                    'desc_new_loc': asc_item.location,
                }

        # Senaryo 3: target sınıfından bir item boş yere taşınabilir mi?
        third_cls = 'C' if target_cls in ('A', 'B') else 'B'
        if self.empty_locs.get(third_cls):
            # target sınıfında en düşük öncelikli item'i bul
            target_items = [s for s in self.item_states.values()
                            if s.current_class == target_cls]
            if target_items:
                # Depot'a en yakın olanı seç (paper: en yakın)
                bridge = min(target_items,
                             key=lambda s: self.wh.dist_m(self.wh.DEPOT, s.location))
                bridge_new_loc = self.empty_locs[third_cls][0]
                return {
                    'type': 3,
                    'asc_item': asc_item,
                    'asc_new_loc': bridge.location,
                    'desc_item': bridge,
                    'desc_new_loc': bridge_new_loc,
                }

        return None  # Hiçbir senaryo uygun değil

    # ──────────────────────────────────────────────────────────────
    # EFFORT HESABI
    # ──────────────────────────────────────────────────────────────

    def _compute_effort(self, suggestion: dict) -> float:
        """
        E_total = E_dis + E_phy + E_adm  (her item için)
        E_dis = depot → current → target mesafesi
        """
        df = self.wh.dist_m
        depot = self.wh.DEPOT
        total = 0.0

        # Ascending item
        asc = suggestion['asc_item']
        e_dis_asc = df(depot, asc.location) + df(asc.location, suggestion['asc_new_loc'])
        total += e_dis_asc + self.E_PHY + self.E_ADM

        # Descending item (varsa)
        desc = suggestion.get('desc_item')
        if desc and suggestion.get('desc_new_loc'):
            e_dis_desc = df(depot, desc.location) + df(desc.location, suggestion['desc_new_loc'])
            total += e_dis_desc + self.E_PHY + self.E_ADM

        return total

    # ──────────────────────────────────────────────────────────────
    # APPLY / UNDO
    # ──────────────────────────────────────────────────────────────

    def _apply_suggestion(self, suggestion: dict) -> None:
        """Relocation önerisini uygula (item lokasyonlarını güncelle)."""
        asc = suggestion['asc_item']
        old_loc = asc.location
        new_loc = suggestion['asc_new_loc']
        target_cls = asc.forecast_class

        # Undo için orijinal state'i kaydet
        suggestion['_orig_asc_loc'] = old_loc
        suggestion['_orig_asc_cls'] = asc.current_class

        # Ascending item'ı taşı
        self.loc_to_item.pop(old_loc, None)
        self.loc_to_item[new_loc] = asc.item_id
        if new_loc in self.empty_locs.get(target_cls, []):
            self.empty_locs[target_cls].remove(new_loc)
        self.empty_locs.setdefault(asc.current_class, []).append(old_loc)
        asc.location = new_loc
        asc.current_class = target_cls

        # Descending item'ı taşı (varsa)
        desc = suggestion.get('desc_item')
        if desc and suggestion.get('desc_new_loc'):
            old_d = desc.location
            new_d = suggestion['desc_new_loc']
            desc_cls = desc.forecast_class
            suggestion['_orig_desc_loc'] = old_d
            suggestion['_orig_desc_cls'] = desc.current_class
            self.loc_to_item.pop(old_d, None)
            self.loc_to_item[new_d] = desc.item_id
            if new_d in self.empty_locs.get(desc_cls, []):
                self.empty_locs[desc_cls].remove(new_d)
            self.empty_locs.setdefault(desc.current_class, []).append(old_d)
            desc.location = new_d
            desc.current_class = desc_cls

    def _undo_suggestion(self, suggestion: dict) -> None:
        """Relocation önerisini geri al — loc_to_item ve empty_locs tam restore."""
        asc      = suggestion['asc_item']
        new_loc  = asc.location                          # apply sonrası konum
        old_loc  = suggestion.get('_orig_asc_loc', new_loc)
        orig_cls = suggestion.get('_orig_asc_cls', asc.current_class)
        cur_cls  = asc.current_class                     # apply sonrası sınıf

        # loc_to_item geri al
        self.loc_to_item.pop(new_loc, None)
        self.loc_to_item[old_loc] = asc.item_id

        # empty_locs geri al
        if new_loc not in self.empty_locs.get(cur_cls, []):
            self.empty_locs.setdefault(cur_cls, []).append(new_loc)
        if old_loc in self.empty_locs.get(orig_cls, []):
            self.empty_locs[orig_cls].remove(old_loc)

        asc.location      = old_loc
        asc.current_class = orig_cls

        # Descending item (varsa)
        desc = suggestion.get('desc_item')
        if desc and '_orig_desc_loc' in suggestion:
            d_new      = desc.location
            d_old      = suggestion['_orig_desc_loc']
            d_orig_cls = suggestion['_orig_desc_cls']
            d_cur_cls  = desc.current_class

            self.loc_to_item.pop(d_new, None)
            self.loc_to_item[d_old] = desc.item_id

            if d_new not in self.empty_locs.get(d_cur_cls, []):
                self.empty_locs.setdefault(d_cur_cls, []).append(d_new)
            if d_old in self.empty_locs.get(d_orig_cls, []):
                self.empty_locs[d_orig_cls].remove(d_old)

            desc.location      = d_old
            desc.current_class = d_orig_cls

    # ──────────────────────────────────────────────────────────────
    # TRAVEL DISTANCE HESABI
    # ──────────────────────────────────────────────────────────────

    def _compute_td(self, orders: list[Order], algorithm) -> float:
        """
        Mevcut item lokasyonlarıyla travel distance hesapla.
        NN+2opt kullanılır — QA önerisi: pure NN yerine daha doğru tahmin.
        """
        from algorithms.routing.two_opt import nn_then_2opt
        from algorithms.batching.first_fit import first_fit_batching

        updated_orders = self._update_order_locations(orders)
        batches = first_fit_batching(updated_orders)
        total = 0.0
        for b in batches:
            _, dist = nn_then_2opt(b.locations, self.wh)
            total += dist
        return total

    def _update_order_locations(self, orders: list[Order]) -> list[Order]:
        """Her orderline'ın lokasyonunu mevcut item state'e göre güncelle."""
        from copy import deepcopy
        from core.data_loader import OrderLine

        updated = []
        for o in orders:
            new_ols = []
            for ol in o.orderlines:
                state = self.item_states.get(ol.item)
                new_loc = state.location if state else ol.location
                new_ols.append(OrderLine(
                    item=ol.item, quantity=ol.quantity,
                    location=new_loc, weight=ol.weight
                ))
            from core.data_loader import Order as Ord
            new_o = Ord(order_id=o.order_id, num_orderlines=o.num_orderlines,
                        total_weight=o.total_weight, orderlines=new_ols)
            updated.append(new_o)
        return updated

    def _estimate_future_gain(self, suggestion: dict,
                              forecasts: list[float]) -> float:
        """
        Paper Section 5.3.5: gelecek periyot kazancını tahmin et.
        Basit yaklaşım: taşınan item'ın mevcut + hedef sınıf
        depot mesafesi farkı × tahmini orderline sayısı
        """
        asc = suggestion['asc_item']
        df = self.wh.dist_m
        depot = self.wh.DEPOT

        # Mevcut lokasyon vs hedef lokasyon depot mesafesi
        cur_dist = df(depot, suggestion.get('_orig_asc_loc', asc.location))
        new_dist = df(depot, suggestion['asc_new_loc'])
        dist_saving = cur_dist - new_dist

        # Tahmini orderline sayısı
        forecast_ol = forecasts[asc.item_id] if asc.item_id < len(forecasts) else 1.0

        # Her orderline için yaklaşık 2× tur (gidip dön)
        gain = max(0.0, dist_saving * forecast_ol * 2)
        return gain


# ════════════════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import numpy as np
    from core.data_loader import DataLoader
    from core.warehouse import Warehouse
    from core.forecasting import ItemForecaster
    from algorithms.depso import DEPSO

    loader = DataLoader()
    wh     = Warehouse()

    print("=" * 60)
    print("Dynamic Storage Relocation Test")
    print("=" * 60)

    # Item metadata
    items = loader.load_items()
    item_locations = [it.initial_location for it in items]
    item_classes   = [it.class_period1    for it in items]

    # Lokasyon sınıfları
    loc_classes = loader.load_location_classes()

    # Relocation sistemi
    reloc = DynamicRelocation(wh, loc_classes)
    reloc.initialize(item_locations, item_classes)

    # Holt-Winters
    demand = loader.load_scenario_demand(1)
    forecaster = ItemForecaster()
    forecaster.fit_all(demand, warmup_periods=12)

    # DEPSO (küçük instance ile test)
    algo = DEPSO(num_iterations=50, seed=42)

    print("\nTest periyotları (küçük instance — 30 sipariş):")
    print(f"{'Periyot':<8} {'Test Sug':>8} {'Kabul':>6} {'TD Önce':>10} "
          f"{'TD Sonra':>10} {'Azalma%':>8} {'Effort%':>8} {'Net%':>6}")
    print("-" * 70)

    total_results = []
    for period in range(1, 4):  # Sadece 3 periyot (hızlı test)
        orders = loader.load_orders(1, period, 1).orders[:30]
        forecasts = forecaster.predict_all(tau=1)

        result = reloc.run_period(period, orders, forecasts, algo)

        # Forecaster güncelle
        forecaster.update_all(demand[:, 11 + period])  # gerçek talep

        total_results.append(result)
        print(f"{period:<8} {result.num_suggestions_tested:>8} "
              f"{result.num_accepted:>6} "
              f"{result.travel_distance_before:>10.1f} "
              f"{result.travel_distance_after:>10.1f} "
              f"{result.reduction_pct:>8.2f}% "
              f"{result.relocation_effort_pct:>8.2f}% "
              f"{result.net_improvement_pct:>6.2f}%")

    # Ortalama
    avg_reduction = sum(r.reduction_pct for r in total_results) / len(total_results)
    avg_effort    = sum(r.relocation_effort_pct for r in total_results) / len(total_results)
    avg_net       = sum(r.net_improvement_pct for r in total_results) / len(total_results)
    print("-" * 70)
    print(f"{'Ortalama':<8} {'':>8} {'':>6} {'':>10} {'':>10} "
          f"{avg_reduction:>8.2f}% {avg_effort:>8.2f}% {avg_net:>6.2f}%")

    print()
    print("Paper hedefleri (Senaryo 1, 9 periyot):")
    print("  Travel distance azalma: ~15%")
    print("  Relocation effort:      ~2.79%")
    print("  Net iyileşme:           ~12.23%")
