#pragma once
#include "companion.h"
bool monitor_decode(const char *json, companion_card_t *card);
bool monitor_key_set(const char *key);
void monitor_net_start(void);
void monitor_net_poll(void);
void monitor_net_status(void);
