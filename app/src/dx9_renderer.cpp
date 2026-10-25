// Ogre Battle 64: Person of Lordly Caliber - native Direct3D 9 renderer.
//
// This is the standalone translation-unit entry for the low-end Windows path.
// The implementation is still split into milestone .inl files while the backend
// is being brought up, but it no longer needs to masquerade as null_renderer.cpp
// for compile validation or for the eventual CMake renderer selector.

#if !defined(_WIN32)
#error "The Ogre Battle 64 Direct3D 9 renderer is Windows-only."
#endif

#include "dx9_renderer.inl"
