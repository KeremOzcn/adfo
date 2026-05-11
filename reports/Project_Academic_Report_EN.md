# Academic Report: Improving the Order Batching and Picker Routing Component of the Joint Warehouse Optimization Problem

## Abstract

This project is based on Kübler, Glock, and Bauernhansl (2020), which proposes an iterative heuristic method for jointly solving three interdependent warehouse planning problems: dynamic storage location assignment, order batching, and picker routing. The paper uses a Discrete Evolutionary Particle Swarm Optimization (DEPSO) algorithm to handle the order batching and picker routing subproblem, embedded within a broader iterative framework that also manages dynamic item relocation.

The present work focuses on improving the algorithmic core of the paper — the DEPSO component for joint order batching and picker routing — by proposing a new algorithm called **RBRS-AE (Route-Based Regret Search with Adaptive Elimination)**. RBRS-AE replaces the permutation-based PSO search with a regret-based batch construction mechanism combined with adaptive batch elimination. Benchmark experiments demonstrate that RBRS-AE consistently outperforms DEPSO across all tested scenarios, with travel distance improvements ranging from **+2.25% to +14.01%**.

**Keywords:** joint warehouse optimization, order batching, picker routing, dynamic storage location assignment, DEPSO, RBRS-AE, regret-based heuristic

---

## 1. Introduction

Order picking is one of the most expensive activities in warehouse operations, accounting for approximately 50% of total warehousing costs (De Koster et al., 2007). Kübler et al. (2020) identify three tightly interdependent planning decisions that must be made to operate an order picking system efficiently:

1. **Storage location assignment** — which items are stored at which rack positions.
2. **Order batching** — which customer orders are grouped into a single picker trip.
3. **Picker routing** — in what sequence a picker visits the storage locations within a batch.

Although these three problems are strongly interdependent, they have traditionally been solved separately, leading to suboptimal solutions. Kübler et al. (2020) propose an iterative heuristic that solves all three jointly, using DEPSO to handle the order batching and picker routing subproblem.

**Scope of this project:** This work focuses on improving the DEPSO component — the algorithm responsible for order batching and picker routing (Section 5 of the paper). The dynamic storage location assignment layer (Section 4 of the paper) is acknowledged as the broader context but is not re-implemented, as it requires real operational demand-time-series data that is proprietary and not publicly available. Our proposed RBRS-AE algorithm can serve as a drop-in replacement for DEPSO within the paper's full iterative framework.

---

## 2. Problem Definition

### 2.1 Full Problem (Paper Scope)

Kübler et al. (2020) study a low-level picker-to-parts warehouse with a multi-block layout (parallel aisles connected by cross-aisles). The depot is located at one end of the warehouse. Three decisions must be made jointly:

- **Storage location assignment:** Items are assigned to storage classes (A, B, C) based on demand frequency. As demand changes over time, items may need to be relocated.
- **Order batching:** A set of released customer orders must be partitioned into batches subject to a picker capacity constraint. Each order consists of one or more order lines; orders cannot be split across batches.
- **Picker routing:** For each batch, the picker must visit all required storage locations and return to the depot. The objective is to minimize total travel distance.

The paper's objective function minimizes total travel distance over all batches across all periods, accounting for relocation costs when items are moved.

### 2.2 Subproblem Addressed in This Work

This project addresses the **order batching and picker routing subproblem** — the decisions made within each time period once the storage locations are fixed. The mathematical formulation is:

$$
\min_{\pi} \sum_{b \in \mathcal{B}(\pi)} d(\text{route}(b))
$$

subject to:

$$
\sum_{o \in b} w_o \le C \quad \forall b \in \mathcal{B}(\pi)
$$

where $\pi$ is the order permutation, $\mathcal{B}(\pi)$ is the induced batch set, $w_o$ is the order weight, $d(\text{route}(b))$ is the travel distance for batch $b$ under the Combined+ routing heuristic, and $C$ is the picker capacity (100 WU in all experiments).

---

## 3. Paper's Solution Method (DEPSO)

### 3.1 Overall Iterative Framework

The paper proposes an iterative procedure with two alternating stages:

1. **Dynamic Storage Location Assignment Stage (Section 4):** Items are classified into demand classes (A, B, C) using an ABC forecasting procedure. Items stored in the wrong class are relocated using a priority-based relocation rule. Only relocations whose expected future benefits exceed their costs are executed.

2. **Order Batching and Picker Routing Stage (Section 5):** Given the current storage assignment, DEPSO is applied to find a good batch assignment and routing plan.

