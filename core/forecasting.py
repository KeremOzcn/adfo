"""
core/forecasting.py
====================
Holt-Winters Triple Exponential Smoothing — Paper Section 6.4

Formüller:
  x̂(T+τ) = aT + bT·τ + c(T+τ-L')          tahmin (L' = L'inci tam kat)
  aT = α·(xT - cT-L) + (1-α)·(aT-1 + bT-1) level
  bT = β·(aT - aT-1)  + (1-β)·bT-1          trend
  cT = γ·(xT - aT)    + (1-γ)·cT-L          seasonality

Parametreler (Silver, Pyke & Thomas 2016 önerisi):
  α = 0.19,  β = 0.053,  γ = 0.10,  L = 12

Kullanım:
  hw = HoltWinters()
  hw.fit(history)          # 12 periyot ısınma verisiyle parametre ayarla
  forecast = hw.predict(tau=1)  # bir sonraki periyot tahmini
"""

from __future__ import annotations
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import HOLT_WINTERS, TIME_SERIES


class HoltWinters:
    """
    Holt-Winters triple exponential smoothing.
    Her item için ayrı bir instance kullanılır.
    """

    def __init__(self, alpha: float = None, beta: float = None,
                 gamma: float = None, L: int = None):
        self.alpha = alpha if alpha is not None else HOLT_WINTERS['alpha']
        self.beta  = beta  if beta  is not None else HOLT_WINTERS['beta']
        self.gamma = gamma if gamma is not None else HOLT_WINTERS['gamma']
        self.L     = L     if L     is not None else TIME_SERIES['seasonal_cycle_L']

        # State
        self.a: float = 0.0        # level
        self.b: float = 0.0        # trend
        self.c: list[float] = []   # seasonality (L adet)
        self._fitted = False
        self._history: list[float] = []

    # ──────────────────────────────────────────────────────────────
    # FIT
    # ──────────────────────────────────────────────────────────────

    def fit(self, history: list[float]) -> None:
        """
        Tarihsel veriyle parametreleri ayarla.
        Paper: 12 periyot ısınma verisi kullanılır.
        history: en az L adet gözlem olmalı.
        """
        if len(history) < self.L:
            raise ValueError(
                f"Holt-Winters için en az {self.L} gözlem gerekli, "
                f"{len(history)} verildi."
            )

        self._history = list(history)
        n = len(history)

        # ── Başlangıç değerleri ────────────────────────────────────
        # Level: ilk L periyot ortalaması
        self.a = sum(history[:self.L]) / self.L

        # Trend: ilk iki L-ortalaması farkı / L
        if n >= 2 * self.L:
            second_avg = sum(history[self.L:2 * self.L]) / self.L
            self.b = (second_avg - self.a) / self.L
        else:
            self.b = 0.0

        # Seasonality: additive model — deviation from level (not ratio)
        self.c = [history[i] - self.a for i in range(self.L)]

        # ── Güncelleme döngüsü ─────────────────────────────────────
        for t in range(n):
            x_t = history[t]
            c_prev = self.c[t % self.L]

            a_new = (self.alpha * (x_t - c_prev) +
                     (1 - self.alpha) * (self.a + self.b))
            b_new = (self.beta * (a_new - self.a) +
                     (1 - self.beta) * self.b)
            c_new = (self.gamma * (x_t - a_new) +
                     (1 - self.gamma) * c_prev)

            self.a = a_new
            self.b = b_new
            self.c[t % self.L] = c_new

        self._fitted = True

    # ──────────────────────────────────────────────────────────────
    # PREDICT
    # ──────────────────────────────────────────────────────────────

    def predict(self, tau: int = 1) -> float:
        """
        tau periyot ilerisi için tahmin.
        Paper formülü: x̂(T+τ) = aT + bT·τ + c(T+τ mod L)

        tau=1 → bir sonraki periyot (storage relocation kararı için)
        """
        if not self._fitted:
            raise RuntimeError("Önce fit() çağrılmalı.")

        n = len(self._history)
        season_idx = (n + tau - 1) % self.L
        forecast = self.a + self.b * tau + self.c[season_idx]
        return max(0.0, forecast)  # negatif orderline olmaz

    def predict_next(self) -> float:
        """Bir sonraki periyot tahmini (kısayol)."""
        return self.predict(tau=1)

    # ──────────────────────────────────────────────────────────────
    # UPDATE (yeni gözlem gelince)
    # ──────────────────────────────────────────────────────────────

    def update(self, x_new: float) -> None:
        """
        Yeni gözlem gelince state'i güncelle.
        Dynamic relocation: her periyot sonunda çağrılır.
        """
        if not self._fitted:
            raise RuntimeError("Önce fit() çağrılmalı.")

        n = len(self._history)
        c_prev = self.c[n % self.L]

        a_new = (self.alpha * (x_new - c_prev) +
                 (1 - self.alpha) * (self.a + self.b))
        b_new = self.beta * (a_new - self.a) + (1 - self.beta) * self.b
        c_new = self.gamma * (x_new - a_new) + (1 - self.gamma) * c_prev

        self.a = a_new
        self.b = b_new
        self.c[n % self.L] = c_new
        self._history.append(x_new)


