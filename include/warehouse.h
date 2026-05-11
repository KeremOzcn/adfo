#ifndef WAREHOUSE_H
#define WAREHOUSE_H

#include <stddef.h>

typedef struct WarehouseConfig {
    int n_aisles;
    int n_cross_aisles;
    int n_positions_per_aisle;
    double aisle_width;
    double rack_depth;
    double cross_aisle_width;
    double position_length;
} WarehouseConfig;

typedef struct Location {
    int aisle_idx;
    int pos_idx;
    double x;
    double y;
} Location;

typedef struct Warehouse {
    WarehouseConfig cfg;
    int n_blocks;
    int positions_per_block;
    double aisle_spacing;
    double *aisle_x;         /* length n_aisles */
    double *cross_aisle_y;   /* length n_cross_aisles */
    double aisle_length;
    double depot_x;
    double depot_y;
    Location *locations;     /* length n_aisles * n_positions_per_aisle */
    size_t n_locations;
} Warehouse;

Warehouse* warehouse_create(const WarehouseConfig* cfg);
void warehouse_destroy(Warehouse* w);
void warehouse_get_location_coords(Warehouse* w, int aisle, int position, double* out_x, double* out_y);
void warehouse_get_depot_coords(Warehouse* w, double* out_x, double* out_y);
double warehouse_manhattan_distance(double x1, double y1, double x2, double y2);

#endif // WAREHOUSE_H