These stages alternate over multiple planning periods. Our work focuses exclusively on Stage 2.

### 3.2 DEPSO Algorithm (Section 5 of the Paper)

DEPSO represents each solution as a permutation of order IDs (particle). Orders are decoded into batches using a **first-fit rule**: each order is placed in the first batch with sufficient remaining capacity. Routes are computed using **Combined+ routing**, which selects the minimum of four classical heuristics:

- S-Shape (traversal)
- Return
- Midpoint
- Largest-Gap

**Initialization:**
- Particle 0: savings-based heuristic seed (farthest orders first).
- Particles 1 to P−1: random permutations.

**Velocity update (threshold-based, §6.2 of paper):**

For each position $h$, draw $r \sim U(0,1)$:
- $r < 0.5$: move toward **Gbest** (global best)
- $0.5 \le r < 0.8$: move toward **Pbest** (personal best)
- $r \ge 0.8$: no movement

**Mutation operators:** Swap, Shift, Inverse — applied with probability proportional to particle closeness to Gbest.

**Adaptive local search:** Triggered when stagnation is detected; applies swap-based improvement to the current Gbest.

**Parameters:** 5 particles, 500 iterations, capacity = 100 WU.

---

## 4. Proposed Solution Method: RBRS-AE

### 4.1 Motivation

DEPSO's permutation representation makes it difficult to reason explicitly about batch composition. The PSO movement operators do not directly account for routing costs when grouping orders. RBRS-AE replaces this with a **construction heuristic that explicitly evaluates insertion costs**, combined with an improvement loop.

### 4.2 Algorithm Description

RBRS-AE follows the pseudocode from the project's new report document and consists of the following steps:

**Step 1 — Priority Scoring:**
Each order $o$ receives a priority score equal to its Manhattan distance from the depot to its storage location. Orders farther from the depot are harder to consolidate efficiently and are assigned first.

**Step 2 — Sort Orders:**
Orders are sorted in descending priority order.

**Step 3 — Regret-Based Batch Construction:**
```
While unassigned orders remain:
  For each unassigned order o:
    Evaluate all feasible batch insertions (capacity check)
    cost[o, b] = distance(batch_b + o) - distance(batch_b)
    best_cost[o]   = min over all feasible options
    second_cost[o] = second-best cost
    regret[o]      = second_cost[o] - best_cost[o]
  Select order with highest regret
  Assign it to its best feasible batch (or open a new batch)
```

**Step 4 — Route Construction and Improvement:**
Compute Combined+ routing distance for all batches. Cache results by batch composition key.

**Step 5 — Iterative Improvement:**
```
While stopping criterion not satisfied:
  Apply Batch Shift (first-improvement)
  Apply Batch Swap (first-improvement)
  If stagnation >= stagnation_limit:
    Identify most inefficient batch (highest avg per-order distance)
    Dissolve it; reassign its orders via regret insertion
  Update best solution if improved
```

**Return:** best batch assignment and total travel distance.

### 4.3 Pseudocode Summary

| Pseudocode Step | Code Location |
|---|---|
| Priority score | `_priority_score(order_id)` |
| Sort orders | `sorted(..., key=_priority_score, reverse=True)` |
| Regret construction | `_build_solution()` → `_regret_step()` |
| Route evaluation | `_batch_distance()` → Combined+ |
| Set best solution | `best_dist = _construct_and_improve_routes(batches)` |
| Batch shift | `_batch_shift()` |
| Batch swap | `_batch_swap()` |
| Identify inefficient batch | `_identify_inefficient_batch()` |
| Adaptive elimination | `_adaptive_elimination()` |
| Update best | `if cur_dist < best_dist: best_dist = cur_dist` |
| Return | `return best_perm, best_dist, elapsed, best_batches` |

### 4.4 Key Design Decisions

- **Distance caching:** All `_batch_distance()` calls are cached by `tuple(sorted(order_ids))`. This eliminates redundant Combined+ evaluations during construction and improvement, making the algorithm practical for repeated calls.
- **First-improvement strategy:** Both Shift and Swap accept the first move that improves total distance. This keeps runtime low while finding good local optima.
- **Adaptive Elimination:** Triggered by stagnation. Dissolves the worst-performing batch and reassigns its orders via regret, allowing the algorithm to escape local optima without pure random restarts.

---

## 5. Experimental Design

### 5.1 Warehouse Model

Following the paper's warehouse structure (10 picking aisles, 4 cross-aisles, multi-block layout), our implementation uses:
- 10 picking aisles
- 4 cross-aisles
- 45 rack positions per aisle (450 storage locations total)
- Depot at front-left

