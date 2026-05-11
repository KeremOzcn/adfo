#ifndef INSTANCES_H
#define INSTANCES_H

#include <stddef.h>

struct Warehouse;

typedef struct Scenario {
    int n_orders;
    int n_max_orderlines;
    int a_max_per_line;
} Scenario;

typedef struct Order {
    int id;
    int aisle;
    int position;
    double weight;
} Order;

typedef struct Instance {
    char scenario_id[64];
    int seed;
    double vehicle_capacity_wu;
    int n_orders;
    Order *orders; /* length n_orders */
} Instance;

Instance* generate_instance(const Scenario *scenario, const struct Warehouse *warehouse, int seed);
void destroy_instance(Instance *inst);

#endif // INSTANCES_H
