"""
algorithms/depso.py
====================
DEPSO (Discrete Evolutionary Particle Swarm Optimization)
Paper: Kübler, Glock, Bauernhansl (2020), Section 5.2, Appendix E-G.

DEPSO permütasyon tabanlı bir PSO varyantıdır:
- Her particle: K sipariş için bir permütasyon
- Velocity: K-boyutlu vektör, her elemanı {-1, 0, 1}
  -  1: Gbest yönünde hareket
  -  0: hareketsiz
  - -1: Pbest yönünde hareket
- Movement: pozisyon h'de v=+1 ise Gbest'teki order P_h ile mevcut order yer değiştirir
- Mutation: stagnasyona karşı swap/shift/inverse operatörü
- Local search: Gbest etrafında swap aramaları

Adımlar (Section 5.2.6):
  1-5: Initialization (random + savings particle)
  6-10: Movement + evaluation
  11: Stagnation check
  12: Mutation
  13: Local search
  14: Iteration loop
  15: Output
"""

from __future__ import annotations

import random
import sys
import time
from copy import copy
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
from core.data_loader import Order
from algorithms.base import BatchingRoutingAlgorithm, Batch, Solution
from algorithms.batching.first_fit import first_fit_batching
from algorithms.routing.two_opt import nn_then_2opt
from config import DEPSO as DEPSO_CONFIG, ITEMS


# ════════════════════════════════════════════════════════════════════════════
# PARTICLE
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class Particle:
    """
    Bir DEPSO parçacığı.

    permutation: K sipariş için sıralama (indeksler 0..K-1)
    velocity:    K-boyutlu vektör, her eleman {-1, 0, 1}
    """
    permutation: list[int]
    velocity: list[int]
    travel_distance: float = float('inf')
    best_permutation: list[int] = field(default_factory=list)
    best_travel_distance: float = float('inf')
    best_batches: list[Batch] = field(default_factory=list)

    def __post_init__(self):
        if not self.best_permutation:
            self.best_permutation = self.permutation[:]


# ════════════════════════════════════════════════════════════════════════════
# DEPSO SINIFI
# ════════════════════════════════════════════════════════════════════════════

