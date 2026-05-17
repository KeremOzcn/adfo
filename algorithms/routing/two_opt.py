"""
algorithms/routing/two_opt.py
==============================
2-opt local search heuristic - Paper Appendix C.

Bir TSP tour'unu iyileştirmek için kullanılır.
Mevcut tour'daki iki kenarı çıkarıp yerine farklı iki kenar koyarak
gelişme arar.

Klasik 2-opt: tour'un (i, i+1) ve (j, j+1) kenarlarını çıkarıp
(i, j) ve (i+1, j+1) ile değiştirir; bu, (i+1..j) segmentini tersine çevirmeye
denk gelir.
"""


def two_opt_improve(route: list[int], warehouse,
                    max_iterations: int = 30,
                    max_no_improvement: int = 2) -> tuple[list[int], float]:
    """
    Bir rotayı 2-opt ile iyileştir.
    warehouse.dist_m() kullanır (numpy matris varsa O(1) lookup).
    """
    if len(route) <= 4:
        return route[:], _route_distance(route, warehouse)

    best_route = route[:]
    best_distance = _route_distance(best_route, warehouse)
    no_improvement_count = 0
    df = warehouse.dist_m  # lokal referans

    for _ in range(max_iterations):
        improved = False
        n = len(best_route)

        for i in range(1, n - 2):
            for j in range(i + 1, n - 1):
                d_before = (df(best_route[i - 1], best_route[i]) +
                            df(best_route[j],     best_route[j + 1]))
                d_after  = (df(best_route[i - 1], best_route[j]) +
                            df(best_route[i],     best_route[j + 1]))

                if d_after < d_before - 1e-9:
                    best_route[i:j + 1] = best_route[i:j + 1][::-1]
                    best_distance += (d_after - d_before)
                    improved = True

        if not improved:
            no_improvement_count += 1
            if no_improvement_count >= max_no_improvement:
                break
        else:
            no_improvement_count = 0

    return best_route, best_distance


def _route_distance(route: list[int], warehouse) -> float:
    """Bir rotanın toplam mesafesi."""
    if len(route) < 2:
        return 0.0
    df = warehouse.dist_m
    return sum(df(route[i], route[i + 1]) for i in range(len(route) - 1))


# ════════════════════════════════════════════════════════════════════════════
# YARDIMCI: NN + 2-opt birleşik
# ════════════════════════════════════════════════════════════════════════════

def nn_then_2opt(locations: list[int], warehouse) -> tuple[list[int], float]:
    """
    Paper'ın standart picker routing yaklaşımı:
    1) NN ile başlangıç çöz
    2) 2-opt ile iyileştir

    Bu fonksiyon, DEPSO içinde her batch için kullanılır.
    """
    from algorithms.routing.nearest_neighbor import nearest_neighbor_route

    route, _ = nearest_neighbor_route(locations, warehouse)
    return two_opt_improve(route, warehouse)


if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from core.warehouse import Warehouse
    from algorithms.routing.nearest_neighbor import nearest_neighbor_route

    wh = Warehouse()

    test_locs = [100, 1500, 3700, 5200, 6800, 800, 2400, 4100]

    nn_route, nn_dist = nearest_neighbor_route(test_locs, wh)
    print(f"NN sonucu:    {nn_route}")
    print(f"NN mesafesi:  {nn_dist:.2f} LU")

    opt_route, opt_dist = two_opt_improve(nn_route, wh)
    print(f"2-opt sonucu: {opt_route}")
    print(f"2-opt mesafe: {opt_dist:.2f} LU")
    print(f"İyileşme:     {(nn_dist - opt_dist) / nn_dist * 100:.1f}%")

    # Birleşik
    final_route, final_dist = nn_then_2opt(test_locs, wh)
    print(f"\nBirleşik (NN+2opt): mesafe={final_dist:.2f}")
