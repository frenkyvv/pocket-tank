#include "monitor_net.h"
#include "update.h"
#include "cJSON.h"
#include "nvs.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_http_client.h"
#include "voice_port.h"
#include "mbedtls/md.h"
#include "lwip/sockets.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/idf_additions.h"
#include "esp_heap_caps.h"
#include "freertos/queue.h"
#include <string.h>
#include <math.h>
#include <ctype.h>
#include <errno.h>
#include <stdio.h>
#include <unistd.h>
static const char *TAG="monitor-net";
static char key[65];
static QueueHandle_t pending, completed;
static unsigned received;
static uint32_t voice_host;
bool net_port_monitor_start(void);
bool monitor_decode(const char *json, companion_card_t *c) {
    cJSON *root=cJSON_Parse(json);
    if(!cJSON_IsObject(root)||!cJSON_IsBool(cJSON_GetObjectItemCaseSensitive(root,"active"))) {cJSON_Delete(root);return false;}
    memset(c,0,sizeof *c);
#define STR(field) do {cJSON *v=cJSON_GetObjectItemCaseSensitive(root,#field);if(cJSON_IsString(v)) snprintf(c->field,sizeof c->field,"%s",v->valuestring);} while(0)
    STR(local_time);STR(name);STR(match);STR(title);STR(clock);STR(updated);STR(extra);
    STR(voice_reply_id);STR(notice_id);STR(notice_source);STR(notice_title);STR(notice_message);STR(notice_time);
#undef STR
    if(c->notice_id[0]) {
        if(strlen(c->notice_id)!=32){cJSON_Delete(root);return false;}
        for(int i=0;i<32;i++)if(!isxdigit((unsigned char)c->notice_id[i])){cJSON_Delete(root);return false;}
    }
    cJSON *duration=cJSON_GetObjectItemCaseSensitive(root,"notice_seconds");c->notice_seconds=cJSON_IsNumber(duration)?duration->valueint:20;
    duration=cJSON_GetObjectItemCaseSensitive(root,"notice_priority");c->notice_priority=cJSON_IsNumber(duration)?duration->valueint:1;
    c->notice_demo=cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(root,"notice_demo"));
    c->voice_ready=cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(root,"voice_ready"));
    c->open_view=cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(root,"show"));
    c->active=cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(root,"active"));
    c->demo=cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(root,"demo"));
    c->stale=cJSON_IsTrue(cJSON_GetObjectItemCaseSensitive(root,"stale"));
    cJSON *v=cJSON_GetObjectItemCaseSensitive(root,"yards");c->has_yards=cJSON_IsNumber(v)&&isfinite(v->valuedouble);if(c->has_yards)c->yards=v->valuedouble;
    v=cJSON_GetObjectItemCaseSensitive(root,"average");c->has_average=cJSON_IsNumber(v)&&isfinite(v->valuedouble);if(c->has_average)c->average=v->valuedouble;
    v=cJSON_GetObjectItemCaseSensitive(root,"state");if(cJSON_IsString(v))c->state=!strcmp(v->valuestring,"in")?1:!strcmp(v->valuestring,"post")?2:0;
    cJSON_Delete(root);return true;
}
bool monitor_key_set(const char *value) {
    if(strlen(value)!=64)return false;
    for(int i=0;i<64;i++)if(!isxdigit((unsigned char)value[i]))return false;
    nvs_handle_t h;if(nvs_open("monitor",NVS_READWRITE,&h)!=ESP_OK)return false;
    bool ok=nvs_set_str(h,"key",value)==ESP_OK&&nvs_commit(h)==ESP_OK;nvs_close(h);return ok;
}
static void worker(void *arg) {
    int fd=socket(AF_INET,SOCK_DGRAM,IPPROTO_UDP);
    struct sockaddr_in address={.sin_family=AF_INET,.sin_port=htons(19432),.sin_addr.s_addr=htonl(INADDR_ANY)};
    if(fd<0||bind(fd,(struct sockaddr *)&address,sizeof address)<0){ESP_LOGE(TAG,"UDP unavailable");if(fd>=0)close(fd);vTaskDeleteWithCaps(NULL);return;}
    char buf[1536];double last_seq=0;
    ESP_LOGI(TAG,"WiFi receiver ready UDP 19432");
    for(;;){
        struct sockaddr_in peer;socklen_t size=sizeof peer;
        int n=recvfrom(fd,buf,sizeof buf-1,0,(struct sockaddr *)&peer,&size);if(n<=0)continue;buf[n]=0;
        cJSON *packet=cJSON_Parse(buf);
        cJSON *body=cJSON_GetObjectItemCaseSensitive(packet,"body"),*sig=cJSON_GetObjectItemCaseSensitive(packet,"sig");
        if(!cJSON_IsString(body)||!cJSON_IsString(sig)||strlen(sig->valuestring)!=64){cJSON_Delete(packet);continue;}
        unsigned char digest[32];char hex[65];
        int result=mbedtls_md_hmac(mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),(unsigned char *)key,64,(unsigned char *)body->valuestring,strlen(body->valuestring),digest);
        if(result){cJSON_Delete(packet);continue;}
        for(int i=0;i<32;i++)snprintf(hex+i*2,3,"%02x",digest[i]);
        unsigned diff=0;for(int i=0;i<64;i++)diff|=(unsigned char)hex[i]^(unsigned char)sig->valuestring[i];
        if(result||diff){cJSON_Delete(packet);continue;}
        cJSON *content=cJSON_Parse(body->valuestring);cJSON *seq=cJSON_GetObjectItemCaseSensitive(content,"seq");
        companion_card_t card;
        if(cJSON_IsNumber(seq)&&isfinite(seq->valuedouble)&&seq->valuedouble>last_seq&&monitor_decode(body->valuestring,&card)) {
            last_seq=seq->valuedouble;voice_host=peer.sin_addr.s_addr;card.wireless=true;xQueueOverwrite(pending,&card);received++;
            char done[33]={0};xQueuePeek(completed,done,0);
            char ack[144];int len=snprintf(ack,sizeof ack,"{\"ok\":true,\"seq\":%.0f,\"done\":\"%s\"}",last_seq,done);
            sendto(fd,ack,len,0,(struct sockaddr *)&peer,size);
            if(received==1)ESP_LOGI(TAG,"first authenticated WiFi card received");
        }
        cJSON_Delete(content);cJSON_Delete(packet);
    }
}
void monitor_net_start(void) {
    nvs_handle_t h;size_t n=sizeof key;
    if(nvs_open("monitor",NVS_READONLY,&h)!=ESP_OK)return;
    esp_err_t e=nvs_get_str(h,"key",key,&n);nvs_close(h);if(e!=ESP_OK||strlen(key)!=64)return;
    pending=xQueueCreate(1,sizeof(companion_card_t));completed=xQueueCreate(1,33);
    if(!pending||!completed||!net_port_monitor_start()){ESP_LOGW(TAG,"WiFi monitor not started; USB still available");return;}
    if(xTaskCreateWithCaps(worker,"monitor-rx",6144,NULL,3,NULL,MALLOC_CAP_SPIRAM|MALLOC_CAP_8BIT)!=pdPASS)ESP_LOGE(TAG,"WiFi receiver task allocation failed");
}
void monitor_net_poll(void) {char done[33];snprintf(done,sizeof done,"%s",companion_notice_done());if(completed)xQueueOverwrite(completed,done);companion_card_t c;if(pending&&xQueueReceive(pending,&c,0)==pdTRUE){voice_port_reply(c.voice_reply_id);companion_set(&c,esp_timer_get_time());if(c.open_view)companion_show(true);}}
void monitor_net_status(void) {ESP_LOGI(TAG,"WiFi cards received: %u",received);}

