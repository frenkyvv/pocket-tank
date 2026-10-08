#include "companion.h"
#include "render.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
static companion_card_t card;
static bool visible, pressed, captured;
static int64_t received;
void companion_set(const companion_card_t *value, int64_t now) { card = *value; received = now; }
void companion_show(bool value) { visible = value; }
bool companion_visible(void) { return visible; }
const companion_card_t *companion_card(void) { return &card; }
bool companion_touch(float x, float y, bool down) {
    if (down && !pressed) {
        captured = visible || (x >= PAGE_X + 350 && y >= PAGE_Y && y < PAGE_Y + 42);
        if (captured && x >= PAGE_X + 350 && y < PAGE_Y + 42) visible = !visible;
    }
    bool consume = captured || visible;
    pressed = down;
    if (!down) captured = false;
    return consume;
}
static void text(uint16_t *fb, int s, int x, int y, int scale, uint32_t rgb, const char *str) {
    render_text(fb,s,x,y,scale,rgb,str);
}
void companion_render(uint16_t *fb, int s, int64_t now, bool chip) {
    const uint32_t white=0xf6f8fa, gray=0xaeb7c1, green=0x35dfa0, red=0xff667b;
    if (!visible) {
        if (chip) render_button(fb,s,350,4,94,32,0x101820,0x405260,"BOB",2);
        return;
    }
    render_rect(fb,s,-PAGE_X,-PAGE_Y,TANK_W,TANK_H,0x0b0e12);
    render_button(fb,s,350,4,94,32,0x182c34,0x405260,"PECERA",2);
    text(fb,s,18,14,2,green,"BOB / NFL");
    if (!card.active) {
        text(fb,s,24,110,2,white,"ESPERANDO SEGUIMIENTO");
        text(fb,s,24,160,2,gray,"PIDE A BOB: SIGUE A...");
        text(fb,s,24,210,2,gray,"LA PECERA SIGUE ACTIVA");
        if (received && now-received > 30000000) text(fb,s,24,270,2,red,"USB SIN DATOS");
        else if(card.stale) text(fb,s,24,270,2,red,"BOB SIN ACTUALIZAR");
        return;
    }
    bool stale = card.stale || !received || now-received > 30000000;
    const char *state=card.demo ? "DEMO / DATOS DE PRUEBA" : stale ? "DATOS SIN ACTUALIZAR" : card.state==1 ? "EN VIVO" : card.state==2 ? "FINAL" : "EN ESPERA";
    text(fb,s,18,52,2,stale?red:gray,state);
    text(fb,s,18,86,2,white,card.name);
    text(fb,s,18,118,2,gray,card.match);
    text(fb,s,18,151,2,gray,card.clock);
    text(fb,s,18,187,2,gray,card.title);
    char buf[64];
    if(card.has_yards) snprintf(buf,sizeof buf,"%.0f YD",card.yards);
    else snprintf(buf,sizeof buf,"SIN DATO");
    text(fb,s,18,220,4,white,buf);
    if(card.has_average && card.average>0 && isfinite(card.average)) {
        snprintf(buf,sizeof buf,"PROM. %.1f YD",card.average);
        text(fb,s,240,224,2,gray,buf);
        if(card.has_yards) {
            float ratio=card.yards/card.average;
            snprintf(buf,sizeof buf,"%.0f%% DEL PROMEDIO",ratio*100);
            text(fb,s,18,263,2,ratio>=1?green:red,buf);
            render_rect(fb,s,18,292,412,16,0x30363e);
            int width=(int)(412*fminf(1,fmaxf(0,ratio)));
            if(width) render_rect(fb,s,18,292,width,16,ratio>=1?green:red);
        }
    } else text(fb,s,18,270,2,gray,"PROMEDIO NO DISPONIBLE");
    text(fb,s,18,326,1,gray,card.extra);
    snprintf(buf,sizeof buf,"BOB %s / USB",card.updated);
    text(fb,s,18,348,1,gray,buf);
}