Note: The paper uses a larger warehouse (7,200 storage locations). Our smaller scale is a simplification consistent with the paper's scenario parameter set.

### 5.2 Benchmark Scenarios

The paper uses the following parameters for scenario generation:
- Number of orders $N_{Ord} \in \{50, 100, 200\}$
- Maximum order lines per order $N_{max}^{ol} \in \{2, 4, 6, 8, 10\}$
- Maximum quantity per order line $A_{max} \in \{2, 4, 6, 8, 10\}$

Our experiments use five representative scenarios matching this parameter design:

| Scenario ID | Orders | Max Lines | Max Qty |
|---|---|---|---|
| 50_2_6 | 50 | 2 | 6 |
| 50_6_6 | 50 | 6 | 6 |
| 50_10_6 | 50 | 10 | 6 |
| 100_6_6 | 100 | 6 | 6 |
| 100_6_10 | 100 | 6 | 10 |

Demand follows an ABC-style distribution (Zipf-like), consistent with the paper's class-based storage framework. Since the paper's proprietary company data is not publicly available, synthetic instances are used. This limitation is explicitly acknowledged.

### 5.3 Baselines

In addition to DEPSO, two simple reference methods are evaluated:
- **SOP (Single Order Picking):** Each order is collected in a separate trip.
- **FCFS (First-Come-First-Served):** Orders are assigned to batches in original ID order using first-fit.

### 5.4 Algorithm Parameters

| Parameter | DEPSO | RBRS-AE |
|---|---|---|
| Iterations | 500 | 200 |
| Particles / Stagnation limit | 5 | 30 |
| Capacity | 100 WU | 100 WU |
| Routing | Combined+ | Combined+ |
| Seeds per scenario | 3 | 3 |

---

## 6. Results

### 6.1 Benchmark Results

Results over 5 scenarios, 3 seeds each:

| Scenario | SOP | FCFS | DEPSO | RBRS-AE | RBRS-AE vs DEPSO |
|:---|---:|---:|---:|---:|---:|
| 50_2_6   | 1742.7 | 556.0  | 429.0 | 419.3 | **+2.25%** |
| 50_6_6   | 1816.7 | 783.7  | 511.3 | 456.0 | **+10.82%** |
| 50_10_6  | 1816.0 | 908.0  | 597.0 | 570.3 | **+4.47%** |
| 100_6_6  | 3720.0 | 1594.0 | 777.0 | 718.7 | **+7.51%** |
| 100_6_10 | 3720.0 | 1885.7 | 940.0 | 808.3 | **+14.01%** |

*All distances in LU (Length Units). Positive RBRS-AE vs DEPSO = RBRS-AE is better.*

### 6.2 Key Observations

**RBRS-AE consistently outperforms DEPSO across all scenarios.** The improvement grows with problem complexity:

- **Simple instances (50_2_6, few order lines):** Both algorithms find near-optimal solutions. The RBRS-AE advantage is modest (+2.25%) because the problem has few conflicting batch assignments.
- **Complex instances (100_6_6, 100_6_10, many orders and lines):** RBRS-AE's advantage grows to +7.51% and +14.01%. With more orders and longer order lines, the regret-based construction correctly identifies which orders are costly to assign and groups them more efficiently.

**Both algorithms substantially reduce travel distance vs. SOP:**
- DEPSO: 78.4% reduction for 100_6_6
- RBRS-AE: 80.7% reduction for 100_6_6

This confirms that batch consolidation is highly effective and that RBRS-AE produces tighter batch groupings.

### 6.3 Runtime

| Scenario | DEPSO (s) | RBRS-AE (s) |
|---|---|---|
| 50_2_6 | ~5 | ~1 |
| 100_6_6 | ~10 | ~3 |

RBRS-AE is also significantly faster than DEPSO due to the distance cache eliminating redundant routing evaluations.

---

## 7. Discussion

### 7.1 Why RBRS-AE Outperforms DEPSO

DEPSO explores batch assignments through random permutation perturbations guided by PSO. The PSO operators (velocity, mutation) do not explicitly reason about routing costs — they search the permutation space hoping to find good batch groupings.

RBRS-AE, in contrast, **evaluates insertion costs explicitly** during construction. The regret mechanism ensures that the most "difficult" orders (those with the largest cost difference between their best and second-best placement) are assigned first, preventing poor assignments that are costly to fix later. This leads to better initial solutions and faster convergence.

### 7.2 Position Within the Paper's Framework

