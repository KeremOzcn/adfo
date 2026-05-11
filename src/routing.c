
#include "../include/routing.h"
#include <stdlib.h>

static void build_aisle_map(const ItemLocation *items, size_t n, int n_aisles,
                           int **positions, int *counts) {
    for (int i = 0; i < n_aisles; ++i) counts[i] = 0;
    for (size_t i = 0; i < n; ++i) {
        int a = items[i].aisle;
        if (a >= 0 && a < n_aisles) {
            int c = counts[a];
            positions[a][c] = items[i].position;
            counts[a] = c + 1;
        }
    }
    for (int i = 0; i < n_aisles; ++i) {
        /* sort and deduplicate */
        if (counts[i] > 1) {
            int *arr = positions[i];
            int m = counts[i];
            /* simple insertion sort */
            for (int p = 1; p < m; ++p) {
                int key = arr[p];
                int q = p - 1;
                while (q >= 0 && arr[q] > key) { arr[q + 1] = arr[q]; --q; }
                arr[q + 1] = key;
            }
            /* dedupe */
            int k = 1;
            for (int p = 1; p < m; ++p) if (arr[p] != arr[p-1]) arr[k++] = arr[p];
            counts[i] = k;
        }
    }
}

static double manh(double a, double b) { return a >= b ? a - b : b - a; }

static double s_shape_distance(const ItemLocation *items, size_t n, Warehouse *wh) {
    if (n == 0) return 0.0;
    int n_aisles = wh->cfg.n_aisles;
    int max_pos = (int)n;
    int **positions = (int**)malloc(sizeof(int*) * n_aisles);
    int *buf = (int*)malloc(sizeof(int) * n_aisles * max_pos);
    int *counts = (int*)malloc(sizeof(int) * n_aisles);
    for (int i = 0; i < n_aisles; ++i) positions[i] = buf + i * max_pos;
    build_aisle_map(items, n, n_aisles, positions, counts);

    double depot_x = wh->depot_x, depot_y = wh->depot_y;
    double front_y = wh->cross_aisle_y[0];
    double back_y = wh->cross_aisle_y[wh->cfg.n_cross_aisles - 1];

    double distance = 0.0;
    double current_x = depot_x, current_y = depot_y;
    int entering_from_front = 1;

    /* collect visited aisles */
    int *visited = (int*)malloc(sizeof(int) * n_aisles);
    int vcount = 0;
    for (int i = 0; i < n_aisles; ++i) if (counts[i] > 0) visited[vcount++] = i;
    /* sorted already as i increases */

    for (int idx = 0; idx < vcount; ++idx) {
        int aisle = visited[idx];
        double aisle_x = wh->aisle_x[aisle];
        if (entering_from_front) {
            distance += manh(current_x, aisle_x) + manh(current_y, front_y);
            current_x = aisle_x; current_y = front_y;
            distance += back_y - front_y;
            current_y = back_y; entering_from_front = 0;
        } else {
            distance += manh(current_x, aisle_x) + manh(current_y, back_y);
            current_x = aisle_x; current_y = back_y;
            distance += back_y - front_y;
            current_y = front_y; entering_from_front = 1;
        }
    }

    distance += manh(current_x, depot_x) + manh(current_y, depot_y);

    free(visited); free(counts); free(buf); free(positions);
    return distance;
}

static double return_distance(const ItemLocation *items, size_t n, Warehouse *wh) {
    if (n == 0) return 0.0;
    int n_aisles = wh->cfg.n_aisles;
    int max_pos = (int)n;
    int **positions = (int**)malloc(sizeof(int*) * n_aisles);
    int *buf = (int*)malloc(sizeof(int) * n_aisles * max_pos);
    int *counts = (int*)malloc(sizeof(int) * n_aisles);
    for (int i = 0; i < n_aisles; ++i) positions[i] = buf + i * max_pos;
    build_aisle_map(items, n, n_aisles, positions, counts);

    double depot_x = wh->depot_x, depot_y = wh->depot_y;
    double front_y = wh->cross_aisle_y[0];

    double distance = 0.0;
    double current_x = depot_x, current_y = depot_y;

    for (int aisle = 0; aisle < n_aisles; ++aisle) if (counts[aisle] > 0) {
        double aisle_x = wh->aisle_x[aisle];
        /* compute farthest y */
        double farthest_y = front_y;
        for (int p = 0; p < counts[aisle]; ++p) {
            double y; warehouse_get_location_coords(wh, aisle, positions[aisle][p], NULL, &y);
            if (y > farthest_y) farthest_y = y;
        }
        distance += manh(current_x, aisle_x) + manh(current_y, front_y);
        current_x = aisle_x; current_y = front_y;
        distance += 2.0 * (farthest_y - front_y);
        current_y = front_y;
    }

    distance += manh(current_x, depot_x) + manh(current_y, depot_y);

    free(counts); free(buf); free(positions);
    return distance;
}

