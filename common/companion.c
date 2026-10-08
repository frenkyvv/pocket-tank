#include "companion.h"
#include "render.h"
#include <stdio.h>
#include <string.h>
#include <math.h>
static companion_card_t card;
static bool visible, pressed, captured;
static int panel_page; /* 0 home, 1 tracking, 2 notices, 3 weather, 4 ETH */
static int64_t received, notice_started;
static companion_card_t notice;
static bool notice_up;
static char notice_seen[33], notice_done[33];
static int voice_state, voice_action;
static int64_t voice_started;
void companion_voice_set(int state) {voice_state=state;voice_started=0;}
int companion_voice_state(void) {return voice_state;}
int companion_voice_take_action(void) {int action=voice_action;voice_action=0;return action;}
const char *companion_notice_done(void) {return notice_done;}
bool companion_notice_active(void) {return notice_up;}
static void dismiss_notice(void) {snprintf(notice_done,sizeof notice_done,"%s",notice.notice_id);notice_up=false;}

void companion_set(const companion_card_t *value, int64_t now) { card = *value; received = now;
    if(value->notice_id[0] && strcmp(value->notice_id,notice_seen)) {
        notice=*value;snprintf(notice_seen,sizeof notice_seen,"%s",value->notice_id);
        notice_up=true;notice_started=0;
    } }
