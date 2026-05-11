#ifndef RBRS_AE_ALGORITHM_H
#define RBRS_AE_ALGORITHM_H

#include <stddef.h>
#include "instances.h"
#include "warehouse.h"

typedef struct RBRS_AE {
    const Instance *inst;
    Warehouse      *wh;
    int             max_iterations;
    int             stagnation_limit;
} RBRS_AE;

RBRS_AE* rbrs_create(const Instance *inst, Warehouse *wh,
                     int max_iters, int stagnation_limit);
void     rbrs_destroy(RBRS_AE *r);
double   rbrs_run(RBRS_AE *r, int **out_perm, size_t *out_len);

#endif /* RBRS_AE_ALGORITHM_H */