static double midpoint_distance(const ItemLocation *items, size_t n, Warehouse *wh) {
    if (n == 0) return 0.0;
    int n_aisles = wh->cfg.n_aisles;
    int max_pos = (int)n;
    int **positions = (int**)malloc(sizeof(int*) * n_aisles);
    int *buf = (int*)malloc(sizeof(int) * n_aisles * max_pos);
    int *counts = (int*)malloc(sizeof(int) * n_aisles);
    for (int i = 0; i < n_aisles; ++i) positions[i] = buf + i * max_pos;
    build_aisle_map(items, n, n_aisles, positions, counts);

    double depot_x = wh->depot_x, depot_y = wh->depot_y;
    double front_y = wh->cross_aisle_y[0];
    double back_y = wh->cross_aisle_y[wh->cfg.n_cross_aisles - 1];
    double mid_y = (front_y + back_y) / 2.0;

    double distance = 0.0;
    double current_x = depot_x, current_y = depot_y;

    for (int aisle = 0; aisle < n_aisles; ++aisle) if (counts[aisle] > 0) {
        double aisle_x = wh->aisle_x[aisle];
        double front_items_max = -1e300;
        double back_items_min = 1e300;
        for (int p = 0; p < counts[aisle]; ++p) {
            double y; warehouse_get_location_coords(wh, aisle, positions[aisle][p], NULL, &y);
            if (y <= mid_y && y > front_items_max) front_items_max = y;
            if (y > mid_y && y < back_items_min) back_items_min = y;
        }

        if (front_items_max > -1e200 && back_items_min < 1e200) {
            distance += manh(current_x, aisle_x) + manh(current_y, front_y);
            distance += back_y - front_y;
            current_x = aisle_x; current_y = back_y;
        } else if (front_items_max > -1e200) {
            double farthest = front_items_max;
            distance += manh(current_x, aisle_x) + manh(current_y, front_y);
            distance += 2.0 * (farthest - front_y);
            current_x = aisle_x; current_y = front_y;
        } else if (back_items_min < 1e200) {
            double nearest = back_items_min;
            distance += manh(current_x, aisle_x) + manh(current_y, back_y);
            distance += 2.0 * (back_y - nearest);
            current_x = aisle_x; current_y = back_y;
        }
    }

    distance += manh(current_x, wh->depot_x) + manh(current_y, wh->depot_y);

    free(counts); free(buf); free(positions);
    return distance;
}

static double largest_gap_distance(const ItemLocation *items, size_t n, Warehouse *wh) {
    if (n == 0) return 0.0;
    int n_aisles = wh->cfg.n_aisles;
    int max_pos = (int)n;
    int **positions = (int**)malloc(sizeof(int*) * n_aisles);
    int *buf = (int*)malloc(sizeof(int) * n_aisles * max_pos);
    int *counts = (int*)malloc(sizeof(int) * n_aisles);
    for (int i = 0; i < n_aisles; ++i) positions[i] = buf + i * max_pos;
    build_aisle_map(items, n, n_aisles, positions, counts);

    double distance = 0.0;
    double current_x = wh->depot_x, current_y = wh->depot_y;
    double front_y = wh->cross_aisle_y[0];
    double back_y = wh->cross_aisle_y[wh->cfg.n_cross_aisles - 1];

    for (int aisle = 0; aisle < n_aisles; ++aisle) if (counts[aisle] > 0) {
        double aisle_x = wh->aisle_x[aisle];
        int m = counts[aisle];
        double *ys = (double*)malloc(sizeof(double) * m);
        for (int p = 0; p < m; ++p) warehouse_get_location_coords(wh, aisle, positions[aisle][p], NULL, &ys[p]);
        /* sort ys */
        for (int i = 1; i < m; ++i) { double key = ys[i]; int j = i-1; while (j>=0 && ys[j]>key){ ys[j+1]=ys[j]; --j;} ys[j+1]=key; }

        /* compute gaps */
        double best_gap = -1.0; int best_type = 0; int best_idx = 0; /* 0 front, 1 mid, 2 back */
        double gap_front = ys[0] - front_y; if (gap_front > best_gap) { best_gap = gap_front; best_type = 0; }
        for (int i = 0; i < m-1; ++i) { double g = ys[i+1]-ys[i]; if (g > best_gap) { best_gap = g; best_type = 1; best_idx = i+1; } }
        double gap_back = back_y - ys[m-1]; if (gap_back > best_gap) { best_gap = gap_back; best_type = 2; }

        if (best_type == 0) {
            distance += manh(current_x, aisle_x) + manh(current_y, back_y);
            distance += 2.0 * (back_y - ys[0]);
            current_x = aisle_x; current_y = back_y;
        } else if (best_type == 2) {
            distance += manh(current_x, aisle_x) + manh(current_y, front_y);
            distance += 2.0 * (ys[m-1] - front_y);
            current_x = aisle_x; current_y = front_y;
        } else {
            int idx = best_idx;
            double front_dist = 0.0; if (idx>0) front_dist = 2.0 * (ys[idx-1] - front_y);
            double back_dist = 0.0; if (idx < m) back_dist = 2.0 * (back_y - ys[idx]);
            distance += manh(current_x, aisle_x) + manh(current_y, front_y);
            distance += front_dist;
            distance += manh(front_y, back_y);
            distance += back_dist;
            current_x = aisle_x; current_y = back_y;
        }
        free(ys);
    }

    distance += manh(current_x, wh->depot_x) + manh(current_y, wh->depot_y);

    free(counts); free(buf); free(positions);
    return distance;
}

double combined_plus_distance(const ItemLocation *item_locations, size_t n_items, Warehouse *wh) {
    if (n_items == 0) return 0.0;
    double d1 = s_shape_distance(item_locations, n_items, wh);
    double d2 = return_distance(item_locations, n_items, wh);
    double d3 = midpoint_distance(item_locations, n_items, wh);
    double d4 = largest_gap_distance(item_locations, n_items, wh);
    double best = d1;
    if (d2 < best) best = d2;
    if (d3 < best) best = d3;
    if (d4 < best) best = d4;
    return best;
}
