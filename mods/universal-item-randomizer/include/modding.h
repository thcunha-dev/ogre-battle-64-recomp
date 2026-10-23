#ifndef OGRE_MODDING_H
#define OGRE_MODDING_H

#define RECOMP_IMPORT(mod, func) \
    _Pragma("GCC diagnostic push") \
    _Pragma("GCC diagnostic ignored \"-Wunused-parameter\"") \
    _Pragma("GCC diagnostic ignored \"-Wreturn-type\"") \
    __attribute__((noinline, weak, used, section(".recomp_import." mod))) func {} \
    _Pragma("GCC diagnostic pop")

#define RECOMP_EXPORT __attribute__((section(".recomp_export")))
#define RECOMP_PATCH __attribute__((section(".recomp_patch")))
#define RECOMP_FORCE_PATCH __attribute__((section(".recomp_force_patch")))
#define RECOMP_HOOK(func) __attribute__((section(".recomp_hook." func)))
#define RECOMP_HOOK_RETURN(func) __attribute__((section(".recomp_hook_return." func)))

#endif
