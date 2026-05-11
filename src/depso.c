#include "../include/depso.h"
#include "../include/routing.h"
#include <stdlib.h>
#include <string.h>
#include <float.h>

/* ---- LCG random number helpers ---- */

static double lcg_rand(unsigned *s) {
    *s = *s * 1103515245u + 12345u;
    return ((double)((*s >> 16) & 0x7FFFu)) / (double)0x7FFFu;
}

static int lcg_rand_int(unsigned *s, int n) {
    *s = *s * 1103515245u + 12345u;
    return (int)(((*s >> 16) & 0x7FFFu) % (unsigned)n);
}

/* ---- Permutation helpers ---- */

/* Sort by (aisle, position) — a natural sweep order as savings seed */
static void savings_seed(int *perm, const Instance *inst) {
    int n = inst->n_orders;
    for (int i = 0; i < n; i++) perm[i] = inst->orders[i].id;
    for (int i = 1; i < n; i++) {
        int key = perm[i];
        int a_k = inst->orders[key - 1].aisle;
        int p_k = inst->orders[key - 1].position;
        int j = i - 1;
        while (j >= 0) {
            int a_j = inst->orders[perm[j] - 1].aisle;
            int p_j = inst->orders[perm[j] - 1].position;
            if (a_j > a_k || (a_j == a_k && p_j > p_k)) {
                perm[j + 1] = perm[j]; j--;
            } else break;
        }
        perm[j + 1] = key;
    }
}

static void random_perm(int *perm, const Instance *inst, unsigned *s) {
    int n = inst->n_orders;
    for (int i = 0; i < n; i++) perm[i] = inst->orders[i].id;
    for (int i = n - 1; i > 0; i--) {
        int j = lcg_rand_int(s, i + 1);
        int tmp = perm[i]; perm[i] = perm[j]; perm[j] = tmp;
    }
}

/* ---- First-fit batching ---- */

static int first_fit_batching(const int *order_ids, int n_orders,
                               const double *weights, double capacity,
                               int **batches, int *batch_sizes) {
    int n_batches = 0;
    double *bw = (double*)calloc(n_orders, sizeof(double));
    for (int i = 0; i < n_orders; i++) batch_sizes[i] = 0;

    for (int idx = 0; idx < n_orders; idx++) {
        int oid  = order_ids[idx];
        double w = weights[oid - 1];
        int placed = 0;
        for (int b = 0; b < n_batches; b++) {
            if (bw[b] + w <= capacity) {
                batches[b][batch_sizes[b]++] = oid;
                bw[b] += w;
                placed = 1; break;
            }
        }
        if (!placed) {
            batches[n_batches][0] = oid;
            batch_sizes[n_batches] = 1;
            bw[n_batches]          = w;
            n_batches++;
        }
    }
    free(bw);
    return n_batches;
}

/* ---- Solution evaluation ---- */

static double evaluate(const int *perm, int n, const Instance *inst, Warehouse *wh) {
    double *weights = (double*)malloc(n * sizeof(double));
    for (int i = 0; i < n; i++) weights[i] = inst->orders[i].weight;

    int **batches = (int**)malloc(n * sizeof(int*));
    int  *buf     = (int*)malloc(n * n * sizeof(int));
    int  *sizes   = (int*)malloc(n * sizeof(int));
    for (int i = 0; i < n; i++) batches[i] = buf + i * n;

    int nb = first_fit_batching(perm, n, weights, inst->vehicle_capacity_wu, batches, sizes);

    double total = 0.0;
    for (int b = 0; b < nb; b++) {
        int k = sizes[b];
        ItemLocation *locs = (ItemLocation*)malloc(k * sizeof(ItemLocation));
        for (int j = 0; j < k; j++) {
            Order *o = &inst->orders[batches[b][j] - 1];
            locs[j].aisle    = o->aisle;
            locs[j].position = o->position;
        }
        total += combined_plus_distance(locs, k, wh);
        free(locs);
    }

    free(buf); free(batches); free(sizes); free(weights);
    return total;
}

/* ---- Particle movement ---- */

/*
 * Move perm toward target: for each position i where perm[i] != target[i],
 * with probability prob perform the swap that places target[i] at position i.
 */
static void move_toward(int *perm, const int *target, int n,
                         double prob, unsigned *s) {
    int *pos = (int*)malloc((n + 2) * sizeof(int));
    for (int i = 0; i < n; i++) pos[perm[i]] = i;

    for (int i = 0; i < n; i++) {
        if (perm[i] != target[i] && lcg_rand(s) < prob) {
            int want = target[i];
            int j    = pos[want];
            pos[perm[i]] = j;
            pos[want]    = i;
            int tmp = perm[i]; perm[i] = perm[j]; perm[j] = tmp;
        }
    }
    free(pos);
}

/* ---- Mutation operators ---- */

static void swap_mut(int *perm, int n, unsigned *s) {
    int i = lcg_rand_int(s, n), j = lcg_rand_int(s, n);
    int tmp = perm[i]; perm[i] = perm[j]; perm[j] = tmp;
}

static void shift_mut(int *perm, int n, unsigned *s) {
    int i = lcg_rand_int(s, n), j = lcg_rand_int(s, n);
    if (i == j) return;
    int val = perm[i];
    if (i < j) { for (int k = i; k < j; k++) perm[k] = perm[k + 1]; perm[j] = val; }
    else        { for (int k = i; k > j; k--) perm[k] = perm[k - 1]; perm[j] = val; }
}

