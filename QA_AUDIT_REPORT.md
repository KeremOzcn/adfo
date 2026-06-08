# Warehouse Optimization Project — QA Audit Report

> **Scope:** Read-only audit. No files were modified.
> **Source:** Kübler, Glock, Bauernhansl (2020), Comp. & Ind. Eng. 147, 106645
> **Date:** 2026-06-08

---

## 1. Architecture & Data Flow Summary

```
config.py  ──→  DATA_DIR / WAREHOUSE / ITEMS / TIME_SERIES / DEPSO / RBRS_AE / …
                ↓
core/data_loader.py   — reads JSON → Item / Order / OrderLine / SubPeriodOrders
core/warehouse.py     — geometry, distance(), dist_m(), build_problem_matrix()
core/forecasting.py   — HoltWinters per item, ItemForecaster (6000 models)
                ↓
algorithms/base.py            — Batch, Solution, BatchingRoutingAlgorithm (ABC)
algorithms/batching/          — first_fit.py, savings.py
algorithms/routing/           — s_shape.py, nearest_neighbor.py, two_opt.py
algorithms/depso.py           — DEPSO (PSO permutation-based)
algorithms/rbrs_ae.py         — RBRS-AE (regret + adaptive elimination)
algorithms/relocation.py      — DynamicRelocation (per-period ABC reassignment)
                ↓
benchmarks/  — SOP, FCFS, comparison, multi_instance
run_*.py     — entry points for 35-scenario paper reproduction
results/     — JSON output files
tests/       — pytest test files (distance, routing, batching smoke tests)
```

---

## 2. Data / Schema Summary

| Entity | Representation | Source |
|---|---|---|
| `Item` | dataclass: `item_id`, `weight_WU`, `class_period1`, `orderlines_period1`, `initial_location` | `items_metadata.json` |
| `OrderLine` | dataclass: `item`, `quantity`, `location`, `weight` | per-order JSON |
| `Order` | dataclass: `order_id`, `num_orderlines`, `total_weight`, `orderlines` | per-subperiod JSON |
| `SubPeriodOrders` | dataclass: `scenario(1/2)`, `period(1..9)`, `subperiod(1..20)`, `orders` | JSON filename |
| demand matrix | `np.ndarray(int32)` shape `(6000, 21)` — items × total_periods | `items_scenario{1,2}.json` |
| location classes | `dict[str, list[int]]` — `{'A': [...], 'B': [...], 'C': [...]}` | `location_class_{A,B,C}.json` |
| `Batch` | dataclass: `batch_id`, `orders`, `total_weight`, `route`, `travel_distance` | runtime |
| `Solution` | dataclass: `algorithm_name`, `batches`, `total_travel_distance`, `runtime_seconds` | runtime |
| `ItemState` | dataclass: `item_id`, `location`, `current_class`, `forecast_class`, `periods_in_wrong_class` | relocation state |
| Distance matrix | `np.ndarray(float32)` — subset only, keyed by `_matrix_idx` dict | `build_problem_matrix()` |

**Schema consistency:** JSON files and Python dataclasses match on all key fields. `demand_matrix` shape `(6000, 21)` aligns with `num_items=6000` and `total_periods=21`. `total_locations = 10 × 2 × 90 × 4 = 7200` is arithmetically correct. Class percentages (5% + 15% + 80%) sum to 1.0. ✓

---

## 3. Findings

---

### Finding 1 — Holt-Winters Seasonality: Multiplicative Init, Additive Update

| | |
|---|---|
| **Location** | `core/forecasting.py` · `HoltWinters.fit()` · line 81 |
| **Severity** | 🔴 High |

**Problem:**

Seasonality is **initialized** with a multiplicative (ratio-based) formula but **updated** with an additive formula:

```python
# Initialization — multiplicative:
self.c = [history[i] / max(self.a, 1e-9) - 1.0 for i in range(self.L)]

# Update loop — additive:
c_new = (self.gamma * (x_t - a_new) + (1 - self.gamma) * c_prev)
```

The predict formula `x̂ = a + b·τ + c` confirms this is a purely additive model. The correct additive initialization is:

```python
self.c = [history[i] - self.a for i in range(self.L)]
```

**Why it matters:**

With `a = 100` and `history[0] = 50`, the multiplicative init gives `c[0] = -0.5` while the correct additive init gives `c[0] = -50`. After 12 warm-up periods with `gamma = 0.10`, only ~72% of weight has shifted to observations; the bad initial values persist substantially. Forecast accuracy drives the ABC classification for relocation decisions, so systematic forecast error propagates directly into incorrect relocation choices, undermining the paper's Section 5.3 results.

**Safe fix:**

