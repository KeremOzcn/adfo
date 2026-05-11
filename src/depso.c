#include "../include/depso.h"
#include "../include/routing.h"
#include <stdlib.h>
#include <string.h>
#include <float.h>

/* ---- LCG random helpers ---- */

static double lcg_rand(unsigned *s) {
    *s = *s * 1103515245u + 12345u;
    return ((double)((*s >> 16) & 0x7FFFu)) / (double)0x7FFFu;
}

static int lcg_rand_int(unsigned *s, int n) {
    *s = *s * 1103515245u + 12345u;
    return (int)(((*s >> 16) & 0x7FFFu) % (unsigned)n);
}

static int rand_vel(unsigned *s) { return lcg_rand_int(s, 3) - 1; }

/* ---- Permutation helpers ---- */

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

/* ---- Df: fraction of differing positions (paper eq.) ---- */

static double perm_df(const int *p1, const int *p2, int n) {
    int diff = 0;
    for (int i = 0; i < n; i++) if (p1[i] != p2[i]) diff++;
    return (double)diff / n;
}

/* ---- Particle movement — Appendix E ----
 * vel[h]=+1: move toward gbest if Df(p,gbest) > S_gbest * rand
 * vel[h]=-1: move toward pbest if Df(p,pbest) > rand
 * After each swap recalculate Df; refresh vel[h] randomly. */

static void move_particle(int *perm, int *vel, int n,
                           const int *gbest, const int *pbest,
                           double s_gbest, unsigned *s) {
    double df_g = perm_df(perm, gbest, n);
    double df_p = perm_df(perm, pbest, n);

    for (int h = 0; h < n; h++) {
        const int *target = NULL;
        if      (vel[h] ==  1 && df_g > s_gbest * lcg_rand(s)) target = gbest;
        else if (vel[h] == -1 && df_p > lcg_rand(s))           target = pbest;

        if (target != NULL) {
            int want = target[h], r = h;
            for (int j = 0; j < n; j++) { if (perm[j] == want) { r = j; break; } }
            if (r != h && (vel[r] != 0 || lcg_rand(s) < 0.5)) {
                int tmp = perm[h]; perm[h] = perm[r]; perm[r] = tmp;
                df_g = perm_df(perm, gbest, n);
                df_p = perm_df(perm, pbest, n);
            }
        }
        vel[h] = rand_vel(s);
    }
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
    if (i < j) { for (int k = i; k < j; k++) perm[k] = perm[k+1]; perm[j] = val; }
    else        { for (int k = i; k > j; k--) perm[k] = perm[k-1]; perm[j] = val; }
}

static void inverse_mut(int *perm, int n, unsigned *s) {
    int i = lcg_rand_int(s, n), j = lcg_rand_int(s, n);
    if (i > j) { int t = i; i = j; j = t; }
    while (i < j) { int tmp = perm[i]; perm[i] = perm[j]; perm[j] = tmp; i++; j--; }
}

/* ---- Intensity-based mutation — Appendix F ----
 * M_p = (Int_max - Int_p) / (Int_max - Int_min): low-intensity particles mutate more.
 * Operator selected by closeness Cl_p = (Td_p - Td_gbest) / (Td_max - Td_gbest). */

static void apply_mutation(int *perm, int *vel, int n,
                            double td_p, double td_gbest, double td_max,
                            double df_pbest, double df_gbest, double df_pb_gb,
                            double int_max, double int_min,
                            unsigned *s) {
    double int_p = (df_pbest + df_gbest + df_pb_gb) / 3.0;
    double m_p   = (int_max > int_min + 1e-12)
                 ? (int_max - int_p) / (int_max - int_min)
                 : 0.5;

    if (lcg_rand(s) > m_p) return;

    double cl_p = (td_max > td_gbest + 1e-12)
                ? (td_p - td_gbest) / (td_max - td_gbest)
                : 0.0;

    if      (cl_p < 0.5) swap_mut(perm, n, s);
    else if (cl_p < 0.8) shift_mut(perm, n, s);
    else                  inverse_mut(perm, n, s);

    vel[lcg_rand_int(s, n)] = rand_vel(s);
    vel[lcg_rand_int(s, n)] = rand_vel(s);
}

/* ---- Adaptive stagnation threshold — Section 5.2.5
 * S_stag = round(1 + S_maxStag * (It_max - It_cur) / It_max): decreases over time. */

static int adaptive_stag_threshold(int s_max_stag, int it_max, int it_cur) {
    double v = 1.0 + s_max_stag * (double)(it_max - it_cur) / (double)it_max;
    return (int)(v + 0.5);
}

/* ---- Local search on Gbest — Appendix G: first-improvement swap ---- */

