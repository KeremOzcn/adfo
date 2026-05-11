#ifndef DEPSO_H
#define DEPSO_H

#include <stddef.h>
#include "instances.h"
#include "warehouse.h"

typedef struct DEPSOConfig {
    int    n_particles;
    int    n_iterations;
    double threshold_gbest;    /* default 0.5  — prob. of moving toward gbest */
    double mutation_rate;      /* default 0.3 */
    int    local_search_iters; /* default 100 */
    int    max_stagnation;     /* default 20 */
} DEPSOConfig;

typedef struct DEPSO {
    const Instance *instance;
    Warehouse      *warehouse;
    DEPSOConfig     cfg;
    unsigned        seed;
} DEPSO;

DEPSO* depso_create(const Instance *instance, Warehouse *warehouse,
                    const DEPSOConfig *cfg, unsigned seed);
void   depso_destroy(DEPSO *d);
double depso_run(DEPSO *d, int **out_perm, size_t *out_len);

#endif /* DEPSO_H */