class DEPSO(BatchingRoutingAlgorithm):
    """
    Paper Section 5.2'deki DEPSO implementasyonu.

    Parametreler config.DEPSO'dan, ama override edilebilir.
    """

    def __init__(
        self,
        num_particles: int = None,
        num_iterations: int = None,
        sgbest_threshold: float = None,
        max_local_search_iterations: int = None,
        max_stagnation_bound: int = None,
        seed: int | None = None,
        verbose: bool = False,
    ):
        self.num_particles = num_particles or DEPSO_CONFIG['num_particles']
        self.num_iterations = num_iterations or DEPSO_CONFIG['num_iterations']
        self.sgbest = sgbest_threshold if sgbest_threshold is not None else DEPSO_CONFIG['sgbest_threshold']
        self.max_ls_iters = max_local_search_iterations or DEPSO_CONFIG['max_local_search_iterations']
        self.max_stag = max_stagnation_bound or DEPSO_CONFIG['max_stagnation_bound']
        self.swap_thresh = DEPSO_CONFIG['swap_threshold']
        self.shift_thresh = DEPSO_CONFIG['shift_threshold']
        self.verbose = verbose

        # RNG
        self.seed = seed
        self._rng = random.Random(seed) if seed is not None else random.Random()

        # Runtime state
        self._orders: list[Order] = []
        self._warehouse = None
        self._K: int = 0  # sipariş sayısı

        # Swarm state
        self.particles: list[Particle] = []
        self.gbest_permutation: list[int] = []
        self.gbest_distance: float = float('inf')
        self.gbest_batches: list[Batch] = []
        self.s_stag_gbest: int = 0

        # Convergence izleme
        self.convergence_history: list[float] = []

    @property
    def name(self) -> str:
        return "DEPSO"

    # ──────────────────────────────────────────────────────────────
    # ANA GİRİŞ NOKTASI
    # ──────────────────────────────────────────────────────────────

    def _solve_impl(self, orders: list[Order], warehouse) -> Solution:
        self._orders = orders
        self._warehouse = warehouse
        self._K = len(orders)

        # Her çağrıda sıfırla — aynı instance tekrar kullanılabilsin
        self.convergence_history = []

        if self._K == 0:
            return Solution(
                algorithm_name=self.name,
                batches=[],
                total_travel_distance=0.0,
                iterations_used=0,
            )

        # Numpy mesafe matrisi — tüm lokasyonlar için 1 kez hesapla
        # Bu, 51M dict lookup yerine O(1) array erişimi sağlar
        if self.verbose:
            print(f"  [DEPSO] Mesafe matrisi ön-hesaplama...")
        warehouse.build_problem_matrix(orders)

        # Adım 1-5: Initialization
        self._initialize()

        # Adım 6-14: Optimization
        for it in range(1, self.num_iterations + 1):
            self._current_iteration = it

            # Adım 6-10: Move each particle
            for p_idx in range(self.num_particles):
                self._move_particle(p_idx)
                self._evaluate_particle(p_idx)

            # Adım 11: Gbest stagnation
            self._update_stagnation()

            # Adım 12: Mutation
            self._mutate()

            # Adım 13: Local search
            self._local_search()

            # Track convergence
            self.convergence_history.append(self.gbest_distance)

            if self.verbose and it % 50 == 0:
                print(f"  [DEPSO] iter {it:4d}/{self.num_iterations}: "
                      f"Gbest={self.gbest_distance:.1f}, stag={self.s_stag_gbest}")

        # Adım 15: Output
        return Solution(
            algorithm_name=self.name,
            batches=self.gbest_batches,
            total_travel_distance=self.gbest_distance,
            iterations_used=self.num_iterations,
            convergence_history=self.convergence_history,
            extra_info={'num_particles': self.num_particles},
        )

    # ──────────────────────────────────────────────────────────────
    # ADIM 1-5: INITIALIZATION
    # ──────────────────────────────────────────────────────────────

    def _initialize(self) -> None:
        """
        Adım 1: A_particle - 1 tane random particle üret + velocity vector
        Adım 2: 1 tane savings particle üret
        Adım 3-4: Her particle için batching + routing → travel distance
        Adım 5: Pbest = current, Gbest = en iyi
        """
        self.particles = []

        # Adım 1: random particles
        for i in range(self.num_particles - 1):
            perm = list(range(self._K))
            self._rng.shuffle(perm)
            vel = [self._rng.choice([-1, 0, 1]) for _ in range(self._K)]
            self.particles.append(Particle(permutation=perm, velocity=vel))

        # Adım 2: savings particle
        savings_perm = self._build_savings_particle()
        savings_vel = [self._rng.choice([-1, 0, 1]) for _ in range(self._K)]
        self.particles.append(Particle(permutation=savings_perm, velocity=savings_vel))

        # Adım 3-4: her particle için fitness
        for p_idx in range(self.num_particles):
            self._evaluate_particle(p_idx, init=True)

        # Adım 5: Gbest = en iyi particle
        best_idx = min(range(self.num_particles),
                       key=lambda i: self.particles[i].travel_distance)
        bp = self.particles[best_idx]
        self.gbest_permutation = bp.permutation[:]
        self.gbest_distance = bp.travel_distance
        self.gbest_batches = bp.best_batches[:]
        self.s_stag_gbest = 0

        if self.verbose:
            print(f"  [DEPSO] Init: {self.num_particles} particle, "
                  f"Gbest start = {self.gbest_distance:.1f}")

    def _build_savings_particle(self) -> list[int]:
        """
        Savings algoritması ile bir permütasyon üret.

        Mantık: Clarke-Wright savings çalıştır, batch'leri tek bir liste
        olarak düzleştir (batch içindekileri yan yana). Bu, "yakın siparişler
        birbirine yakın olur" hipotezini DEPSO'ya başlangıç olarak verir.
        """
        from algorithms.batching.savings import savings_batching

        batches = savings_batching(self._orders, self._warehouse,
                                    capacity=ITEMS['picker_capacity_WU'])
        perm = []
        for b in batches:
            for o in b.orders:
                # Order ID'leri global olabilir; biz orders listesindeki indeksleri istiyoruz
                idx = self._orders.index(o)
                perm.append(idx)

        # Atanmamış varsa ekle (olmamalı ama güvenlik)
        already = set(perm)
        for i in range(self._K):
            if i not in already:
                perm.append(i)

        return perm

    # ──────────────────────────────────────────────────────────────
    # FITNESS DEĞERLENDİRME (Adım 4, 8-10)
    # ──────────────────────────────────────────────────────────────

    def _evaluate_particle(self, p_idx: int, init: bool = False) -> None:
        """
        Bir particle'ın travel distance'ını hesapla:
        - permütasyon → first-fit batching → her batch için NN+2-opt
        - Pbest ve Gbest güncelle
        """
        p = self.particles[p_idx]

        # Permütasyon sırasına göre siparişleri çek
        ordered = [self._orders[i] for i in p.permutation]

        # Batching
        batches = first_fit_batching(ordered)

        # Her batch için routing
        total = 0.0
        for b in batches:
            route, dist = nn_then_2opt(b.locations, self._warehouse)
            b.route = route
            b.travel_distance = dist
            total += dist

        p.travel_distance = total

        # Pbest güncelle (Adım 5/10)
        if total < p.best_travel_distance:
            p.best_travel_distance = total
            p.best_permutation = p.permutation[:]
            p.best_batches = batches  # son geçen iyi çözümü sakla

        # Gbest güncelle (Adım 10) — sadece init değilse
        if not init and total < self.gbest_distance:
            self.gbest_distance = total
            self.gbest_permutation = p.permutation[:]
            self.gbest_batches = batches

    # ──────────────────────────────────────────────────────────────
    # ADIM 7: MOVEMENT (Appendix E)
    # ──────────────────────────────────────────────────────────────

    def _move_particle(self, p_idx: int) -> None:
        """
        Paper Appendix E. Particle'ın permütasyonunu Pbest ve Gbest'e doğru kaydır.

        Her pozisyon h için:
        - v[h] = +1 ise: Gbest yönünde, B_{p,Gbest} olasılığıyla swap
        - v[h] = -1 ise: Pbest yönünde, B_{p,Pbest} olasılığıyla swap
        - v[h] = 0  ise: hareket yok
        - Velocity rastgele yenilenir
        """
        p = self.particles[p_idx]

        # Movement probabilities (Df = normalized difference)
        b_p_gbest = self._diff(p.permutation, self.gbest_permutation)
        b_p_pbest = self._diff(p.permutation, p.best_permutation)

        # Her pozisyon h için (Appendix E adımları)
        for h in range(self._K):
            v = p.velocity[h]

            # Comparative permutation seç
            comp = None
            if v == 1 and b_p_gbest > self.sgbest * self._rng.random():
                comp = self.gbest_permutation
            elif v == -1 and b_p_pbest > self._rng.random():
                comp = p.best_permutation

            # Step 3-4: comparative permütasyonda P[h]'yi bul, swap
            if comp is not None:
                target_order = comp[h]
                # particle'ın permütasyonunda bu order nerede?
                try:
                    r = p.permutation.index(target_order)
                except ValueError:
                    continue

                if r == h:
                    pass  # aynı zaten
                else:
                    # Velocity koşullarını kontrol et (Adım 4)
                    vr = p.velocity[r]
                    if vr != 0 or self._rng.random() < 0.5:
                        # Swap
                        p.permutation[h], p.permutation[r] = (
                            p.permutation[r], p.permutation[h])

            # Step 5: Update velocity[h]
            p.velocity[h] = self._rng.choice([-1, 0, 1])

    @staticmethod
    def _diff(perm1: list[int], perm2: list[int]) -> float:
        """
        Df = (1/K) * Σ 𝟙[P1(j) ≠ P2(j)]  (indicator function)
        İki permütasyonun normalize edilmiş farkı [0, 1].
        """
        K = len(perm1)
        if K == 0:
            return 0.0
        diff_count = sum(1 for j in range(K) if perm1[j] != perm2[j])
        return diff_count / K

    # ──────────────────────────────────────────────────────────────
    # ADIM 11: STAGNATION TRACKING
    # ──────────────────────────────────────────────────────────────

    def _update_stagnation(self) -> None:
        """
        Gbest geçen iterasyonda güncellendiyse stagnation = 0,
        aksi halde +1.
        """
        if not self.convergence_history:
            return

        # Bu iterasyonda Gbest güncellendi mi?
        last = self.convergence_history[-1] if self.convergence_history else float('inf')
        if self.gbest_distance < last:
            self.s_stag_gbest = 0
        else:
            self.s_stag_gbest += 1

    # ──────────────────────────────────────────────────────────────
    # ADIM 12: MUTATION (Appendix F)
    # ──────────────────────────────────────────────────────────────

    def _mutate(self) -> None:
        """
        Paper Appendix F.

        1) Her particle için intensity hesapla
        2) Mutation probability M_p = (Int_max - Int_p) / (Int_max - Int_min)
        3) Eğer M_p > rand: closeness Cl_p hesapla
        4) Cl'ye göre operator seç:
           - Cl < 0.5: swap (küçük değişiklik)
           - 0.5 ≤ Cl < 0.8: shift
           - Cl ≥ 0.8: inverse (büyük değişiklik)
        """
        # Intensity hesapla (her particle için)
        intensities = []
        for p in self.particles:
            df_p_pbest = self._diff(p.permutation, p.best_permutation)
            df_p_gbest = self._diff(p.permutation, self.gbest_permutation)
            df_pbest_gbest = self._diff(p.best_permutation, self.gbest_permutation)
            intensity = (df_p_pbest + df_p_gbest + df_pbest_gbest) / 3.0
            # Paper'da: yüksek intensity = parçacıklar yakın → küçük mutation
            # Aslında paper Int = ortalama diff → yüksek = uzak → kafalar karıştırıcı
            # Tian et al.'a göre "Intensity yüksek = yakın"; biz 1-diff alıyoruz
            intensity = 1.0 - intensity  # close = high intensity
            intensities.append(intensity)

        int_max = max(intensities)
        int_min = min(intensities)
        int_range = int_max - int_min if int_max > int_min else 1.0

        # Travel distance bilgileri (Cl için)
        td_max = max(p.travel_distance for p in self.particles)
        td_gbest = self.gbest_distance
        td_range = td_max - td_gbest if td_max > td_gbest else 1.0

        for p_idx, p in enumerate(self.particles):
            # Mutation probability
            if int_max == int_min:
                m_p = 1.0
            else:
                m_p = (int_max - intensities[p_idx]) / int_range

            if m_p <= self._rng.random():
                continue  # mutasyon yok

            # Closeness
            cl_p = (p.travel_distance - td_gbest) / td_range
            cl_p = max(0.0, min(1.0, cl_p))

            # Operator seç
            if cl_p < self.swap_thresh:
                self._op_swap(p)
            elif cl_p < self.shift_thresh:
                self._op_shift(p)
            else:
                self._op_inverse(p)

            # Adım 6: velocity'de 2 random pozisyonu değiştir
            i, j = self._rng.sample(range(self._K), 2) if self._K >= 2 else (0, 0)
            p.velocity[i] = -p.velocity[i] if p.velocity[i] != 0 else self._rng.choice([-1, 1])
            p.velocity[j] = -p.velocity[j] if p.velocity[j] != 0 else self._rng.choice([-1, 1])

    def _op_swap(self, p: Particle) -> None:
        """İki rastgele pozisyonun siparişlerini yer değiştir."""
        if self._K < 2:
            return
        i, j = self._rng.sample(range(self._K), 2)
        p.permutation[i], p.permutation[j] = p.permutation[j], p.permutation[i]

    def _op_shift(self, p: Particle) -> None:
        """Bir siparişi başka bir pozisyona kaydır."""
        if self._K < 2:
            return
        src = self._rng.randrange(self._K)
        dst = self._rng.randrange(self._K)
        if src == dst:
            return
        order = p.permutation.pop(src)
        p.permutation.insert(dst, order)

    def _op_inverse(self, p: Particle) -> None:
        """İki pozisyon seç, arasındaki segmenti ters çevir."""
        if self._K < 2:
            return
        i, j = sorted(self._rng.sample(range(self._K), 2))
        p.permutation[i:j + 1] = p.permutation[i:j + 1][::-1]

    # ──────────────────────────────────────────────────────────────
    # ADIM 13: LOCAL SEARCH (Appendix G)
    # ──────────────────────────────────────────────────────────────

    def _local_search(self) -> None:
        """
        Stagnation threshold'a ulaşıldıysa Gbest etrafında swap araması yap.
        Paper Appendix G: sadece swap operatörü + first-fit + NN routing.
        (2-opt değil — paper açıkça yazmıyor, swap zaten permutation seviyesinde)
        """
        threshold = round(
            self.max_stag * (1 - self._current_iteration / self.num_iterations)
        ) + 1

        if not (self.s_stag_gbest > threshold * self._rng.random()):
            return

        it_ls = 0
        improved = False
        current_perm = self.gbest_permutation[:]
        current_distance = self.gbest_distance

        while it_ls < self.max_ls_iters and not improved:
            trial = current_perm[:]
            if self._K >= 2:
                i, j = self._rng.sample(range(self._K), 2)
                trial[i], trial[j] = trial[j], trial[i]

            ordered = [self._orders[k] for k in trial]
            batches = first_fit_batching(ordered)
            total = 0.0
            for b in batches:
                # NN yeterli — local search hızı için 2-opt atlıyoruz
                from algorithms.routing.nearest_neighbor import nearest_neighbor_route
                route, dist = nearest_neighbor_route(b.locations, self._warehouse)
                b.route = route
                b.travel_distance = dist
                total += dist

            if total < current_distance:
                self.gbest_distance = total
                self.gbest_permutation = trial[:]
                self.gbest_batches = batches
                self.s_stag_gbest = 0
                rand_p_idx = self._rng.randrange(self.num_particles)
                self.particles[rand_p_idx].permutation = trial[:]
                improved = True

            it_ls += 1