static double local_search_gbest(int *gbest, int n, const Instance *inst,
                                  Warehouse *wh, int max_iters, unsigned *s) {
    double score = evaluate(gbest, n, inst, wh);
    int *tmp = (int*)malloc(n * sizeof(int));
    for (int it = 0; it < max_iters; it++) {
        int i = lcg_rand_int(s, n), j = lcg_rand_int(s, n);
        memcpy(tmp, gbest, n * sizeof(int));
        int t = tmp[i]; tmp[i] = tmp[j]; tmp[j] = t;
        double ns = evaluate(tmp, n, inst, wh);
        if (ns < score - 1e-9) {
            score = ns;
            memcpy(gbest, tmp, n * sizeof(int));
            break;
        }
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
        d->cfg.local_search_iters = 50;
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
    int   **vels         = (int**)malloc(np * sizeof(int*));
    double *pscores      = (double*)malloc(np * sizeof(double));
    double *pbest_scores = (double*)malloc(np * sizeof(double));
    for (int i = 0; i < np; i++) {
        particles[i] = (int*)malloc(n * sizeof(int));
        pbests[i]    = (int*)malloc(n * sizeof(int));
        vels[i]      = (int*)malloc(n * sizeof(int));
    }

    /* Particle 0: savings-order seed; rest: random */
    savings_seed(particles[0], inst);
    pscores[0] = evaluate(particles[0], n, inst, wh);
    for (int i = 1; i < np; i++) {
        random_perm(particles[i], inst, &s);
        pscores[i] = evaluate(particles[i], n, inst, wh);
    }

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

    /* Initialize velocity vectors randomly */
    for (int i = 0; i < np; i++)
        for (int h = 0; h < n; h++)
            vels[i][h] = rand_vel(&s);

    int stag_gbest = 0;

    for (int iter = 0; iter < cfg->n_iterations; iter++) {

        /* Move all particles and update pbest / gbest */
        double td_max = -DBL_MAX;
        for (int i = 0; i < np; i++) {
            move_particle(particles[i], vels[i], n,
                          gbest, pbests[i], cfg->threshold_gbest, &s);
            pscores[i] = evaluate(particles[i], n, inst, wh);

            if (pscores[i] < pbest_scores[i]) {
                memcpy(pbests[i], particles[i], n * sizeof(int));
                pbest_scores[i] = pscores[i];
                if (pscores[i] < gbest_score) {
                    memcpy(gbest, particles[i], n * sizeof(int));
                    gbest_score = pscores[i];
                }
            }
            if (pscores[i] > td_max) td_max = pscores[i];
        }

        /* Compute intensity bounds for mutation */
        double int_min = DBL_MAX, int_max = -DBL_MAX;
        for (int i = 0; i < np; i++) {
            double df_pb = perm_df(particles[i], pbests[i], n);
            double df_gb = perm_df(particles[i], gbest,    n);
            double df_pg = perm_df(pbests[i],    gbest,    n);
            double ip    = (df_pb + df_gb + df_pg) / 3.0;
            if (ip < int_min) int_min = ip;
            if (ip > int_max) int_max = ip;
        }

        /* Apply mutation, re-evaluate, update pbest / gbest */
        for (int i = 0; i < np; i++) {
            double df_pb = perm_df(particles[i], pbests[i], n);
            double df_gb = perm_df(particles[i], gbest,    n);
            double df_pg = perm_df(pbests[i],    gbest,    n);
            apply_mutation(particles[i], vels[i], n,
                           pscores[i], gbest_score, td_max,
                           df_pb, df_gb, df_pg,
                           int_max, int_min, &s);

            double ns = evaluate(particles[i], n, inst, wh);
            pscores[i] = ns;
            if (ns < pbest_scores[i]) {
                memcpy(pbests[i], particles[i], n * sizeof(int));
                pbest_scores[i] = ns;
                if (ns < gbest_score) {
                    memcpy(gbest, particles[i], n * sizeof(int));
                    gbest_score = ns;
                }
            }
        }

        /* Track gbest stagnation */
        if (gbest_score < prev_gbest - 1e-9) {
            stag_gbest = 0;
            prev_gbest = gbest_score;
        } else {
            stag_gbest++;
        }

        /* Adaptive local search on Gbest */
        int s_stag = adaptive_stag_threshold(cfg->max_stagnation,
                                              cfg->n_iterations, iter);
        if ((double)stag_gbest > (double)s_stag * lcg_rand(&s)) {
            int *gbcopy = (int*)malloc(n * sizeof(int));
            memcpy(gbcopy, gbest, n * sizeof(int));
            double ns = local_search_gbest(gbcopy, n, inst, wh,
                                            cfg->local_search_iters, &s);
            if (ns < gbest_score - 1e-9) {
                gbest_score = ns;
                prev_gbest  = ns;
                memcpy(gbest, gbcopy, n * sizeof(int));
                stag_gbest  = 0;
                /* Seed one random particle on improved gbest */
                int ri = lcg_rand_int(&s, np);
                memcpy(particles[ri], gbest, n * sizeof(int));
                pscores[ri]      = gbest_score;
                memcpy(pbests[ri], gbest, n * sizeof(int));
                pbest_scores[ri] = gbest_score;
            }
            free(gbcopy);
        }
    }

    for (int i = 0; i < np; i++) {
        free(particles[i]); free(pbests[i]); free(vels[i]);
    }
    free(particles); free(pbests); free(vels);
    free(pscores); free(pbest_scores);

    if (out_perm) *out_perm = gbest; else free(gbest);
    if (out_len)  *out_len  = n;
    return gbest_score;
}