```python
# Before:
self.c = [history[i] / max(self.a, 1e-9) - 1.0 for i in range(self.L)]

# After:
self.c = [history[i] - self.a for i in range(self.L)]
```

No other code changes needed.

---

### Finding 2 — Relocation Priority: `periods_in_target_class >= 0` Is Always True

| | |
|---|---|
| **Location** | `algorithms/relocation.py` · `_build_priority_list()` · line 276 |
| **Severity** | 🟠 Medium |

**Problem:**

```python
if (state.periods_in_wrong_class >= self.o and
        state.periods_in_target_class >= 0):   # ← always True; int ≥ 0 always
```

`periods_in_target_class` is initialized to `0` and can never be negative. `DYNAMIC_STORAGE['min_periods_in_target_class_u'] = 1` is stored as `self.u = 1` but is **never referenced** in this condition. The intended guard was almost certainly `>= self.u`.

**Why it matters:**

Items whose forecast class is unstable (flipping between classes) may be prematurely relocated after just 2 periods in the wrong class, instead of waiting for forecast class stability for at least `u` periods. This increases unnecessary relocation effort and can cause oscillatory relocations across periods.

**Safe fix:**

```python
# Before:
state.periods_in_target_class >= 0

# After:
state.periods_in_target_class >= self.u
```

---

### Finding 3 — DEPSO Stagnation: Gbest Compared Before Local Search Runs

| | |
|---|---|
| **Location** | `algorithms/depso.py` · `_solve_impl()` loop · lines 162–171, `_update_stagnation()` · lines 365–378 |
| **Severity** | 🟠 Medium |

**Problem:**

```python
self._update_stagnation()   # reads convergence_history[-1] (prev iteration post-LS)
                            # compares against self.gbest_distance (post-move, pre-LS)
self._mutate()
self._local_search()        # may improve gbest AND reset s_stag_gbest internally
self.convergence_history.append(self.gbest_distance)  # captures post-LS gbest
```

`_update_stagnation` increments the stagnation counter based on gbest **before** the current iteration's local search. The stagnation counter may trigger a local search that then resets the counter itself (`self.s_stag_gbest = 0`). In the next iteration, `convergence_history[-1]` is the post-local-search value (potentially better), so the stagnation check compares a pre-LS current gbest against an already-improved baseline. This causes the counter to fluctuate in a way that does not strictly reflect "iterations without improvement."

**Why it matters:**

Incorrect stagnation counting causes local search (Paper Appendix G) to trigger more or less often than intended, affecting solution quality in a non-deterministic way.

**Safe fix (non-breaking):**

Append to `convergence_history` immediately after particle moves (before mutation/LS), then call `_update_stagnation`:

```python
for p_idx in range(self.num_particles):
    self._move_particle(p_idx)
    self._evaluate_particle(p_idx)

# Record current gbest BEFORE local search
self.convergence_history.append(self.gbest_distance)
self._update_stagnation()
self._mutate()
self._local_search()
```

---

### Finding 4 — DEPSO Savings Particle: O(K²) `list.index()` Lookup

| | |
|---|---|
| **Location** | `algorithms/depso.py` · `_build_savings_particle()` · line 245 |
| **Severity** | 🟠 Medium (performance) |

**Problem:**

```python
for b in batches:
    for o in b.orders:
        idx = self._orders.index(o)   # O(K) linear scan per order
        perm.append(idx)
```

`list.index(o)` performs a linear equality comparison over all K orders for each of the K orders being placed. Total cost is **O(K²)**. For `Order` dataclass equality (comparing all fields including nested `orderlines`), each comparison is not O(1).

**Safe fix:**

```python
order_to_idx = {id(o): i for i, o in enumerate(self._orders)}
# then replace:
idx = order_to_idx[id(o)]
```

---

### Finding 5 — first_fit_batching: Paper Two-Phase Algorithm Not Implemented

| | |
|---|---|
| **Location** | `algorithms/batching/first_fit.py` · lines 43–67 |
| **Severity** | 🟠 Medium (paper deviation) |

**Problem:**

The paper (Section 5.2.2) describes a two-phase first-fit:
1. Process orders in permutation sequence; open a **new** batch when an order doesn't fit in the current batch.
2. Backfill remaining orders into the **smallest-numbered** batch that fits.

The code uses a single-pass: for every order, it tries **all existing batches** in creation order and places it in the first that fits, only opening a new batch when no existing batch has room. This conflates both phases into one and produces different batch compositions than the paper describes.

**Why it matters:**

DEPSO fitness evaluations depend on this function. If the batching behavior diverges from the paper, comparisons with paper results (Table 1 benchmarks) may not be exactly reproducible.

**Severity note:** The current implementation is a valid first-fit bin-packing heuristic and is internally self-consistent. Only change if exact paper reproduction is required.

