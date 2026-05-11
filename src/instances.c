
#include "../include/instances.h"
#include "../include/warehouse.h"
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

static double rnd_double(unsigned *state) {
    *state = (*state * 1103515245u + 12345u);
    return (double)((*state >> 16) & 0x7FFF) / 32767.0;
}

Instance* generate_instance(const Scenario *scenario, const Warehouse *warehouse, int seed) {
    if (!scenario || !warehouse) return NULL;
    Instance *inst = (Instance*)malloc(sizeof(Instance));
    if (!inst) return NULL;
    snprintf(inst->scenario_id, sizeof(inst->scenario_id), "%d_%d_%d", scenario->n_orders, scenario->n_max_orderlines, scenario->a_max_per_line);
    inst->seed = seed;
    inst->vehicle_capacity_wu = 100.0;
    inst->n_orders = scenario->n_orders;
    inst->orders = (Order*)malloc(sizeof(Order) * inst->n_orders);
    if (!inst->orders) { free(inst); return NULL; }

    unsigned state = (unsigned)seed;
    int n_aisles = warehouse->cfg.n_aisles;
    int n_positions = warehouse->cfg.n_positions_per_aisle;

    for (int i = 0; i < inst->n_orders; ++i) {
        inst->orders[i].id = i + 1;
        inst->orders[i].aisle = (int)(rnd_double(&state) * n_aisles);
        if (inst->orders[i].aisle >= n_aisles) inst->orders[i].aisle = n_aisles - 1;
        inst->orders[i].position = 1 + (int)(rnd_double(&state) * n_positions);
        if (inst->orders[i].position > n_positions) inst->orders[i].position = n_positions;
        inst->orders[i].weight = 0.1 + rnd_double(&state) * 0.9; /* in [0.1,1.0] */
    }

    return inst;
}

void destroy_instance(Instance *inst) {
    if (!inst) return;
    free(inst->orders);
    free(inst);
}
