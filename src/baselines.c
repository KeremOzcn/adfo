#include "../include/baselines.h"
#include "../include/routing.h"
#include <stdlib.h>
#include <string.h>

static double batch_dist_items(const int *oids, int k,
                                const Instance *inst, Warehouse *wh) {
    if (k == 0) return 0.0;
    ItemLocation *locs = (ItemLocation*)malloc(k * sizeof(ItemLocation));
    for (int j = 0; j < k; j++) {
        locs[j].aisle    = inst->orders[oids[j] - 1].aisle;
        locs[j].position = inst->orders[oids[j] - 1].position;
    }
    double d = combined_plus_distance(locs, k, wh);
    free(locs);
    return d;
}

/* SOP: each order is its own picker trip */
double sop_distance(const Instance *inst, Warehouse *wh) {
    double total = 0.0;
    for (int i = 0; i < inst->n_orders; i++) {
        int oid = inst->orders[i].id;
        total += batch_dist_items(&oid, 1, inst, wh);
    }
    return total;
}

/* FCFS: first-fit batching in ascending order-ID sequence */
double fcfs_distance(const Instance *inst, Warehouse *wh) {
    int n = inst->n_orders;
    int **batches     = (int**)malloc(n * sizeof(int*));
    int  *buf         = (int*)malloc(n * n * sizeof(int));
    int  *batch_sizes = (int*)calloc(n, sizeof(int));
    double *bweights  = (double*)calloc(n, sizeof(double));
    for (int i = 0; i < n; i++) batches[i] = buf + i * n;

    /* Build index array sorted by order ID (ascending) */
    int *idx = (int*)malloc(n * sizeof(int));
    for (int i = 0; i < n; i++) idx[i] = i;
    for (int i = 1; i < n; i++) {
        int key = idx[i];
        int j = i - 1;
        while (j >= 0 && inst->orders[idx[j]].id > inst->orders[key].id) {
            idx[j + 1] = idx[j]; j--;
        }
        idx[j + 1] = key;
    }

    int nb = 0;
    for (int k = 0; k < n; k++) {
        int oi  = idx[k];
        int oid = inst->orders[oi].id;
        double w = inst->orders[oi].weight;
        int placed = 0;
        for (int b = 0; b < nb; b++) {
            if (bweights[b] + w <= inst->vehicle_capacity_wu) {
                batches[b][batch_sizes[b]++] = oid;
                bweights[b] += w;
                placed = 1; break;
            }
        }
        if (!placed) {
            batches[nb][0] = oid;
            batch_sizes[nb] = 1;
            bweights[nb]    = w;
            nb++;
        }
    }

    double total = 0.0;
    for (int b = 0; b < nb; b++)
        total += batch_dist_items(batches[b], batch_sizes[b], inst, wh);

    free(idx); free(bweights); free(batch_sizes); free(buf); free(batches);
    return total;
}
