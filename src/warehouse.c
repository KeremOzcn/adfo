
#include "../include/warehouse.h"
#include <stdlib.h>
#include <string.h>

static WarehouseConfig default_config(void) {
    WarehouseConfig c;
    c.n_aisles = 10;
    c.n_cross_aisles = 4;
    c.n_positions_per_aisle = 45;
    c.aisle_width = 2.0;
    c.rack_depth = 1.0;
    c.cross_aisle_width = 2.0;
    c.position_length = 1.0;
    return c;
}

Warehouse* warehouse_create(const WarehouseConfig* cfg_in) {
    WarehouseConfig cfg = cfg_in ? *cfg_in : default_config();
    Warehouse* w = (Warehouse*)malloc(sizeof(Warehouse));
    if (!w) return NULL;
    w->cfg = cfg;

    w->n_blocks = cfg.n_cross_aisles - 1;
    w->positions_per_block = cfg.n_positions_per_aisle / w->n_blocks;
    w->aisle_spacing = cfg.aisle_width + 2.0 * cfg.rack_depth;

    /* aisle_x */
    w->aisle_x = (double*)malloc(sizeof(double) * cfg.n_aisles);
    for (int i = 0; i < cfg.n_aisles; ++i) {
        w->aisle_x[i] = (i + 1) * w->aisle_spacing;
    }

    /* cross_aisle_y */
    w->cross_aisle_y = (double*)malloc(sizeof(double) * cfg.n_cross_aisles);
    double block_length = w->positions_per_block * cfg.position_length;
    for (int j = 0; j < cfg.n_cross_aisles; ++j) {
        w->cross_aisle_y[j] = j * (block_length + cfg.cross_aisle_width);
    }

    w->aisle_length = w->cross_aisle_y[cfg.n_cross_aisles - 1] - w->cross_aisle_y[0];
    w->depot_x = 0.0;
    w->depot_y = w->cross_aisle_y[0];

    /* locations */
    w->n_locations = (size_t)cfg.n_aisles * (size_t)cfg.n_positions_per_aisle;
    w->locations = (Location*)malloc(sizeof(Location) * w->n_locations);
    if (!w->locations) {
        free(w->aisle_x);
        free(w->cross_aisle_y);
        free(w);
        return NULL;
    }
    size_t idx = 0;
    for (int aisle_idx = 0; aisle_idx < cfg.n_aisles; ++aisle_idx) {
        double x = w->aisle_x[aisle_idx];
        for (int pos_idx = 1; pos_idx <= cfg.n_positions_per_aisle; ++pos_idx) {
            int block = (pos_idx - 1) / w->positions_per_block;
            int pos_in_block = (pos_idx - 1) % w->positions_per_block;
            double y = (w->cross_aisle_y[block]
                        + cfg.cross_aisle_width
                        + (pos_in_block + 0.5) * cfg.position_length);
            w->locations[idx].aisle_idx = aisle_idx;
            w->locations[idx].pos_idx = pos_idx;
            w->locations[idx].x = x;
            w->locations[idx].y = y;
            ++idx;
        }
    }

    return w;
}

void warehouse_destroy(Warehouse* w) {
    if (!w) return;
    free(w->aisle_x);
    free(w->cross_aisle_y);
    free(w->locations);
    free(w);
}

void warehouse_get_location_coords(Warehouse* w, int aisle, int position, double* out_x, double* out_y) {
    if (!w || aisle < 0 || aisle >= w->cfg.n_aisles || position < 1 || position > w->cfg.n_positions_per_aisle) {
        if (out_x) *out_x = 0.0;
        if (out_y) *out_y = 0.0;
        return;
    }
    double x = w->aisle_x[aisle];
    int block = (position - 1) / w->positions_per_block;
    int pos_in_block = (position - 1) % w->positions_per_block;
    double y = (w->cross_aisle_y[block]
                + w->cfg.cross_aisle_width
                + (pos_in_block + 0.5) * w->cfg.position_length);
    if (out_x) *out_x = x;
    if (out_y) *out_y = y;
}

void warehouse_get_depot_coords(Warehouse* w, double* out_x, double* out_y) {
    if (!w) return;
    if (out_x) *out_x = w->depot_x;
    if (out_y) *out_y = w->depot_y;
}

double warehouse_manhattan_distance(double x1, double y1, double x2, double y2) {
    double dx = x1 - x2; if (dx < 0) dx = -dx;
    double dy = y1 - y2; if (dy < 0) dy = -dy;
    return dx + dy;
}

