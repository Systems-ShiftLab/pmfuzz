/**
 *  @file        shiftregarr.h
 *  @details     todo
 *  @author      author
 *  @copyright   License text
 */

#pragma once

#include <assert.h>
#include <limits.h>		/* for CHAR_BIT */
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>

#define SRA_SET   0
#define SRA_UNSET 255

#define BITMASK(b) (1 << ((b) % CHAR_BIT))
#define BITSLOT(b) ((b) / CHAR_BIT)
#define BITSET(a, b) ((a)[BITSLOT(b)] |= BITMASK(b))
#define BITCLEAR(a, b) ((a)[BITSLOT(b)] &= ~BITMASK(b))
#define BITTEST(a, b) ((a)[BITSLOT(b)] & BITMASK(b))
#define BITNSLOTS(nb) ((nb + CHAR_BIT - 1) / CHAR_BIT)

#define BYTE_TO_BINARY_PATTERN "%c%c%c%c%c%c%c%c"
#define BYTE_TO_BINARY(byte)  \
  (byte & 0x80 ? '1' : '0'), \
  (byte & 0x40 ? '1' : '0'), \
  (byte & 0x20 ? '1' : '0'), \
  (byte & 0x10 ? '1' : '0'), \
  (byte & 0x08 ? '1' : '0'), \
  (byte & 0x04 ? '1' : '0'), \
  (byte & 0x02 ? '1' : '0'), \
  (byte & 0x01 ? '1' : '0') 

/**
 * @brief Pushes back either 1 or 0 to the end of the shift register 
 * @param mem Pointer to the shift reg array
 * @param size Size of the shift reg array in bytes
 * @param elem_sz Size of each element in bytes (used for indexing the array)
 * @param loc Index of the shift reg in the array
 * @param basebit Value of unset bit in the map
 * @return void
 * 
 * **NOTE**: elem_sz cannot be larger than INT_32_MAX
*/
static inline void 
sra_push_back(uint8_t *mem, size_t size, size_t elem_sz, size_t loc, uint8_t basebit) {
    size_t elem_cnt = size/elem_sz;
    assert(loc < elem_cnt);

    uint8_t *arr = mem+(loc*elem_sz);
    size_t elem_sz_bits = elem_sz*8;

    int32_t it = elem_sz_bits;
    while (it--) {
        if (basebit && !BITTEST(arr, it)) {
            break;
        } else if (!basebit && BITTEST(arr, it)) {
            break;
        }
    }

    if (it != (int32_t)elem_sz_bits-1) {
        it++;
        if (basebit) {
            BITCLEAR(arr, it);
        } else {
            BITSET(arr, it);
        }
        if (it != 0) {
            it--;
            if (basebit) {
                BITSET(arr, it);
            } else{
                BITCLEAR(arr, it);
            }
        }
    }
}