static void inverse_mut(int *perm, int n, unsigned *s) {
    int i = lcg_rand_int(s, n), j = lcg_rand_int(s, n);
    if (i > j) { int t = i; i = j; j = t; }
    while (i < j) {
        int tmp = perm[i]; perm[i] = perm[j]; perm[j] = tmp;
        i++; j--;
    }
}

/* ---- Swap-based local search ---- */

static double local_search(int *perm, int n, const Instance *inst,
                             Warehouse *wh, int max_iters, unsigned *s) {
    double score = evaluate(perm, n, inst, wh);
    int *tmp = (int*)malloc(n * sizeof(int));
    for (int it = 0; it < max_iters; it++) {
        int i = lcg_rand_int(s, n), j = lcg_rand_int(s, n);
        memcpy(tmp, perm, n * sizeof(int));
        int t = tmp[i]; tmp[i] = tmp[j]; tmp[j] = t;
        double ns = evaluate(tmp, n, inst, wh);
        if (ns < score) { score = ns; memcpy(perm, tmp, n * sizeof(int)); }
    }
    free(tmp);
    return score;
}

/* ---- Public API ---- */

DEPSO* depso_create(const Instance *instance, Warehouse *warehouse,
                    const DEPSOConfig *cfg, unsigned seed) {
    DEPSO *d = (DEPSO*)malloc(sizeof(DEPSO));
    if (!d) return NULL;
    d->instance  = instance;
    d->warehouse = warehouse;
    if (cfg) {
        d->cfg = *cfg;
    } else {
        d->cfg.n_particles        = 5;
        d->cfg.n_iterations       = 200;
        d->cfg.threshold_gbest    = 0.5;
        d->cfg.mutation_rate      = 0.3;
        d->cfg.local_search_iters = 100;
        d->cfg.max_stagnation     = 20;
    }
    d->seed = seed ? seed : 1u;
    return d;
}

void depso_destroy(DEPSO *d) { free(d); }

double depso_run(DEPSO *d, int **out_perm, size_t *out_len) {
    const Instance    *inst = d->instance;
    Warehouse          *wh  = d->warehouse;
    const DEPSOConfig *cfg  = &d->cfg;
    int n  = inst->n_orders;
    int np = cfg->n_particles;
    unsigned s = d->seed;

    int   **particles    = (int**)malloc(np * sizeof(int*));
    int   **pbests       = (int**)malloc(np * sizeof(int*));
    double *pscores      = (double*)malloc(np * sizeof(double));
    double *pbest_scores = (double*)malloc(np * sizeof(double));
    for (int i = 0; i < np; i++) {
        particles[i] = (int*)malloc(n * sizeof(int));
        pbests[i]    = (int*)malloc(n * sizeof(int));
    }

    /* Particle 0 gets savings seed; rest random */
    savings_seed(particles[0], inst);
    pscores[0] = evaluate(particles[0], n, inst, wh);
    for (int i = 1; i < np; i++) {
        random_perm(particles[i], inst, &s);
        pscores[i] = evaluate(particles[i], n, inst, wh);
    }

    /* Personal bests = initial positions */
    int gbest_idx = 0;
    for (int i = 0; i < np; i++) {
        memcpy(pbests[i], particles[i], n * sizeof(int));
        pbest_scores[i] = pscores[i];
        if (pscores[i] < pscores[gbest_idx]) gbest_idx = i;
    }

    int *gbest = (int*)malloc(n * sizeof(int));
    memcpy(gbest, particles[gbest_idx], n * sizeof(int));
    double gbest_score = pscores[gbest_idx];
    double prev_gbest  = gbest_score;
    int stagnation     = 0;

    for (int iter = 0; iter < cfg->n_iterations; iter++) {
        for (int i = 0; i < np; i++) {
            if (lcg_rand(&s) < cfg->threshold_gbest)
                move_toward(particles[i], gbest,    n, 0.5, &s);
            else
                move_toward(particles[i], pbests[i], n, 0.5, &s);

            if (lcg_rand(&s) < cfg->mutation_rate) {
                int op = lcg_rand_int(&s, 3);
                if      (op == 0) swap_mut(particles[i], n, &s);
                else if (op == 1) shift_mut(particles[i], n, &s);
                else              inverse_mut(particles[i], n, &s);
            }

            pscores[i] = evaluate(particles[i], n, inst, wh);

            if (pscores[i] < pbest_scores[i]) {
                memcpy(pbests[i], particles[i], n * sizeof(int));
                pbest_scores[i] = pscores[i];
                if (pscores[i] < gbest_score) {
                    memcpy(gbest, particles[i], n * sizeof(int));
                    gbest_score = pscores[i];
                }
            }
        }

        if (gbest_score < prev_gbest - 1e-9) {
            stagnation = 0;
            prev_gbest = gbest_score;
        } else {
            stagnation++;
        }

        if (stagnation >= cfg->max_stagnation) {
            stagnation = 0;
            double ns = local_search(gbest, n, inst, wh, cfg->local_search_iters, &s);
            if (ns < gbest_score) {
                gbest_score = ns;
                prev_gbest  = ns;
                int ri = lcg_rand_int(&s, np);
                memcpy(particles[ri], gbest, n * sizeof(int));
                pscores[ri]      = gbest_score;
                memcpy(pbests[ri], gbest, n * sizeof(int));
                pbest_scores[ri] = gbest_score;
            }
        }
    }

    for (int i = 0; i < np; i++) { free(particles[i]); free(pbests[i]); }
    free(particles); free(pbests); free(pscores); free(pbest_scores);

    if (out_perm) *out_perm = gbest; else free(gbest);
    if (out_len)  *out_len  = n;
    return gbest_score;
}