In the paper's full iterative framework, DEPSO is called after each storage location update. Our RBRS-AE can serve as a direct replacement: given the same storage assignment, RBRS-AE returns a better batch-routing plan with lower total distance and faster runtime. This would improve the performance of the full three-problem joint solution.

### 7.3 Related Work

A closely related paper by the same research group (Kübler, Glock, Bauernhansl 2020b — the present paper) extends the joint framework to include dynamic storage location assignment. Earlier works (Van Gils et al. 2019, Scholz & Wäscher 2017) solve order batching and routing jointly using iterated local search and integrated routing algorithms. RBRS-AE differs from these by introducing regret-based construction with adaptive elimination, which has not been applied to this problem class before.

---

## 8. Conclusion

This project implements and improves the algorithmic core of Kübler, Glock, and Bauernhansl (2020): the DEPSO component responsible for order batching and picker routing. The proposed RBRS-AE algorithm replaces PSO-based permutation search with regret-based batch construction and adaptive elimination.

**Main contributions:**
- Faithful reproduction of the DEPSO algorithm from the paper (velocity update, first-fit decoding, Combined+ routing, mutation operators)
- New RBRS-AE algorithm: priority scoring, regret construction, shift/swap improvement, adaptive elimination
- Benchmark analysis across 5 scenarios showing RBRS-AE achieves +2.25% to +14.01% improvement over DEPSO
- Distance caching mechanism that makes RBRS-AE 3–5× faster than DEPSO
- Live demo: `python main.py --demo` (completes in ~3 seconds)

**Scope limitation:** The dynamic storage location assignment component (Section 4 of the paper) is not implemented, as it requires multi-period demand time-series data that is proprietary. RBRS-AE is validated on the order batching and picker routing subproblem, consistent with the paper's Section 5 scope.

---

## 9. Project Architecture

| Module | Role |
|---|---|
| `warehouse.py` | Warehouse geometry (10 aisles, 4 cross-aisles, depot) |
| `routing.py` | Combined+ routing (S-Shape, Return, Midpoint, Largest-Gap) + NN+2opt |
| `instances.py` | Instance generation (ABC demand distribution, scenario parameters) |
| `depso.py` | DEPSO algorithm — faithful to paper Section 5 |
| `rbrs_ae_algorithm.py` | RBRS-AE — proposed new algorithm |
| `baselines.py` | SOP and FCFS reference methods |
| `main.py` | Benchmark pipeline (`--demo`, `--full`, `--validate`, `--scenario`) |
| `dashboard.py` | Interactive Streamlit visualization |

### Libraries Used

| Library | Purpose |
|---|---|
| `numpy` | Numerical operations, random number generation |
| `matplotlib` | Convergence curves and bar charts |
| `scipy` | Statistical utilities |
| `tqdm` | Progress bars for benchmark runs |
| `streamlit` | Interactive dashboard |
| `pandas` | Result table handling |

---

## 10. Limitations and Future Work

**Limitations:**
1. Dynamic storage location assignment is not implemented (requires proprietary demand data).
2. Warehouse scale is smaller than the paper's (450 vs. 7,200 storage locations).
3. Benchmark uses synthetic proxy scenarios, not the paper's real company data.
4. RBRS-AE uses first-improvement; best-improvement might yield higher quality at greater runtime cost.

**Future work:**
- Integrate RBRS-AE into the full three-problem iterative framework when real demand data becomes available.
- Scale experiments to 7,200-location warehouse.
- Apply Wilcoxon significance tests across all 35 scenario combinations.
- Compare against iterated local search (Van Gils et al. 2019) and other strong baselines.

---

## References

Kübler, P., Glock, C. H., & Bauernhansl, T. (2020). A new iterative method for solving the joint dynamic storage location assignment, order batching and picker routing problem in manual picker-to-parts warehouses. *Computers & Industrial Engineering*, 147, 106645. https://doi.org/10.1016/j.cie.2020.106645

De Koster, R., Le-Duc, T., & Roodbergen, K. J. (2007). Design and control of warehouse order picking: A literature review. *European Journal of Operational Research*, 182(2), 481–501.

Van Gils, T., Caris, A., Ramaekers, K., & Braekers, K. (2019). Formulating and solving the integrated batching, routing, and picker scheduling problem in a real-world spare parts warehouse. *European Journal of Operational Research*, 277(3), 920–932.

Scholz, A., & Wäscher, G. (2017). Order batching and picker routing in manual order picking systems: the benefits of integrated routing. *Central European Journal of Operations Research*, 25(2), 491–520.
