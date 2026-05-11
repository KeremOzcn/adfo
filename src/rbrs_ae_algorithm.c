#include "../include/rbrs_ae_algorithm.h"
#include "../include/routing.h"
#include <stdlib.h>
#include <string.h>
#include <float.h>

/* ---- Batch distance helpers ---- */

static double batch_dist(const int *oids, int k,
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

/* Distance of batch b with one extra order appended (non-destructive) */
static double batch_dist_with(int *batch, int size, int extra_oid,
                               const Instance *inst, Warehouse *wh) {
    ItemLocation *locs = (ItemLocation*)malloc((size + 1) * sizeof(ItemLocation));
    for (int j = 0; j < size; j++) {
        locs[j].aisle    = inst->orders[batch[j] - 1].aisle;
        locs[j].position = inst->orders[batch[j] - 1].position;
    }
    locs[size].aisle    = inst->orders[extra_oid - 1].aisle;
    locs[size].position = inst->orders[extra_oid - 1].position;
    double d = combined_plus_distance(locs, size + 1, wh);
    free(locs);
    return d;
}

static double marginal_cost(int oid, int b, int **batches, int *sizes,
                              const Instance *inst, Warehouse *wh) {
    double old_cost = batch_dist(batches[b], sizes[b], inst, wh);
    double new_cost = batch_dist_with(batches[b], sizes[b], oid, inst, wh);
    return new_cost - old_cost;
}

static int weight_ok(int oid, int b, double *bweights,
                      double capacity, const Instance *inst) {
    return bweights[b] + inst->orders[oid - 1].weight <= capacity;
}

static double total_cost(int **batches, int *sizes, int nb,
                          const Instance *inst, Warehouse *wh) {
    double t = 0.0;
    for (int b = 0; b < nb; b++)
        t += batch_dist(batches[b], sizes[b], inst, wh);
    return t;
}

/* ---- Public API ---- */

RBRS_AE* rbrs_create(const Instance *inst, Warehouse *wh,
                     int max_iters, int stagnation_limit) {
    RBRS_AE *r = (RBRS_AE*)malloc(sizeof(RBRS_AE));
    if (!r) return NULL;
    r->inst             = inst;
    r->wh               = wh;
    r->max_iterations   = max_iters       > 0 ? max_iters       : 100;
    r->stagnation_limit = stagnation_limit > 0 ? stagnation_limit : 20;
    return r;
}

void rbrs_destroy(RBRS_AE *r) { free(r); }

double rbrs_run(RBRS_AE *r, int **out_perm, size_t *out_len) {
    const Instance *inst = r->inst;
    Warehouse       *wh  = r->wh;
    int n   = inst->n_orders;
    double cap = inst->vehicle_capacity_wu;

    /* Fixed-layout batch storage */
    int    **batches  = (int**)malloc(n * sizeof(int*));
    int     *buf      = (int*)malloc(n * n * sizeof(int));
    int     *sizes    = (int*)calloc(n, sizeof(int));
    double  *bweights = (double*)calloc(n, sizeof(double));
    for (int i = 0; i < n; i++) batches[i] = buf + i * n;
    int nb = 0;

    int *unassigned = (int*)malloc(n * sizeof(int));
    int nu = n;
    for (int i = 0; i < n; i++) unassigned[i] = inst->orders[i].id;

    /* ---- Regret-based construction ---- */
    while (nu > 0) {
        int    best_oi    = 0;
        double best_regret = -1.0;
        int    best_batch  = nb;

        for (int oi = 0; oi < nu; oi++) {
            int oid = unassigned[oi];
            double cost1 = DBL_MAX, cost2 = DBL_MAX;
            int    batch1 = nb;

            for (int b = 0; b < nb; b++) {
                if (!weight_ok(oid, b, bweights, cap, inst)) continue;
                double mc = marginal_cost(oid, b, batches, sizes, inst, wh);
                if (mc < cost1) { cost2 = cost1; cost1 = mc; batch1 = b; }
                else if (mc < cost2) { cost2 = mc; }
            }

            double new_cost = batch_dist(&oid, 1, inst, wh);
            if (new_cost < cost1) {
                cost2 = cost1; cost1 = new_cost; batch1 = nb;
            } else if (new_cost < cost2) {
                cost2 = new_cost;
            }

            if (cost2 == DBL_MAX) cost2 = cost1;
            double regret = cost2 - cost1;

            if (regret > best_regret) {
                best_regret = regret;
                best_oi     = oi;
                best_batch  = batch1;
            }
        }

        int oid = unassigned[best_oi];
        if (best_batch == nb) {
            batches[nb][0] = oid;
            sizes[nb]      = 1;
            bweights[nb]   = inst->orders[oid - 1].weight;
            nb++;
        } else {
            batches[best_batch][sizes[best_batch]++] = oid;
            bweights[best_batch] += inst->orders[oid - 1].weight;
        }
        unassigned[best_oi] = unassigned[nu - 1];
        nu--;
    }
    free(unassigned);

    double current = total_cost(batches, sizes, nb, inst, wh);

    /* ---- Improvement: batch shift + batch swap + adaptive elimination ---- */
    int stagnation = 0;

    for (int iter = 0; iter < r->max_iterations; iter++) {
        int improved = 0;

        /* Batch shift: try relocating each order to a better batch */
        for (int b = 0; b < nb; b++) {
            int j = 0;
            while (j < sizes[b]) {
                int oid = batches[b][j];

                double old_b = batch_dist(batches[b], sizes[b], inst, wh);
                /* Remove oid by swapping with last element */
                batches[b][j] = batches[b][sizes[b] - 1];
                sizes[b]--;
                double new_b = batch_dist(batches[b], sizes[b], inst, wh);
                double save  = old_b - new_b;

                int    best_b2     = -1;
                double best_insert = DBL_MAX;
                for (int b2 = 0; b2 < nb; b2++) {
                    if (b2 == b) continue;
                    if (!weight_ok(oid, b2, bweights, cap, inst)) continue;
                    double mc = marginal_cost(oid, b2, batches, sizes, inst, wh);
                    if (mc < best_insert) { best_insert = mc; best_b2 = b2; }
                }

                if (best_b2 >= 0 && save - best_insert > 1e-9) {
                    batches[best_b2][sizes[best_b2]++] = oid;
                    bweights[best_b2] += inst->orders[oid - 1].weight;
                    bweights[b]       -= inst->orders[oid - 1].weight;
                    current           -= (save - best_insert);
                    improved = 1;
                    if (sizes[b] == 0) {
                        /* Compact: copy last batch into slot b */
                        memcpy(batches[b], batches[nb - 1], sizes[nb - 1] * sizeof(int));
                        sizes[b]    = sizes[nb - 1];
                        bweights[b] = bweights[nb - 1];
                        nb--;
                        j = sizes[b]; /* stop iterating this (now replaced) batch */
                    }
                    /* j unchanged: former last element is now at position j */
                } else {
                    /* Revert removal */
                    sizes[b]++;
                    batches[b][sizes[b] - 1] = batches[b][j];
                    batches[b][j]            = oid;
                    j++;
                }
            }
        }

        /* Batch swap: try exchanging a pair of orders across batches */
        for (int b1 = 0; b1 < nb && !improved; b1++) {
            for (int b2 = b1 + 1; b2 < nb && !improved; b2++) {
                for (int j1 = 0; j1 < sizes[b1] && !improved; j1++) {
                    for (int j2 = 0; j2 < sizes[b2] && !improved; j2++) {
                        int oid1 = batches[b1][j1];
                        int oid2 = batches[b2][j2];
                        double w1 = bweights[b1]
                                    - inst->orders[oid1 - 1].weight
                                    + inst->orders[oid2 - 1].weight;
                        double w2 = bweights[b2]
                                    - inst->orders[oid2 - 1].weight
                                    + inst->orders[oid1 - 1].weight;
                        if (w1 > cap || w2 > cap) continue;

                        double old1 = batch_dist(batches[b1], sizes[b1], inst, wh);
                        double old2 = batch_dist(batches[b2], sizes[b2], inst, wh);
                        batches[b1][j1] = oid2;
                        batches[b2][j2] = oid1;
                        double new1 = batch_dist(batches[b1], sizes[b1], inst, wh);
                        double new2 = batch_dist(batches[b2], sizes[b2], inst, wh);
                        double delta = (new1 + new2) - (old1 + old2);
                        if (delta < -1e-9) {
                            bweights[b1] = w1;
                            bweights[b2] = w2;
                            current += delta;
                            improved = 1;
                        } else {
                            batches[b1][j1] = oid1;
                            batches[b2][j2] = oid2;
                        }
                    }
                }
            }
        }

        if (improved) {
            stagnation = 0;
        } else {
            stagnation++;
            /* Adaptive elimination: remove worst batch and reinsert its orders */
            if (nb > 1) {
                int    worst_b   = 0;
                double worst_avg = 0.0;
                for (int b = 0; b < nb; b++) {
                    double d   = batch_dist(batches[b], sizes[b], inst, wh);
                    double avg = sizes[b] > 0 ? d / sizes[b] : 0.0;
                    if (avg > worst_avg) { worst_avg = avg; worst_b = b; }
                }
                int *to_reinsert = (int*)malloc(sizes[worst_b] * sizeof(int));
                int nr = sizes[worst_b];
                memcpy(to_reinsert, batches[worst_b], nr * sizeof(int));

                memcpy(batches[worst_b], batches[nb - 1], sizes[nb - 1] * sizeof(int));
                sizes[worst_b]    = sizes[nb - 1];
                bweights[worst_b] = bweights[nb - 1];
                nb--;

                for (int ri = 0; ri < nr; ri++) {
                    int oid = to_reinsert[ri];
                    double best_mc = DBL_MAX;
                    int    best_b  = -1;
                    for (int b = 0; b < nb; b++) {
                        if (!weight_ok(oid, b, bweights, cap, inst)) continue;
                        double mc = marginal_cost(oid, b, batches, sizes, inst, wh);
                        if (mc < best_mc) { best_mc = mc; best_b = b; }
                    }
                    if (best_b >= 0) {
                        batches[best_b][sizes[best_b]++] = oid;
                        bweights[best_b] += inst->orders[oid - 1].weight;
                    } else {
                        batches[nb][0] = oid;
                        sizes[nb]      = 1;
                        bweights[nb]   = inst->orders[oid - 1].weight;
                        nb++;
                    }
                }
                free(to_reinsert);
                current    = total_cost(batches, sizes, nb, inst, wh);
                stagnation = 0;
            }
        }

        if (stagnation >= r->stagnation_limit) break;
    }

    /* Flatten batches into output permutation */
    int *perm = (int*)malloc(n * sizeof(int));
    int pi = 0;
    for (int b = 0; b < nb; b++)
        for (int j = 0; j < sizes[b]; j++)
            perm[pi++] = batches[b][j];

    free(bweights); free(sizes); free(buf); free(batches);

    if (out_perm) *out_perm = perm; else free(perm);
    if (out_len)  *out_len  = n;
    return current;
}
