"""
algorithms/rbrs_ae.py
======================
RBRS-AE: Route-Based Regret Search with Adaptive Elimination

Spec:
1) Priority(o) = 0.5*AvgDist + 0.3*Variance + 0.2*Weight  (1 kez, başlangıçta)
2) Regret-based initial assignment
3) Iterative: Shift → Swap → Adaptive Elimination (100 iter, 15 no-imp)
4) I(b) = 0.7*(dist/orderCount) + 0.3*(1-utilization)
5) Routing: NN + 2-opt
"""

from __future__ import annotations
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_loader import Order
from algorithms.base import BatchingRoutingAlgorithm, Batch, Solution
from algorithms.routing.nearest_neighbor import nearest_neighbor_route
from algorithms.routing.two_opt import two_opt_improve
from config import ITEMS, RBRS_AE as RBRS_CONFIG


class RBRS_AE(BatchingRoutingAlgorithm):

    def __init__(self, max_iterations=None, max_no_improvement=None,
                 shift_attempts=None, swap_attempts=None,
                 seed=None, verbose=False):
        self.max_iterations     = max_iterations     or RBRS_CONFIG['max_iterations']
        self.max_no_improvement = max_no_improvement or RBRS_CONFIG['max_no_improvement']
        self.shift_attempts     = shift_attempts     or RBRS_CONFIG['shift_attempts']
        self.swap_attempts      = swap_attempts      or RBRS_CONFIG['swap_attempts']
        self.capacity           = ITEMS['picker_capacity_WU']
        self.verbose            = verbose
        self._rng               = random.Random(seed)
        self._wh                = None
        self.convergence_history: list[float] = []

    @property
    def name(self) -> str:
        return "RBRS-AE"

    # ──────────────────────────────────────────────────────────────
    # ANA GİRİŞ
    # ──────────────────────────────────────────────────────────────

    def _solve_impl(self, orders: list[Order], warehouse) -> Solution:
        self._wh = warehouse
        if not orders:
            return Solution(self.name, [], 0.0)

        warehouse.build_problem_matrix(orders)

        # 1) Priority skorları — 1 kez
        priorities = self._priority_scores(orders)

        # 2) Regret-only başlangıç (multi-start ve savings kaldırıldı — performance fix)
        # Önceki versiyon: 3 multi-start × (savings + regret) = aşırı yavaş, kalite kazancı minimal
        # Yeni versiyon: tek regret assignment, ana iyileştirme iterative loop'ta yapılıyor
        batches      = self._regret_assignment(orders, priorities)
        self._compute_routes(batches)
        best_dist    = self._total_dist(batches)
        best_batches = self._clone(batches)
        self.convergence_history = [best_dist]

        if self.verbose:
            print(f"  [RBRS-AE] Başlangıç: {best_dist:.1f} LU, "
                  f"{len(batches)} batch")

        # 3) Iterative improvement
        no_imp = 0
        it = 0
        for it in range(1, self.max_iterations + 1):
            if no_imp >= self.max_no_improvement:
                break

            # Shift
            batches, c1 = self._shift(batches)
            # Swap
            batches, c2 = self._swap(batches)
            # Route güncelle (sadece değişiklik olduysa)
            if c1 or c2:
                self._compute_routes(batches)

            # Adaptive elimination (%20 → %10)
            elim_pct = 0.20 - 0.10 * (it / self.max_iterations)
            batches = self._eliminate(batches, orders, priorities, elim_pct)
            self._compute_routes(batches)

            dist = self._total_dist(batches)
            self.convergence_history.append(dist)

            if dist < best_dist - 1e-9:
                best_dist    = dist
                best_batches = self._clone(batches)
                no_imp = 0
                if self.verbose:
                    print(f"  [RBRS-AE] iter {it:3d}: {best_dist:.1f} LU ✓")
            else:
                no_imp += 1

        if self.verbose:
            print(f"  [RBRS-AE] Bitti: {best_dist:.1f} LU, {it} iter")

        # ── Final Local Improvement ────────────────────────────────
        # Ana döngü bittikten sonra Gbest üzerinde 15 kez saf shift/swap
        # Exploration değil exploitation — sadece iyileşme kabul edilir
        final_batches = self._clone(best_batches)
        for _ in range(15):
            final_batches, c1 = self._final_shift(final_batches)
            final_batches, c2 = self._final_swap(final_batches)
            if not c1 and not c2:
                break

        final_dist = self._total_dist(final_batches)
        if final_dist < best_dist - 1e-9:
            best_dist    = final_dist
            best_batches = final_batches
            if self.verbose:
                print(f"  [RBRS-AE] Final LS: {best_dist:.1f} LU ✓")

        return Solution(
            algorithm_name=self.name,
            batches=best_batches,
            total_travel_distance=best_dist,
            iterations_used=it,
            convergence_history=self.convergence_history,
        )

    # ══════════════════════════════════════════════════════════════
    # 1) PRIORITY SCORE
    # ══════════════════════════════════════════════════════════════

    def _priority_scores(self, orders: list[Order]) -> list[float]:
        """Priority(o) = 0.5*AvgDist + 0.3*Variance + 0.2*Weight (normalize edilmiş)"""
        depot = self._wh.DEPOT
        df    = self._wh.dist_m

        raw_ad, raw_vr, raw_wt = [], [], []

        for o in orders:
            locs = list(set(o.locations))

            # AvgDist: depot'a ortalama uzaklık
            avg_d = sum(df(depot, l) for l in locs) / len(locs) if locs else 0.0

            # Variance: lokasyonlar arası mesafelerin varyansı
            if len(locs) >= 2:
                pairs = [df(locs[i], locs[j])
                         for i in range(len(locs))
                         for j in range(i + 1, len(locs))]
                m   = sum(pairs) / len(pairs)
                var = sum((d - m) ** 2 for d in pairs) / len(pairs)
            else:
                var = 0.0

            raw_ad.append(avg_d)
            raw_vr.append(var)
            raw_wt.append(o.total_weight)

        # Normalize [0, 1]
        mx_ad = max(raw_ad) or 1.0
        mx_vr = max(raw_vr) or 1.0
        mx_wt = max(raw_wt) or 1.0

        return [0.5 * raw_ad[i] / mx_ad +
                0.3 * raw_vr[i] / mx_vr +
                0.2 * raw_wt[i] / mx_wt
                for i in range(len(orders))]

    # ══════════════════════════════════════════════════════════════
    # 2) REGRET-BASED ASSIGNMENT
    # ══════════════════════════════════════════════════════════════

    def _regret_assignment(self, orders: list[Order],
                           priorities: list[float],
                           rng: random.Random = None) -> list[Batch]:
        """
        Her adımda en yüksek regret'e sahip order'ı ata.
        regret = secondBest - bestCost  (priority ile ağırlıklandırılmış)
        rng verilmişse order sırasını karıştır (multi-start diversification).
        """
        if rng is not None:
            idx = list(range(len(orders)))
            rng.shuffle(idx)
            orders     = [orders[i]     for i in idx]
            priorities = [priorities[i] for i in idx]
        assigned = [False] * len(orders)
        batches: list[Batch] = []
        remaining = len(orders)

        while remaining > 0:
            best_score = -1.0
            best_i     = -1
            best_bidx  = -1   # -1 = yeni batch

            for i, o in enumerate(orders):
                if assigned[i]:
                    continue

                costs = self._insertion_costs(o, batches)
                # costs: [(delta, batch_idx), ...] sıralı, -1 = yeni batch

                if len(costs) >= 2:
                    regret = costs[1][0] - costs[0][0]
                    target = costs[0][1]
                elif len(costs) == 1:
                    regret = costs[0][0]
                    target = costs[0][1]
                else:
                    regret = 0.0
                    target = -1

                score = regret * (1.0 + priorities[i])
                if score > best_score:
                    best_score = score
                    best_i     = i
                    best_bidx  = target

            o = orders[best_i]
            if best_bidx == -1:
                b = Batch(batch_id=len(batches), orders=[o],
                          total_weight=o.total_weight)
                batches.append(b)
            else:
                b = batches[best_bidx]
                b.orders.append(o)
                b.total_weight += o.total_weight

            assigned[best_i] = True
            remaining -= 1

        return batches

    def _insertion_costs(self, order: Order,
                         batches: list[Batch]) -> list[tuple[float, int]]:
        """Mevcut batch'lere + yeni batch'e insertion maliyetleri (sıralı)."""
        costs = []
        new_locs = order.locations

        for idx, b in enumerate(batches):
            if b.total_weight + order.total_weight > self.capacity:
                continue
            if b.travel_distance == 0.0 and b.orders:
                _, b.travel_distance = self._route_cost(b.locations)
            _, c = self._route_cost(b.locations + new_locs)
            costs.append((c - b.travel_distance, idx))

        # Yeni batch alternatifi
        _, single = self._route_cost(new_locs)
        costs.append((single, -1))
        costs.sort(key=lambda x: x[0])
        return costs

    # ══════════════════════════════════════════════════════════════
    # 3a) SHIFT
    # ══════════════════════════════════════════════════════════════

    def _shift(self, batches: list[Batch]) -> tuple[list[Batch], bool]:
        """
        Best-improvement shift: her order için tüm feasible hedeflere bak,
        en fazla kazanç sağlayanı seç. Rastgele değil sistematik.
        """
        if len(batches) < 2:
            return batches, False

        changed = False

        # Tüm (batch, order) çiftlerini karıştır, shift_attempts kadar dene
        candidates = [(b_idx, o_idx)
                      for b_idx, b in enumerate(batches)
                      for o_idx in range(len(b.orders))]
        self._rng.shuffle(candidates)
        candidates = candidates[:self.shift_attempts]

        for src_idx, o_idx in candidates:
            src = batches[src_idx]
            if o_idx >= len(src.orders):
                continue
            o = src.orders[o_idx]

            # Kaynak batch'in order çıkarılmış hali
            src_locs_new = [loc
                            for ord_ in src.orders
                            for loc in ord_.locations
                            if ord_ is not o]
            _, sd = self._route_cost(src_locs_new) if src_locs_new else ([], 0.0)

            # Tüm hedef batch'lere bak, en iyi kazancı bul
            best_gain = 1e-9
            best_dst_idx = None
            best_dd = 0.0

            for dst_idx, dst in enumerate(batches):
                if dst_idx == src_idx:
                    continue
                if dst.total_weight + o.total_weight > self.capacity:
                    continue
                _, dd = self._route_cost(dst.locations + o.locations)
                gain = (src.travel_distance + dst.travel_distance) - (sd + dd)
                if gain > best_gain:
                    best_gain    = gain
                    best_dst_idx = dst_idx
                    best_dd      = dd

            if best_dst_idx is not None:
                dst = batches[best_dst_idx]
                src.orders.pop(o_idx)
                src.total_weight    -= o.total_weight
                src.travel_distance  = sd
                dst.orders.append(o)
                dst.total_weight    += o.total_weight
                dst.travel_distance  = best_dd
                changed = True

        batches = [b for b in batches if b.orders]
        self._renumber(batches)
        return batches, changed

    # ══════════════════════════════════════════════════════════════
    # 3b) SWAP
    # ══════════════════════════════════════════════════════════════

    def _swap(self, batches: list[Batch]) -> tuple[list[Batch], bool]:
        """İki farklı batch'ten birer order takas et — iyileşme varsa kabul."""
        if len(batches) < 2:
            return batches, False

        changed = False
        for _ in range(self.swap_attempts):
            b1, b2 = self._rng.sample(batches, 2)
            if not b1.orders or not b2.orders:
                continue

            o1 = self._rng.choice(b1.orders)
            o2 = self._rng.choice(b2.orders)

            w1 = b1.total_weight - o1.total_weight + o2.total_weight
            w2 = b2.total_weight - o2.total_weight + o1.total_weight
            if w1 > self.capacity or w2 > self.capacity:
                continue

            locs1 = [l for ord_ in b1.orders for l in ord_.locations
                     if ord_ is not o1] + o2.locations
            locs2 = [l for ord_ in b2.orders for l in ord_.locations
                     if ord_ is not o2] + o1.locations

            _, d1 = self._route_cost(locs1)
            _, d2 = self._route_cost(locs2)

            if d1 + d2 < b1.travel_distance + b2.travel_distance - 1e-9:
                b1.orders.remove(o1); b1.orders.append(o2)
                b1.total_weight = w1; b1.travel_distance = d1
                b2.orders.remove(o2); b2.orders.append(o1)
                b2.total_weight = w2; b2.travel_distance = d2
                changed = True

        return batches, changed

    # ══════════════════════════════════════════════════════════════
    # 3c) ADAPTIVE ELIMINATION
    # ══════════════════════════════════════════════════════════════

    def _eliminate(self, batches: list[Batch], all_orders: list[Order],
                   priorities: list[float], elim_pct: float) -> list[Batch]:
        """
        En kötü batch'lerin elim_pct'sini yık, order'ları yeniden regret ile ata.
        I(b) = 0.7*(dist/orderCount) + 0.3*(1-utilization)
        """
        if len(batches) <= 2:
            return batches

        scored = sorted(
            batches,
            key=lambda b: (0.7 * b.travel_distance / max(len(b.orders), 1) +
                           0.3 * (1.0 - b.total_weight / self.capacity)),
            reverse=True
        )

        num_elim   = max(1, int(len(scored) * elim_pct))
        elim_ids   = {id(b) for b in scored[:num_elim]}
        freed      = [o for b in batches if id(b) in elim_ids for o in b.orders]
        kept       = [b for b in batches if id(b) not in elim_ids]

        if not freed:
            return batches

        # Freed order'ların priority indekslerini bul
        oid_map   = {id(o): i for i, o in enumerate(all_orders)}
        freed_pri = [priorities[oid_map[id(o)]] if id(o) in oid_map else 0.5
                     for o in freed]

        # Performance fix: tüm pool'u yeniden assign etmek yerine sadece freed'i kept'e ekle.
        # Eski yaklaşım her iter'de N×B insertion cost hesabı yapıyordu (gereksiz iş).
        # Freed order'ları priority'ye göre sıralayıp greedy regret ile yerleştir.
        new_batches = kept[:]
        for o, pri in sorted(zip(freed, freed_pri), key=lambda x: -x[1]):
            costs = self._insertion_costs(o, new_batches)
            if not costs:
                # Hiç feasible yer yok, yeni batch aç
                new_batches.append(Batch(batch_id=len(new_batches),
                                          orders=[o],
                                          total_weight=o.total_weight))
                continue
            _, target = costs[0]  # En düşük cost'lu hedef
            if target == -1:
                new_batches.append(Batch(batch_id=len(new_batches),
                                          orders=[o],
                                          total_weight=o.total_weight))
            else:
                new_batches[target].orders.append(o)
                new_batches[target].total_weight += o.total_weight
                # Route'u invalidate et, _compute_routes daha sonra yeniden hesaplayacak
                new_batches[target].travel_distance = 0.0

        self._renumber(new_batches)
        return new_batches

    # ══════════════════════════════════════════════════════════════
    # YARDIMCILAR
    # ══════════════════════════════════════════════════════════════

    def _savings_start(self, orders: list[Order],
                       rng: random.Random = None) -> list[Batch]:
        """Clarke-Wright savings ile başlangıç batch'leri."""
        from algorithms.batching.savings import savings_batching
        # savings_batching deterministik, rng burada order sıralaması için
        if rng is not None:
            shuffled = orders[:]
            rng.shuffle(shuffled)
            return savings_batching(shuffled, self._wh, capacity=self.capacity)
        return savings_batching(orders, self._wh, capacity=self.capacity)

    def _final_shift(self, batches: list[Batch]) -> tuple[list[Batch], bool]:
        """
        Final local improvement — tüm order/batch kombinasyonlarını tara,
        en iyi tek hareketi uygula (best improvement).
        """
        if len(batches) < 2:
            return batches, False

        best_gain    = 1e-9
        best_move    = None  # (src_idx, o_idx, dst_idx, sd, dd)

        for src_idx, src in enumerate(batches):
            for o_idx, o in enumerate(src.orders):
                src_locs = [l for ord_ in src.orders
                            for l in ord_.locations if ord_ is not o]
                _, sd = self._route_cost(src_locs) if src_locs else ([], 0.0)

                for dst_idx, dst in enumerate(batches):
                    if dst_idx == src_idx:
                        continue
                    if dst.total_weight + o.total_weight > self.capacity:
                        continue
                    _, dd = self._route_cost(dst.locations + o.locations)
                    gain  = (src.travel_distance + dst.travel_distance) - (sd + dd)
                    if gain > best_gain:
                        best_gain = gain
                        best_move = (src_idx, o_idx, dst_idx, sd, dd)

        if best_move is None:
            return batches, False

        src_idx, o_idx, dst_idx, sd, dd = best_move
        o = batches[src_idx].orders.pop(o_idx)
        batches[src_idx].total_weight    -= o.total_weight
        batches[src_idx].travel_distance  = sd
        batches[dst_idx].orders.append(o)
        batches[dst_idx].total_weight    += o.total_weight
        batches[dst_idx].travel_distance  = dd

        batches = [b for b in batches if b.orders]
        self._renumber(batches)
        return batches, True

    def _final_swap(self, batches: list[Batch]) -> tuple[list[Batch], bool]:
        """
        Final local improvement — tüm order çiftlerini tara,
        en iyi swap'ı uygula.
        """
        if len(batches) < 2:
            return batches, False

        best_gain = 1e-9
        best_move = None

        for i in range(len(batches)):
            for j in range(i + 1, len(batches)):
                b1, b2 = batches[i], batches[j]
                for o1 in b1.orders:
                    for o2 in b2.orders:
                        w1 = b1.total_weight - o1.total_weight + o2.total_weight
                        w2 = b2.total_weight - o2.total_weight + o1.total_weight
                        if w1 > self.capacity or w2 > self.capacity:
                            continue

                        locs1 = [l for ord_ in b1.orders
                                 for l in ord_.locations if ord_ is not o1] + o2.locations
                        locs2 = [l for ord_ in b2.orders
                                 for l in ord_.locations if ord_ is not o2] + o1.locations
                        _, d1 = self._route_cost(locs1)
                        _, d2 = self._route_cost(locs2)
                        gain  = (b1.travel_distance + b2.travel_distance) - (d1 + d2)

                        if gain > best_gain:
                            best_gain = gain
                            best_move = (i, j, o1, o2, w1, w2, d1, d2)

        if best_move is None:
            return batches, False

        i, j, o1, o2, w1, w2, d1, d2 = best_move
        batches[i].orders.remove(o1)
        batches[i].orders.append(o2)
        batches[i].total_weight    = w1
        batches[i].travel_distance = d1
        batches[j].orders.remove(o2)
        batches[j].orders.append(o1)
        batches[j].total_weight    = w2
        batches[j].travel_distance = d2

        return batches, True

    def _route_cost(self, locations: list[int]) -> tuple[list[int], float]:
        if not locations:
            return [self._wh.DEPOT, self._wh.DEPOT], 0.0
        route, _ = nearest_neighbor_route(list(set(locations)), self._wh)
        return two_opt_improve(route, self._wh)

    def _compute_routes(self, batches: list[Batch]) -> None:
        for b in batches:
            if not b.orders:
                b.travel_distance = 0.0
                b.route = []
                continue
            route, dist = self._route_cost(b.locations)
            b.route = route
            b.travel_distance = dist

    def _total_dist(self, batches: list[Batch]) -> float:
        return sum(b.travel_distance for b in batches)

    @staticmethod
    def _renumber(batches: list[Batch]) -> None:
        for i, b in enumerate(batches):
            b.batch_id = i

    @staticmethod
    def _clone(batches: list[Batch]) -> list[Batch]:
        return [Batch(batch_id=b.batch_id, orders=b.orders[:],
                      total_weight=b.total_weight,
                      route=b.route[:] if b.route else [],
                      travel_distance=b.travel_distance)
                for b in batches]


