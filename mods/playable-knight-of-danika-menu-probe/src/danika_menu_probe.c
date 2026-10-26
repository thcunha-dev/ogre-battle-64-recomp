// Knight of Danika native Change Class menu probe.
// READ-ONLY: observes menu state and selected roster class; never writes game RAM.
#include "modding.h"

RECOMP_IMPORT("*", void recomp_log(const char* message));

#define MENU_BASE  0x801939F0u
#define MENU_SIZE  0x30u
#define ROSTER     0x80193BE0u
#define STRIDE     0x38u
#define CLASS_OFF  0x12u
#define COUNT      100u

static unsigned char prev[MENU_SIZE];
static unsigned char initialized;
static unsigned char last_selected = 0xFFu;
static unsigned char last_class = 0xFFu;

static unsigned char rd8(unsigned int a) { return *(volatile const unsigned char*)a; }
static char hx(unsigned int v) { v &= 15u; return v < 10u ? (char)('0'+v) : (char)('A'+v-10u); }

static void log_change(unsigned int off, unsigned int oldv, unsigned int newv) {
    char s[] = "DANIKA_MENU +00 00->00";
    s[13]=hx(off>>4); s[14]=hx(off);
    s[16]=hx(oldv>>4); s[17]=hx(oldv);
    s[20]=hx(newv>>4); s[21]=hx(newv);
    recomp_log(s);
}

static void log_selected(unsigned int idx, unsigned int cls) {
    char s[] = "DANIKA_SELECTED i=00 class=00";
    s[18]=hx(idx>>4); s[19]=hx(idx);
    s[27]=hx(cls>>4); s[28]=hx(cls);
    recomp_log(s);
}

RECOMP_HOOK("func_80072944")
void danika_menu_probe_tick(void) {
    unsigned int i;
    if (!initialized) {
        for (i=0;i<MENU_SIZE;i++) prev[i]=rd8(MENU_BASE+i);
        initialized=1u;
        recomp_log("DANIKA_MENU_PROBE ready read_only");
    } else {
        for (i=0;i<MENU_SIZE;i++) {
            unsigned int v=rd8(MENU_BASE+i);
            if (v!=prev[i]) { log_change(i,prev[i],v); prev[i]=(unsigned char)v; }
        }
    }

    // D_801939F4 is the selected roster index used by the native UI formatter.
    // Only dereference the proven player roster when the index is valid.
    {
        unsigned int idx=rd8(0x801939F4u);
        if (idx<COUNT) {
            unsigned int cls=rd8(ROSTER+idx*STRIDE+CLASS_OFF);
            if (idx!=last_selected || cls!=last_class) {
                last_selected=(unsigned char)idx;
                last_class=(unsigned char)cls;
                log_selected(idx,cls);
            }
        }
    }
}
