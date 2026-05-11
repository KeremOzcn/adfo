#ifndef ROUTING_H
#define ROUTING_H

#include <stddef.h>
#include "warehouse.h"

typedef struct ItemLocation {
	int aisle;
	int position;
} ItemLocation;

double combined_plus_distance(const ItemLocation *item_locations, size_t n_items, Warehouse *wh);

#endif // ROUTING_H
