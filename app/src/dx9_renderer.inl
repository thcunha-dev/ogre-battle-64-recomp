// Direct3D 9 low-end renderer entry point.
// Stage 5 remains the active, compiler-validated path while Stage 6 depth
// integration is completed behind the CI gate. Do not expose an unfinished Z
// path to low-end hardware tests.
#include "dx9_renderer_stage5.inl"