---

### Finding 6 — RBRS-AE: `travel_distance == 0.0` Used as "Not Computed" Sentinel

| | |
|---|---|
| **Location** | `algorithms/rbrs_ae.py` · `_insertion_costs()` · lines 250–251 |
| **Severity** | 🟠 Medium |

**Problem:**

```python
if b.travel_distance == 0.0 and b.orders:
    _, b.travel_distance = self._route_cost(b.locations)
```

`0.0` is used to mean "route not yet computed." However, a batch containing a single location very close to the depot can legitimately have a near-zero travel distance. Using `0.0` as a sentinel conflates "not computed" with "zero cost" and causes unnecessary route recomputation for such batches on every call.

The same sentinel is set deliberately in `relocation.py:420`:
```python
new_batches[target].travel_distance = 0.0
```

This is intentional but fragile — any future code that initializes `travel_distance = 0.0` for a valid reason will inadvertently trigger recomputation.

**Safe fix:**

Use `None` as the uninitialized sentinel in `Batch`. Alternatively, add a `route_valid: bool = False` flag to `Batch`.

---

### Finding 7 — Relocation: Rejected Items Re-Queued Asymmetrically, Can Exhaust Budget

| | |
|---|---|
| **Location** | `algorithms/relocation.py` · `run_period()` · lines 206–211 |
| **Severity** | 🟠 Medium |

**Problem:**

