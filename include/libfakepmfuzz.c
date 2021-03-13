/**
 *  @file        libpmfuzz.c
 *  @details     todo
 *  @author      author
 *  @copyright   License text
 * 
 * Libpmfuzz uses a non-standard size bitset to record PM accesses, on every
 * PM access the element would be left shifted by one, e.g.:
 *    [Location1 value: 00000000 00000000 00000000 00000000]
 * 1. PM access to location 1
 *    [New Location1 value: 00000000 00000000 00000000 00000001]
 * 2. PM access to location 1
 *    [New Location1 value: 00000000 00000000 00000000 00000010]
 */

#include "pmfuzz.h"

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wunused-parameter"

void update_loc(uint32_t loc) {
	return;
}
void pmfuzz_ro(uint32_t rand) {
	return;
}

void pmfuzz_wo(uint32_t rand) {
    return;
}

void pmfuzz_rw(uint32_t rand) {
    return;
}

void pmfuzz_inject_failure(char* file, int line) {
	return;
}

void pmfuzz_set_addr_env(void* addr, unsigned long size) {
	return;
}
void pmfuzz_set_path_env(char* path) {
	return;
}

void pmfuzz_init(void* addr, unsigned long size, char* path) {
	return;
}

void pmfuzz_term() {
	return;
}

#pragma GCC diagnostic pop
