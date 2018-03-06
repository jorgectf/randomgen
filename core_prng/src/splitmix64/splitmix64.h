#include <stdint.h>

typedef struct s_splitmix64_state {
  uint64_t state;
  int has_uint32;
  uint32_t uinteger;
} splitmix64_state;

static inline uint64_t splitmix64_next(uint64_t *state) {
  uint64_t z = (state[0] += 0x9e3779b97f4a7c15);
  z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9;
  z = (z ^ (z >> 27)) * 0x94d049bb133111eb;
  return z ^ (z >> 31);
}

static inline uint64_t splitmix64_next64(splitmix64_state *state) {
  return splitmix64_next(&state->state);
}

static inline uint32_t splitmix64_next32(splitmix64_state *state) {
  if (state->has_uint32) {
    state->has_uint32 = 0;
    return state->uinteger;
  }
  uint64_t next = splitmix64_next64(state);
  state->uinteger = next & 0xffffffff;
  state->has_uint32 = 1;
  return (uint32_t)(next >> 32);
}