# ════════════════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from core.data_loader import DataLoader
    from core.warehouse import Warehouse
    from benchmarks.sop import SOP
    from benchmarks.fcfs import FCFS
    from algorithms.depso import DEPSO

    loader = DataLoader()
    wh     = Warehouse()
    orders = loader.load_orders(1, 1, 20).orders[:50]

    print(f"Test: {len(orders)} sipariş")
    print("=" * 55)

    sop  = SOP().solve(orders, wh)
    fcfs = FCFS().solve(orders, wh)
    print(f"SOP:     {sop.total_travel_distance:7.1f} LU  ({sop.runtime_seconds:.2f}s)")
    print(f"FCFS:    {fcfs.total_travel_distance:7.1f} LU  ({fcfs.runtime_seconds:.2f}s)")

    print("\nRBRS-AE çalıştırılıyor...")
    rbrs = RBRS_AE(seed=42, verbose=True).solve(orders, wh)
    print(f"RBRS-AE: {rbrs.total_travel_distance:7.1f} LU  ({rbrs.runtime_seconds:.2f}s)")

    print("\nDEPSO çalıştırılıyor (500 iter)...")
    depso = DEPSO(num_iterations=500, seed=42).solve(orders, wh)
    print(f"DEPSO:   {depso.total_travel_distance:7.1f} LU  ({depso.runtime_seconds:.2f}s)")

    print("\n" + "=" * 55)
    print("Karşılaştırma (SOP baseline):")
    for sol in [sop, fcfs, rbrs, depso]:
        pct = (sol.total_travel_distance - sop.total_travel_distance) / sop.total_travel_distance * 100
        print(f"  {sol.algorithm_name:<10}: {sol.total_travel_distance:7.1f} LU  {pct:+.1f}%")
