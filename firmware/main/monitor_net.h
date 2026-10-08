#pragma once
#include "companion.h"
#include <stddef.h>
bool monitor_decode(const char *json, companion_card_t *card);
bool monitor_key_set(const char *key);
void monitor_net_start(void);
void monitor_net_poll(void);
void monitor_net_status(void);

bool monitor_voice_upload(const unsigned char *wav, size_t length, const char *id);