# ════════════════════════════════════════════════════════════════════════════
# TÜM İTEMLER İÇİN TOPLU TAHMİN
# ════════════════════════════════════════════════════════════════════════════

class ItemForecaster:
    """
    6000 item için Holt-Winters modellerini yönetir.

    Kullanım:
        forecaster = ItemForecaster()
        forecaster.fit_all(demand_matrix)       # (6000, 21) matris
        forecasts = forecaster.predict_all()    # (6000,) array
        forecaster.update_all(actual_period)    # yeni periyot geldikten sonra
    """

    def __init__(self):
        self.models: list[HoltWinters] = []
        self._fitted = False

    def fit_all(self, demand_matrix, warmup_periods: int = None) -> None:
        """
        demand_matrix: (num_items, num_periods) — tüm periyotlar
        warmup_periods: kaç periyot ısınma için kullanılacak (default: 12)
        """
        import numpy as np

        if warmup_periods is None:
            warmup_periods = TIME_SERIES['num_warmup_periods']

        num_items = demand_matrix.shape[0]
        self.models = []

        for i in range(num_items):
            hw = HoltWinters()
            history = [float(x) for x in demand_matrix[i, :warmup_periods]]
            try:
                hw.fit(history)
            except Exception:
                # Bazı itemlerin tüm değerleri 0 olabilir
                hw._fitted = True
                hw.a = 0.0
                hw.b = 0.0
                hw.c = [0.0] * hw.L
                hw._history = history
            self.models.append(hw)

        self._fitted = True

    def predict_all(self, tau: int = 1):
        """Tüm itemler için tau adım ilerisi tahmini. Döndürür: list[float]"""
        if not self._fitted:
            raise RuntimeError("Önce fit_all() çağrılmalı.")
        return [m.predict(tau) for m in self.models]

    def update_all(self, actual_period) -> None:
        """
        Yeni periyot gerçekleşti — tüm modelleri güncelle.
        actual_period: (num_items,) dizisi — bu periyodun gerçek talepleri
        """
        for i, m in enumerate(self.models):
            m.update(float(actual_period[i]))

    def abc_classify(self, forecasts: list[float],
                     a_pct: float = 0.05,
                     b_pct: float = 0.15) -> list[str]:
        """
        Tahmin değerlerine göre ABC sınıflandırması.
        Yüksek talep → A sınıfı (depot'a yakın)

        Döndürür: ['A', 'B', 'C', ...] (num_items uzunluğunda)
        """
        n = len(forecasts)
        n_a = int(n * a_pct)
        n_b = int(n * b_pct)

        # Azalan sırada indeks
        sorted_idx = sorted(range(n), key=lambda i: -forecasts[i])

        classes = ['C'] * n
        for rank, idx in enumerate(sorted_idx):
            if rank < n_a:
                classes[idx] = 'A'
            elif rank < n_a + n_b:
                classes[idx] = 'B'

        return classes