When `tdr <= 0` (relocation doesn't immediately reduce travel distance):
1. The item is undone (correct).
2. The item is re-appended to the **end** of `priority_list`.
3. `tested` is incremented.

When `future_gain + tdr <= effort` (future gain insufficient):
1. The item is rejected and **not** re-queued.

This asymmetry means "currently harmful" items keep cycling through the list until `tested >= max_suggestions` (50) exhausts the budget, potentially blocking better candidates later in the queue.

**Safe fix:**

Track tested items in a set and skip them on re-encounter, or limit each item to at most one retry per period.

---

### Finding 8 — RBRS-AE Route Cache: Double Deduplication via frozenset + NN

| | |
|---|---|
| **Location** | `algorithms/rbrs_ae.py` · `_route_cost()` · line 535 |
| **Severity** | 🟡 Low |

**Problem:**

```python
key = frozenset(locations)
route, _ = nearest_neighbor_route(list(key), self._wh)
```

`frozenset` eliminates duplicate location IDs. `nearest_neighbor_route` internally does `unique_locs = list(set(locations))` as well. The double deduplication is harmless but wasteful. `list(key)` also has implementation-dependent iteration order (irrelevant since NN uses a `set` internally).

---

### Finding 9 — Import Inside While Loop in DEPSO Local Search

| | |
|---|---|
| **Location** | `algorithms/depso.py` · `_local_search()` · line 503 |
| **Severity** | 🟡 Low |

**Problem:**

```python
while it_ls < self.max_ls_iters and not improved:
    ...
    from algorithms.routing.nearest_neighbor import nearest_neighbor_route
```

Import is inside a tight loop (`max_ls_iters = 100`). Python caches after first import but still performs a dict lookup and name binding per iteration.

**Safe fix:** Move import to module top or to the start of `_local_search()`.

---

### Finding 10 — `sys.path.insert(0, ...)` Scattered Across All Modules

| | |
|---|---|
| **Location** | Every file in `core/`, `algorithms/`, and all sub-packages |
| **Severity** | 🟡 Low |

**Problem:**

```python
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
```

Repeated in 10+ files. Works for standalone script execution but is an anti-pattern for packages. Can cause import shadowing issues and makes proper distribution impossible without cleanup.

**Safe fix:** Add `pyproject.toml` and install with `pip install -e .`. All modules then use absolute package paths without `sys.path` manipulation.

---

### Finding 11 — savings_batching Is Inherently O(N²·NN+2opt)

| | |
|---|---|
| **Location** | `algorithms/batching/savings.py` · lines 62–73 |
| **Severity** | 🟡 Low |

**Problem:**

```python
for i in range(n):
    for j in range(i + 1, n):
        ...
        _, combined_td = nn_then_2opt(combined_locs, warehouse)
```

For `n = 500` orders: 124,750 NN+2opt calls. Even at 1ms each, this is ~2 minutes for a single savings computation. The code already removed multi-start savings for performance, but the underlying O(n²) structure remains.

**Note:** Current instance sizes (50–200 orders) are manageable. Flagged for awareness when scaling.

---

## 4. Tests Coverage Assessment

### What Is Covered

- Distance calculations: same-aisle Manhattan, cross-aisle routing, depot distances, aisle-to-aisle paths — well tested with exact numeric assertions.
- Warehouse geometry: `cross_aisle_x` positions, depot coordinates, `total_locations`.
- NN routing: basic route construction, depot inclusion, uniqueness.
- Smoke tests for batching and a DEPSO basic run.

### What Is NOT Covered

| Gap | Risk |
|---|---|
| Holt-Winters seasonality `c` values after `fit()` | Finding 1 would be caught by a unit test here |
| `_build_priority_list()` with `u` threshold | Finding 2 would be caught |
| `DynamicRelocation.run_period()` full loop (apply/undo, effort, future gain) | Core relocation logic entirely untested |
| `first_fit_batching` with oversized single orders | Edge case commented as "shouldn't happen" but unguarded |
| `savings_batching` empty / single-order inputs | Minor edge cases |
| `DEPSO` with K=1 (single order) | K=0 handled; K=1 is not explicitly validated |
| Multi-period relocation integration (period 1 → period 9) | No end-to-end scenario test |
| `demand_matrix` shape/type validation on load | Bad data would produce confusing downstream errors |

**Estimated meaningful path coverage: ~35–40%.**

---

## 5. Performance Notes

| Location | Issue | Impact |
|---|---|---|
| `build_problem_matrix()` | Pure-Python O(N²) loop over unique locations | Called once per solve; ~250k calls for 500 unique locs. Acceptable. |
| `locations_sorted_by_depot_distance()` | 7200 `distance()` calls; uses dict cache | One-time at generator time. Not on hot path. |
| `savings_batching` | O(n²·NN+2opt) | Slow for n > 200. See Finding 11. |
| `DEPSO._build_savings_particle` | O(K²) via `list.index` | See Finding 4. |
| `RBRS-AE _final_swap` | O(B² · O²) — all order pairs across all batch pairs | Called 15× as final polish. Acceptable for typical batch counts. |
| `build_problem_matrix` uses `float32` | Halves memory vs float64 | Correct choice. ✓ |
| `dist_m()` fallback to `distance()` | Occurs for relocated items not in original matrix | Correct behaviour; minor performance loss only. |

---

## 6. Summary Table

| # | File · Function · Line | Problem | Severity |
|---|---|---|---|
| 1 | `core/forecasting.py` · `fit()` · L81 | Holt-Winters seasonality init is multiplicative; update is additive → systematic forecast error → bad relocation decisions | 🔴 High |
| 2 | `algorithms/relocation.py` · `_build_priority_list()` · L276 | `periods_in_target_class >= 0` always true; `u` threshold never enforced → over-aggressive relocation | 🟠 Medium |
| 3 | `algorithms/depso.py` · `_solve_impl()` · L162–171 | Stagnation counter incremented before local search in same iteration; inconsistent comparison baseline | 🟠 Medium |
| 4 | `algorithms/depso.py` · `_build_savings_particle()` · L245 | `list.index(o)` is O(K) per order → O(K²) savings particle build | 🟠 Medium (perf) |
| 5 | `algorithms/batching/first_fit.py` · L43–67 | Paper two-phase first-fit not implemented; single-pass used instead | 🟠 Medium (paper deviation) |
| 6 | `algorithms/rbrs_ae.py` · `_insertion_costs()` · L250–251 | `travel_distance == 0.0` used as "not computed" sentinel; ambiguous for zero-cost batches | 🟠 Medium |
| 7 | `algorithms/relocation.py` · `run_period()` · L206–211 | Rejected items (tdr≤0) re-queued asymmetrically; can exhaust suggestion budget on cycling failures | 🟠 Medium |
| 8 | `algorithms/rbrs_ae.py` · `_route_cost()` · L535 | Double deduplication via `frozenset` + NN's own `set` | 🟡 Low |
| 9 | `algorithms/depso.py` · `_local_search()` · L503 | Import inside while loop | 🟡 Low |
| 10 | All modules | `sys.path.insert(0, ...)` anti-pattern repeated in 10+ files | 🟡 Low |
| 11 | `algorithms/batching/savings.py` · L62–73 | O(n²·NN+2opt) inherently slow for large n | 🟡 Low |

---

## 7. Overall Assessment

**No Critical findings.** The overall data structures, location encoding scheme, distance matrix geometry, JSON schema alignment, and algorithm interfaces are **sound and mutually consistent**.

The most impactful fix is **Finding 1** (Holt-Winters seasonality initialization) — one line change that eliminates systematic forecast error propagating into all relocation decisions.

The second priority is **Finding 2** (relocation `u` threshold) — one comparison operator change that correctly enforces the paper's stability guard before triggering relocations.

Findings 3–7 are correctness or algorithmic-fidelity issues worth addressing before publishing results. Findings 8–11 are maintainability and style issues with no effect on current correctness.
