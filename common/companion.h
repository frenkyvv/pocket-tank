#ifndef PT_COMPANION_H
#define PT_COMPANION_H
#include <stdbool.h>
#include <stdint.h>
typedef struct {
    char name[33], match[35], title[32], clock[25], updated[21], extra[40];
    bool active, has_yards, has_average, demo, stale, wireless, open_view;
    float yards, average;
    int state; /* 0 waiting, 1 live, 2 final */
} companion_card_t;
void companion_set(const companion_card_t *card, int64_t now_us);
void companion_show(bool visible);
bool companion_visible(void);
const companion_card_t *companion_card(void);
bool companion_touch(float x, float y, bool down);
void companion_render(uint16_t *fb, int stride, int64_t now_us, bool chip);
#endif
