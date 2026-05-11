#ifndef BASELINES_H
#define BASELINES_H

#include "instances.h"
#include "warehouse.h"

double sop_distance(const Instance *inst, Warehouse *wh);
double fcfs_distance(const Instance *inst, Warehouse *wh);

#endif // BASELINES_H