# ════════════════════════════════════════════════════════════════════════════
# HIZLI TEST
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from core.data_loader import DataLoader
    from core.warehouse import Warehouse
    from benchmarks.sop import SOP
    from benchmarks.fcfs import FCFS

    loader = DataLoader()
    wh = Warehouse()

    # Küçük test - paper'ın "50_2_6" instance benzeri
    sub = loader.load_orders(1, 1, 20)
    test_orders = sub.orders[:50]
    print(f"Test instance: 50 sipariş (paper '50_2_6' benzeri)")
    print("=" * 60)

    # Karşılaştırma
    sop_sol = SOP().solve(test_orders, wh)
    fcfs_sol = FCFS().solve(test_orders, wh)

    print(f"SOP+S-Shape: {sop_sol.total_travel_distance:.1f} LU")
    print(f"FCFS+S-Shape: {fcfs_sol.total_travel_distance:.1f} LU")

    # DEPSO - kısa koşu (zamandan tasarruf için)
    print("\nDEPSO çalıştırılıyor (kısa koşu - 100 iter)...")
    depso = DEPSO(num_iterations=100, seed=42, verbose=True)
    depso_sol = depso.solve(test_orders, wh)

    print(f"\nDEPSO: {depso_sol.total_travel_distance:.1f} LU")
    print(f"Süre: {depso_sol.runtime_seconds:.1f}s")

    # Karşılaştırma
    print()
    print("Sonuç karşılaştırması:")
    sop_pct = (depso_sol.total_travel_distance - sop_sol.total_travel_distance) / sop_sol.total_travel_distance * 100
    fcfs_pct = (depso_sol.total_travel_distance - fcfs_sol.total_travel_distance) / fcfs_sol.total_travel_distance * 100
    print(f"  DEPSO vs SOP:  {sop_pct:+.2f}%  (paper: ~-88%)")
    print(f"  DEPSO vs FCFS: {fcfs_pct:+.2f}%  (paper: ~-39%)")
