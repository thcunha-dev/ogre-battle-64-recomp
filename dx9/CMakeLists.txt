cmake_minimum_required(VERSION 3.20)

# Clean entry point for the old/weak Windows PC build.
#
# Usage from the repository root:
#   cmake -S dx9 -B build-dx9 -G Ninja -DCMAKE_BUILD_TYPE=Release
#   cmake --build build-dx9 -j
#
# This wrapper intentionally reuses the normal app project/runtime/game code,
# but forces RT64 off and selects the Direct3D 9 renderer through the existing
# bring-up selector. Keeping this separate avoids passing ad-hoc compiler and
# linker flags and, most importantly, prevents RT64/D3D12/Vulkan from entering
# a low-end package by accident.
project(ogrebattle64_dx9 LANGUAGES C CXX)

if (NOT WIN32)
    message(FATAL_ERROR "The Ogre Battle 64 Direct3D 9 build is Windows-only.")
endif()

set(OGRE_USE_RT64 OFF CACHE BOOL "RT64 is disabled in the Direct3D 9 low-end build" FORCE)
set(OGRE_USE_DX9 ON CACHE BOOL "Direct3D 9 low-end renderer" FORCE)
add_compile_definitions(OGRE_USE_DX9=1)

# The app owns all game/runtime/platform targets. CMAKE_CURRENT_SOURCE_DIR
# becomes app/ inside the subdirectory, so its existing relative tool paths stay
# valid exactly as in the normal build.
add_subdirectory("${CMAKE_CURRENT_LIST_DIR}/../app" app)

if (NOT TARGET ogrebattle64)
    message(FATAL_ERROR "The Ogre Battle 64 app target was not created.")
endif()

# Direct3D 9 is part of Windows. No D3DX, DXGI, D3D12, Vulkan or runtime shader
# compiler is linked by this wrapper.
target_link_libraries(ogrebattle64 PRIVATE d3d9)
target_compile_definitions(ogrebattle64 PRIVATE OGRE_USE_DX9=1)

message(STATUS "Ogre Battle 64 renderer: Direct3D 9 low-end (RT64 disabled)")
