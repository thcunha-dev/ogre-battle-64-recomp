#include "modding.h"
RECOMP_IMPORT("*", void recomp_log(const char* message));
#define CHAR_TABLE 0x80193BE0u
#define CHAR_STRIDE 0x38u
#define CHAR_CLASS 0x12u
#define CHAR_COUNT 100u
#define FIGHTER_CLASS_ID 0x02u
#define DRAGOON_CLASS_ID 0x14u
static unsigned char s_done;
static unsigned char rd8(unsigned int a){return *(volatile const unsigned char*)a;}
static void wr8(unsigned int a,unsigned char v){*(volatile unsigned char*)a=v;}
RECOMP_HOOK("func_80072944")
void gatekeeper_stable_bridge_tick(void){
    unsigned int i,seen=0u;
    if(s_done)return;
    for(i=0u;i<CHAR_COUNT;++i){
        unsigned int a=CHAR_TABLE+i*CHAR_STRIDE+CHAR_CLASS;
        if(rd8(a)!=(unsigned char)FIGHTER_CLASS_ID)continue;
        ++seen;
        if(seen==2u){
            wr8(a,(unsigned char)DRAGOON_CLASS_ID);
            s_done=1u;
            recomp_log("GATEKEEPER_BRIDGE Fighter2_to_Dragoon");
            return;
        }
    }
}
