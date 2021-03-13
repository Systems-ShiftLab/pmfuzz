#ifndef INCLUDE_PMFUZZ_INSTRUMENTATION_H__
#define INCLUDE_PMFUZZ_INSTRUMENTATION_H__

#include <stdint.h>
#include <stdio.h>
#include "shiftregarr.h"

extern char pmfuzz_version_str[];

void pmfuzz_ro(uint32_t rand);
void pmfuzz_wo(uint32_t rand);
void pmfuzz_rw(uint32_t rand);
void pmfuzz_inject_failure(char* file, int line);
void pmfuzz_set_addr_env(void* addr, unsigned long size);
void pmfuzz_set_path_env(char* path);

void pmfuzz_init(void* addr, unsigned long size, char* path);
void pmfuzz_term(void);

#define PMFUZZ_RND(range) \
    (((uint32_t)((15485867*__LINE__*__LINE__*(__COUNTER__+9))%4392203))%(range))

#define PMFUZZ_RND_LN(line, range) \
    (((uint32_t)((15485867*line*line*(__COUNTER__+9))%4392203))%(range))

#ifdef PMFUZZ

/* AFL variables */
extern uint8_t      *__pmfuzz_area_ptr;
extern uint32_t     __pmfuzz_map_size;
extern uint32_t     __pmfuzz_prev_loc;

#define PMFUZZ_MARK_RO __attribute__((annotate("pmfuzz_pm_read_func")))
#define PMFUZZ_MARK_WO __attribute__((annotate("pmfuzz_pm_write_func")))
#define PMFUZZ_MARK_RW __attribute__((annotate("pmfuzz_pm_read_write_func")))
#define NO_INLINE      __attribute__((noinline))

#define PMFUZZ_FAILURE_HINT pmfuzz_inject_failure(__FILE__, __LINE__);

#else

#define PMFUZZ_MARK_RO
#define PMFUZZ_MARK_WO
#define PMFUZZ_MARK_RW
#define NO_INLINE

#define PMFUZZ_FAILURE_HINT

#endif // PMFUZZ

#endif // INCLUDE_PMFUZZ_INSTRUMENTATION_H__