# ════════════════════════════════════════════════════════════════════════════
# TEST
# ════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import numpy as np
    from core.data_loader import DataLoader

    loader = DataLoader()

    print("=" * 60)
    print("Holt-Winters Forecasting Test")
    print("=" * 60)

    # ── Tek item testi ────────────────────────────────────────────
    print("\n1) Tek item — sentetik veri")
    # Trend=0.3, Seasonality=0.15 olan bir serinin ilk 12 periyodu
    rng = np.random.default_rng(42)
    history = [100 + 30 * t/12 + 15 * np.cos(2 * np.pi * t / 12) + rng.normal(0, 3)
               for t in range(12)]

    hw = HoltWinters()
    hw.fit(history)
    print(f"  Son 3 gözlem: {[round(h, 1) for h in history[-3:]]}")
    for tau in [1, 2, 3]:
        pred = hw.predict(tau)
        print(f"  τ={tau} tahmini: {pred:.1f}")

    # ── Dataset ile tam test ──────────────────────────────────────
    print("\n2) Dataset — 6000 item, 12 periyot ısınma")
    demand_s1 = loader.load_scenario_demand(1)  # (6000, 21)
    print(f"  Matris boyutu: {demand_s1.shape}")

    forecaster = ItemForecaster()
    forecaster.fit_all(demand_s1, warmup_periods=12)
    print(f"  Model sayısı: {len(forecaster.models)}")

    # Periyot 13 tahmini (ilk test periyodu)
    preds = forecaster.predict_all(tau=1)
    actual_p13 = demand_s1[:, 12].tolist()

    # İlk 5 item için karşılaştır
    print("\n  İlk 5 item — tahmin vs gerçek (Periyot 13):")
    print(f"  {'Item':<6} {'Tahmin':>10} {'Gerçek':>10} {'Hata%':>8}")
    for i in range(5):
        pred = preds[i]
        actual = actual_p13[i]
        err = abs(pred - actual) / max(actual, 1) * 100
        print(f"  {i:<6} {pred:>10.1f} {actual:>10.0f} {err:>7.1f}%")

    # Ortalama mutlak hata
    errs = [abs(preds[i] - actual_p13[i]) / max(actual_p13[i], 1) * 100
            for i in range(6000) if actual_p13[i] > 0]
    print(f"\n  Ortalama mutlak hata (MAPE): {sum(errs)/len(errs):.1f}%")

    # ── ABC sınıflandırması ───────────────────────────────────────
    print("\n3) Tahmin bazlı ABC sınıflandırması")
    classes = forecaster.abc_classify(preds)
    from collections import Counter
    dist = Counter(classes)
    print(f"  A: {dist['A']} ({dist['A']/6000*100:.1f}%)")
    print(f"  B: {dist['B']} ({dist['B']/6000*100:.1f}%)")
    print(f"  C: {dist['C']} ({dist['C']/6000*100:.1f}%)")

    # Update testi
    print("\n4) Update testi (periyot 13 gerçekleşti)")
    forecaster.update_all(demand_s1[:, 12])
    preds_p14 = forecaster.predict_all(tau=1)
    actual_p14 = demand_s1[:, 13].tolist()
    errs2 = [abs(preds_p14[i] - actual_p14[i]) / max(actual_p14[i], 1) * 100
             for i in range(6000) if actual_p14[i] > 0]
    print(f"  Periyot 14 MAPE: {sum(errs2)/len(errs2):.1f}%")

    print("\n✓ Holt-Winters tamamlandı")
