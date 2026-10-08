#include "voice_port.h"
#include "audio_port.h"
#include "monitor_net.h"
#include "companion.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/idf_additions.h"
#include "freertos/queue.h"
#include "esp_heap_caps.h"
#include "esp_random.h"
#include "esp_log.h"
#include <string.h>
#include <stdio.h>
#include <stdint.h>
static QueueHandle_t progress;
static volatile bool stop_record, cancel_record, working;
static char request_id[33];
static void state(int value) {if(progress)xQueueOverwrite(progress,&value);}
static void put16(unsigned char *p,uint16_t n) {p[0]=n;p[1]=n>>8;}
static void put32(unsigned char *p,uint32_t n) {p[0]=n;p[1]=n>>8;p[2]=n>>16;p[3]=n>>24;}
static void record(void *arg) {
    (void)arg;
    unsigned char *wav=heap_caps_malloc(44+192000*2,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT);
    if(!wav){state(4);goto finish;}
    size_t count=audio_port_record((int16_t *)(wav+44),192000,&stop_record);
    if(cancel_record){heap_caps_free(wav);goto finish;}
    if(count<4000){ESP_LOGW("voice","recording too short or microphone unavailable");heap_caps_free(wav);state(5);goto finish;}
    int peak=0;uint64_t energy=0;int16_t *pcm=(int16_t *)(wav+44);
    for(size_t i=0;i<count;i++){int v=pcm[i];int a=v<0?-v:v;if(a>peak)peak=a;energy+=(int64_t)v*v;}
    ESP_LOGI("voice","recorded %u samples, peak %d, mean-square %llu",(unsigned)count,peak,(unsigned long long)(energy/count));
    if(peak<50){heap_caps_free(wav);state(5);goto finish;}
    memset(wav,0,44);memcpy(wav,"RIFF",4);put32(wav+4,36+count*2);memcpy(wav+8,"WAVEfmt ",8);
    put32(wav+16,16);put16(wav+20,1);put16(wav+22,1);put32(wav+24,16000);put32(wav+28,32000);put16(wav+32,2);put16(wav+34,16);memcpy(wav+36,"data",4);put32(wav+40,count*2);
    state(2);bool ok=monitor_voice_upload(wav,44+count*2,request_id);heap_caps_free(wav);
    if(!cancel_record)state(ok?3:4);
finish:
    working=false;vTaskDeleteWithCaps(NULL);
}
void voice_port_start(void) {
    if(working)return;
    if(!progress)progress=xQueueCreate(1,sizeof(int));
    if(!progress){companion_voice_set(4);return;}
    int ignored;while(xQueueReceive(progress,&ignored,0)==pdTRUE){}
    for(int i=0;i<4;i++)snprintf(request_id+i*8,9,"%08lx",(unsigned long)esp_random());
    stop_record=false;cancel_record=false;working=true;companion_voice_set(1);
    if(xTaskCreateWithCaps(record,"susi-voice",12288,NULL,4,NULL,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT)!=pdPASS){working=false;companion_voice_set(4);}
}
void voice_port_poll(void) {
    int action=companion_voice_take_action();
    if(action==1)voice_port_start();
    else if(action==2){stop_record=true;companion_voice_set(2);}
    else if(action==3){stop_record=true;cancel_record=true;}
    int value;if(progress && xQueueReceive(progress,&value,0)==pdTRUE && !cancel_record)companion_voice_set(value);
}
void voice_port_reply(const char *id) {if(id && id[0] && !strcmp(id,request_id))companion_voice_set(0);}