void companion_show(bool value) { visible = value; panel_page=0; }
bool companion_visible(void) { return visible || notice_up || voice_state; }
const companion_card_t *companion_card(void) { return &card; }
bool companion_touch(float x, float y, bool down) {
    if(voice_state) {
        if(down && !pressed) {
            if(x>=PAGE_X+350 && y<PAGE_Y+42) {voice_action=3;voice_state=0;visible=false;}
            else if(voice_state==1 && y>=PAGE_Y+308 && y<PAGE_Y+360)voice_action=2;
            else if(voice_state>=4 && y>=PAGE_Y+308)voice_state=0;
        }
        pressed=down;captured=down;return true;
    }
    if(visible && panel_page==0 && !notice_up && down && !pressed && x>=PAGE_X+24 && x<PAGE_X+424 && y>=PAGE_Y+176 && y<PAGE_Y+220) {
        if(card.voice_ready && received && received>0)voice_action=1;
        else companion_voice_set(4);
        pressed=true;captured=true;return true;
    }
    if (notice_up) {
        if(down && !pressed) {
            if(x>=PAGE_X+350 && y<PAGE_Y+42) {dismiss_notice();visible=false;}
            else if(y>=PAGE_Y+308 && y<PAGE_Y+360) dismiss_notice();
        }
        pressed=down;captured=down;return true;
    }
    if (down && !pressed) {
        float dx=x-(PAGE_X+414), dy=y-(PAGE_Y+334);
        bool launcher=dx*dx+dy*dy<=24*24;
        captured=visible || launcher;
        if(!visible && launcher) {visible=true;panel_page=0;}
        else if(visible && x>=PAGE_X+350 && y<PAGE_Y+42) {
            if(panel_page)panel_page=0;else visible=false;
        } else if(visible && panel_page==0 && x>=PAGE_X+24 && x<PAGE_X+424) {
            if(x>=PAGE_X+240 && y>=PAGE_Y+50 && y<PAGE_Y+160)panel_page=3;
            else if(y>=PAGE_Y+232 && y<PAGE_Y+276)panel_page=x<PAGE_X+224?1:2;
            else if(y>=PAGE_Y+288 && y<PAGE_Y+344)panel_page=4;
        }
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
    if(voice_state) {
        if(!voice_started)voice_started=now;
        if(voice_state==3 && now-voice_started>450000000LL)voice_state=4;
        render_rect(fb,s,-PAGE_X,-PAGE_Y,TANK_W,TANK_H,0x0b111c);
        text(fb,s,18,14,2,green,"HABLAR CON SUSI");
        render_button(fb,s,350,4,94,32,0x182c34,0x405260,"PECERA",2);
        text(fb,s,24,100,3,white,voice_state==1?"TE ESCUCHO":voice_state==2?"ENVIANDO...":voice_state==3?"SUSI RESPONDE":voice_state==5?"NO ESCUCHE VOZ":"SIN CONEXION");
        text(fb,s,24,165,2,gray,voice_state==1?"DI TU PREGUNTA Y TOCA ENVIAR":voice_state==2?"TU AUDIO VIAJA POR WIFI":voice_state==3?"SUSI CONVIERTE TU VOZ A TEXTO":voice_state==5?"ACERCATE AL MICROFONO":"REVISA WIFI Y LA MAC");
        text(fb,s,24,205,2,gray,voice_state==1?"MAXIMO 12 SEGUNDOS":voice_state==3?"LA PECERA SIGUE ACTIVA":"PUEDES VOLVER A LA PECERA");
        if(voice_state==1) {char elapsed[40];snprintf(elapsed,sizeof elapsed,"GRABANDO %lld / 12 S",(now-voice_started)/1000000);text(fb,s,24,250,2,green,elapsed);}
        if(voice_state==1 || voice_state>=4)render_button(fb,s,24,318,400,38,0x183b32,0x35dfa0,voice_state==1?"ENVIAR":"LISTO",2);
        return;
    }
    if(notice_up) {
        if(!notice_started)notice_started=now;
        int seconds=notice.notice_seconds; if(seconds<5||seconds>60)seconds=20;
        if(now-notice_started>seconds*1000000LL) dismiss_notice();
    }
    if(notice_up) {
        render_rect(fb,s,-PAGE_X,-PAGE_Y,TANK_W,TANK_H,0x0b111c);
        text(fb,s,18,14,2,green,notice.notice_source[0]?notice.notice_source:"SUSI");
        render_button(fb,s,350,4,94,32,0x182c34,0x405260,"PECERA",2);
        text(fb,s,18,52,2,notice.notice_priority>=2?red:gray,notice.notice_demo?"DEMO / AVISO DE PRUEBA":notice.notice_priority>=2?"AVISO PRIORITARIO":"NUEVO AVISO");
        text(fb,s,18,86,2,white,notice.notice_title);
        const char *cursor=notice.notice_message;
        for(int row=0;row<7 && *cursor;row++) {
            while(*cursor==' ')cursor++;
            int n=0;while(cursor[n] && cursor[n]!='\n' && n<34)n++;
            if(n==34 && cursor[n] && cursor[n]!=' ') {int cut=n;while(cut>0 && cursor[cut]!=' ')cut--;if(cut>0)n=cut;}
            char line[35];memcpy(line,cursor,n);line[n]=0;
            if(row==6 && cursor[n] && n>=3)memcpy(line+n-3,"...",3);
            text(fb,s,18,122+row*23,2,white,line);cursor+=n;if(*cursor=='\n'||*cursor==' ')cursor++;
        }
        text(fb,s,18,290,1,gray,notice.notice_time);
        render_button(fb,s,24,318,400,38,0x183b32,0x35dfa0,"LISTO",2);
        return;
    }
    if (!visible) {
        if (chip) {
            for(int dy=-23;dy<=23;dy++) {int half=(int)sqrtf(23*23-dy*dy);render_rect(fb,s,414-half,334+dy,half*2+1,1,0x183b32);}
            /* Three dots: a quiet launcher without a text label. */
            for(int i=0;i<3;i++)render_rect(fb,s,403+i*9,332,4,4,green);
        }
        return;
    }
    render_rect(fb,s,-PAGE_X,-PAGE_Y,TANK_W,TANK_H,0x0b111c);
    render_button(fb,s,350,4,94,32,0x182c34,0x405260,panel_page?"VOLVER":"PECERA",2);
    if(panel_page==0) {
        text(fb,s,24,18,2,green,"MI COMPANERO");
        text(fb,s,24,68,4,white,card.local_time[0]?card.local_time:"--:--");
        text(fb,s,24,125,2,gray,"MONTERREY");
        render_rect(fb,s,240,55,184,104,0x182c34);
        text(fb,s,254,65,1,green,"CLIMA / MONTERREY");
        text(fb,s,254,88,3,white,card.weather_temp[0]?card.weather_temp:"-- C");
        text(fb,s,254,132,1,card.weather_stale || now-received>30000000?red:gray,card.weather_stale || now-received>30000000?"SIN ACTUALIZAR":"TOCA PARA VER MAS");
        text(fb,s,24,149,1,received && now-received<30000000?green:red,received && now-received<30000000?"CONECTADO POR WIFI":"ESPERANDO CONEXION");
        render_button(fb,s,24,176,400,44,0x183b32,green,"HABLAR CON SUSI",2);
        render_button(fb,s,24,232,194,44,0x182c34,0x405260,"SEGUIMIENTO",2);
        render_button(fb,s,230,232,194,44,0x182c34,0x405260,"AVISOS",2);
        render_rect(fb,s,24,288,400,56,0x182c34);
        text(fb,s,36,298,2,green,"ETH");
        text(fb,s,102,298,2,white,card.eth_usd[0]?card.eth_usd:"SIN DATOS");
        text(fb,s,330,301,1,gray,"USD / MAS");
        char stamp[40];snprintf(stamp,sizeof stamp,"%s %s",card.eth_stale || now-received>30000000?"SIN ACTUALIZAR":"ACTUALIZADO",card.eth_updated);
        text(fb,s,36,326,1,card.eth_stale || now-received>30000000?red:gray,stamp);
        return;
    }
    if(panel_page==3 || panel_page==4) {
        bool weather=panel_page==3;
        bool stale=(weather?card.weather_stale:card.eth_stale) || !received || now-received>30000000;
        text(fb,s,24,18,2,green,weather?"CLIMA / MONTERREY":"ETH / ETHEREUM");
        text(fb,s,24,66,1,stale?red:green,stale?"DATOS SIN ACTUALIZAR":"DATOS ACTUALIZADOS");
        text(fb,s,24,104,4,white,weather?(card.weather_temp[0]?card.weather_temp:"-- C"):(card.eth_usd[0]?card.eth_usd:"SIN DATOS"));
        char detail[64];
        if(weather) {
            text(fb,s,24,161,2,white,card.weather_desc);
            snprintf(detail,sizeof detail,"SENSACION %s",card.weather_feels);text(fb,s,24,208,2,gray,detail);
            snprintf(detail,sizeof detail,"HUMEDAD %s",card.weather_humidity);text(fb,s,24,244,2,gray,detail);
        } else {
            text(fb,s,24,161,2,gray,"USD POR 1 ETH");
            text(fb,s,24,208,3,white,card.eth_mxn[0]?card.eth_mxn:"SIN DATOS");
            text(fb,s,24,252,2,gray,"MXN POR 1 ETH");
        }
        snprintf(detail,sizeof detail,"%s %s",weather?"CLIMA":"CONSULTA",weather?card.weather_updated:card.eth_updated);
        text(fb,s,24,301,1,gray,detail);
        text(fb,s,24,331,1,gray,weather?"FUENTE: OPEN-METEO / MODELO":"FUENTE: COINBASE / PRECIO SPOT");
        return;
    }
    if(panel_page==2) {
        text(fb,s,24,18,2,green,"AVISOS DE SUSI");
        text(fb,s,24,100,2,white,notice.notice_id[0]?notice.notice_title:"TODO TRANQUILO");
        const char *cursor=notice.notice_message;
        for(int row=0;row<7 && *cursor;row++) {
            int n=0;while(cursor[n] && cursor[n]!='\n' && n<33)n++;
            if(n==33 && cursor[n]) {int cut=n;while(cut>0 && cursor[cut]!=' ')cut--;if(cut)n=cut;}
            char line[34];memcpy(line,cursor,n);line[n]=0;text(fb,s,24,144+row*24,2,white,line);
            cursor+=n;while(*cursor==' '||*cursor=='\n')cursor++;
        }
        if(!notice.notice_id[0])text(fb,s,24,148,2,gray,"TUS AVISOS APARECERAN AQUI");
        return;
    }
    text(fb,s,18,14,2,green,"BOB / NFL");
    if (!card.active) {
        text(fb,s,24,110,2,white,"ESPERANDO SEGUIMIENTO");
        text(fb,s,24,160,2,gray,"PIDE A BOB: SIGUE A...");
        text(fb,s,24,210,2,gray,"LA PECERA SIGUE ACTIVA");
        if (received && now-received > 30000000) text(fb,s,24,270,2,red,"ENLACE SIN DATOS");
        else if(card.stale) text(fb,s,24,270,2,red,"BOB SIN ACTUALIZAR");
        if(received && now-received<30000000) text(fb,s,18,348,1,green,card.wireless?"ENLACE WIFI ACTIVO":"ENLACE USB ACTIVO");
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
    snprintf(buf,sizeof buf,"BOB %s / %s",card.updated,card.wireless?"WIFI":"USB");
    text(fb,s,18,348,1,gray,buf);
}