bool monitor_voice_upload(const unsigned char *wav,size_t length,const char *id) {
    uint32_t host=voice_host;if(!host || !key[0])return false;
    char ip[16],url[64],sig[65],prefix[48];unsigned char digest[32];
    struct in_addr addr={.s_addr=host};inet_ntop(AF_INET,&addr,ip,sizeof ip);
    snprintf(url,sizeof url,"http://%s:19433/voice",ip);
    snprintf(prefix,sizeof prefix,"voice:%s\n",id);
    mbedtls_md_context_t md;mbedtls_md_init(&md);
    int result=mbedtls_md_setup(&md,mbedtls_md_info_from_type(MBEDTLS_MD_SHA256),1);
    if(!result)result=mbedtls_md_hmac_starts(&md,(const unsigned char *)key,64);
    if(!result)result=mbedtls_md_hmac_update(&md,(const unsigned char *)prefix,strlen(prefix));
    if(!result)result=mbedtls_md_hmac_update(&md,wav,length);
    if(!result)result=mbedtls_md_hmac_finish(&md,digest);
    mbedtls_md_free(&md);if(result)return false;
    for(int i=0;i<32;i++)snprintf(sig+i*2,3,"%02x",digest[i]);
    esp_http_client_config_t cfg={.url=url,.timeout_ms=15000,.buffer_size=512,.buffer_size_tx=512,.disable_auto_redirect=true};
    esp_http_client_handle_t client=esp_http_client_init(&cfg);if(!client)return false;
    esp_http_client_set_method(client,HTTP_METHOD_POST);
    esp_http_client_set_header(client,"Content-Type","audio/wav");
    esp_http_client_set_header(client,"X-Voice-ID",id);esp_http_client_set_header(client,"X-Voice-Signature",sig);
    bool ok=esp_http_client_open(client,length)==ESP_OK;size_t sent=0;
    while(ok && sent<length) {int n=esp_http_client_write(client,(const char *)wav+sent,length-sent>4096?4096:length-sent);if(n<=0)ok=false;else sent+=n;}
    if(ok) {esp_http_client_fetch_headers(client);int code=esp_http_client_get_status_code(client);ok=code==200||code==202;ESP_LOGI(TAG,"voice upload status %d, %u bytes",code,(unsigned)length);}
    esp_http_client_close(client);esp_http_client_cleanup(client);return ok;
}
