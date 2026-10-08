#ifndef PT_COMPANION_H
#define PT_COMPANION_H
#include <stdbool.h>
#include <stdint.h>
typedef struct {
    char name[33], match[35], title[32], clock[25], updated[21], extra[40];
    bool active, has_yards, has_average, demo, stale, wireless, open_view;
    float yards, average;
    char notice_id[33], notice_source[17], notice_title[33], notice_message[241], notice_time[9];
    int notice_seconds, notice_priority;
    bool notice_demo;
    bool voice_ready;
    char voice_reply_id[33];
    char local_time[6];
    char weather_temp[9],weather_desc[26],weather_feels[9],weather_humidity[6],weather_updated[12];
    char eth_usd[20],eth_mxn[20],eth_updated[12];
    bool weather_stale,eth_stale;
    char ux_day[11],ux_updated[6],ux_total[8],ux_admissions[8],ux_voluntary[8],ux_nursing_delay[8],ux_ic_delay[8];
    char ux_doctors[721],ux_nurses[721];
    bool ux_stale;
    int state; /* 0 waiting, 1 live, 2 final */
} companion_card_t;
void companion_set(const companion_card_t *card, int64_t now_us);
void companion_show(bool visible);
void companion_voice_set(int state); /* 0 idle, 1 recording, 2 sending, 3 waiting, 4 unavailable */
int companion_voice_state(void);
int companion_voice_take_action(void); /* 1 record, 2 send, 3 cancel */
const char *companion_notice_done(void);
bool companion_notice_active(void);
bool companion_visible(void);
const companion_card_t *companion_card(void);
bool companion_touch(float x, float y, bool down);
void companion_render(uint16_t *fb, int stride, int64_t now_us, bool chip);
#endif
