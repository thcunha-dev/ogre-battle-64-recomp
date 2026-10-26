# Cross toolchain used by the ROM-local/offline DX9 build kit.
# The kit places LLVM-MinGW under tools/llvm-mingw; nothing here downloads or
# depends on RT64/D3D12/Vulkan at build time.
set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

get_filename_component(OGRE_DX9_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
set(OGRE_LLVM_MINGW "${OGRE_DX9_ROOT}/tools/llvm-mingw")
set(OGRE_LLVM_MINGW_TRIPLE "x86_64-w64-mingw32")

set(CMAKE_C_COMPILER   "${OGRE_LLVM_MINGW}/bin/${OGRE_LLVM_MINGW_TRIPLE}-clang")
set(CMAKE_CXX_COMPILER "${OGRE_LLVM_MINGW}/bin/${OGRE_LLVM_MINGW_TRIPLE}-clang++")
set(CMAKE_RC_COMPILER  "${OGRE_LLVM_MINGW}/bin/${OGRE_LLVM_MINGW_TRIPLE}-windres")
set(CMAKE_AR           "${OGRE_LLVM_MINGW}/bin/llvm-ar")
set(CMAKE_RANLIB       "${OGRE_LLVM_MINGW}/bin/llvm-ranlib")
set(CMAKE_STRIP        "${OGRE_LLVM_MINGW}/bin/llvm-strip")

set(CMAKE_FIND_ROOT_PATH
    "${OGRE_LLVM_MINGW}/${OGRE_LLVM_MINGW_TRIPLE}"
)
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
