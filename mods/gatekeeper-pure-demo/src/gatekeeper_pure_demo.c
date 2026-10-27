#include "modding.h"
RECOMP_IMPORT("*", void recomp_log(const char* message));

#define CHAR_TABLE 0x80193BE0u
#define CHAR_STRIDE 0x38u
#define CHAR_CLASS 0x12u
#define CHAR_EQUIP0 0x2Au
#define CHAR_COUNT 100u

/* Class record+0x2E: four u16 default equipment IDs. */
#define CLASS_EQUIP_TABLE 0x80187C62u
#define CLASS_STRIDE 0x48u
#define CLASS_EQUIP_SLOTS 4u

#define FIGHTER_CLASS_ID 0x02u
#define GATEKEEPER_CLASS_ID 0x71u

static unsigned char s_done;

static unsigned char rd8(unsigned int a){
    return *(volatile const unsigned char*)a;
}

static unsigned short rd16(unsigned int a){
    return *(volatile const unsigned short*)a;
}

static void wr8(unsigned int a,unsigned char v){
    *(volatile unsigned char*)a=v;
}

static void wr16(unsigned int a,unsigned short v){
    *(volatile unsigned short*)a=v;
}

static void apply_gatekeeper_defaults(unsigned int character){
    unsigned int slot;
    unsigned int defaults = CLASS_EQUIP_TABLE + GATEKEEPER_CLASS_ID * CLASS_STRIDE;

    for(slot=0u; slot<CLASS_EQUIP_SLOTS; ++slot){
        unsigned short item = rd16(defaults + slot * 2u);
        wr16(character + CHAR_EQUIP0 + slot * 2u, item);
    }
}

/*
 * Coherent promotion smoke/demo:
 *   second persistent Fighter -> Gatekeeper 0x71
 *   and copy Gatekeeper's own four class-default equipment IDs first.
 *
 * No battle participant writes.
 * No Dragoon class bridge.
 * No visual-selector writes.
 * No streamed/banked hooks.
 */
RECOMP_HOOK("func_80072944")
void gatekeeper_pure_demo_tick(void){
    unsigned int i;
    unsigned int seen=0u;

    if(s_done){
        return;
    }

    for(i=0u;i<CHAR_COUNT;++i){
        unsigned int character=CHAR_TABLE+i*CHAR_STRIDE;
        unsigned int class_addr=character+CHAR_CLASS;

        if(rd8(class_addr)!=(unsigned char)FIGHTER_CLASS_ID){
            continue;
        }

        ++seen;
        if(seen==2u){
            /* Match vanilla promotion ordering: make equipment coherent first. */
            apply_gatekeeper_defaults(character);
            wr8(class_addr,(unsigned char)GATEKEEPER_CLASS_ID);
            s_done=1u;
            recomp_log("GATEKEEPER_PURE_DEMO Fighter2_to_Gatekeeper_with_Gatekeeper_defaults");
            return;
        }
    }
}
