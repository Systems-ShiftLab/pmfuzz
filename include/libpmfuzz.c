/**
 *  @file        libpmfuzz.c
 *  @details     Header file for PMFuzz annotation interface
 *  @copyright   2020-21 PMFuzz Authors
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
#include "rtinfo.h"

#include <assert.h>
#include <err.h>
#include <execinfo.h>
#include <libunwind.h>
#include <pthread.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <ucontext.h>
#include <unistd.h>
#include <unwind.h>

#ifndef DISABLE_PMFUZZ

char pmfuzz_version_str[] = "1.0.0";

/** Define the maximum value of the counter, for PMfuzz this value cannot
 * go more than 255 */
#define COUNTER_CAP (255)

/* Define the element size of SRA in bytes */
uint32_t __pmfuzz_sra_elem_size = 0;

/* AFL variables */
extern uint8_t      *__pmfuzz_area_ptr;
// extern uint8_t      *__afl_area_ptr;
extern uint32_t     __pmfuzz_map_size;
extern uint32_t     __pmfuzz_prev_loc;

extern uint8_t      *__last_pmfuzz_area_ptr;

/* Maximum number of failure point allowed. No crash image generate if exceed 
   this number */
#define MAX_FAILURE_COUNT 10000L
/* Maximum number of crash sites to generate */
#define MAX_CRASH_DUMP_ID (10000)

/* Failure point variables */
uint8_t             pmfuzz_init_complete = 0;
uint32_t            __pmfuzz_failure_id = -1; // Initialize to -1
uint8_t             failure_list[MAX_FAILURE_COUNT];
FILE*               failure_list_file;

/* Env variables */
#define FI_MODE_ENV         "FI_MODE"       /* Failure injection mode */
#define FAILURE_LIST_ENV    "FAILURE_LIST"  /* File to write failure ids */
#define PMFUZZ_DEBUG_ENV    "PMFUZZ_DEBUG"  /* Enables debug messages */
#define FI_IMG_SUFFIX_ENV   "FI_IMG_SUFFIX" /* Suffix for crash sites */
#define GEN_ALL_CS_ENV      "GEN_ALL_CS"    /* Makes selection probability 1 */
#define IMG_CREAT_FINJ_ENV  "IMG_CREAT_FINJ"/* Enables all images for failure inj during creation */

/* Modes for failure injection */
#define TEST_MODE           "TEST"          /* Run on top of testing tool */
#define FUZZ_MODE           "FUZZ"          /* Run on top of fuzzer */
#define IMG_GEN_MODE        "IMG_GEN"       /* Generate crash image */
#define IMG_REP_MODE        "IMG_REP"       /* Reproduce image */

#define debug(...) do {\
    if (getenv(PMFUZZ_DEBUG_ENV)) {\
        if (strcmp("1", getenv(PMFUZZ_DEBUG_ENV)) == 0) {\
            dprintf(2, __VA_ARGS__);\
        }\
    }\
} while(0);

#define debug_enabled (getenv(PMFUZZ_DEBUG_ENV) && \
        strcmp("1", getenv(PMFUZZ_DEBUG_ENV)) == 0)

/**
 * @enum FIMode
 * @brief Failure injection mode
 */
typedef enum {
    FIM_NONE    = 0,
    FIM_IMG_GEN = 1,
    FIM_IMG_REP = 2,
    FIM_MAX     = 3,
} FIMode_t;

/* Compute the next highest power of 2 of 32-bit val */
uint32_t get_next_pow_2(uint32_t val) {
    val--;
    val |= val >> 1;
    val |= val >> 2;
    val |= val >> 4;
    val |= val >> 8;
    val |= val >> 16;
    val++;
    return val;
}

/**
 * @brief Updates a single element in the whole map
 * @param loc Location of the element to update
 * @return void
*/
void update_loc(uint32_t loc) {
    if (getenv("ENABLE_PM_PATH") != NULL || getenv("UNFOCUSSED_MODE") != NULL) {
        uint32_t elem_id = loc;

        uint32_t cur_loc = elem_id^__pmfuzz_prev_loc;
        __pmfuzz_prev_loc = elem_id>>1;

        if (__pmfuzz_area_ptr[cur_loc] < COUNTER_CAP) {
            __pmfuzz_area_ptr[cur_loc]++;
        }
    } else { // For baseline
        if (__pmfuzz_sra_elem_size == 0) {
            __pmfuzz_sra_elem_size = get_next_pow_2(COUNTER_CAP/8);
            printf("%u -> %u\n", (COUNTER_CAP/8), __pmfuzz_sra_elem_size);
        }

        uint32_t elem_id = (loc)%(__pmfuzz_map_size/__pmfuzz_sra_elem_size-97);

        uint32_t cur_loc = elem_id^__pmfuzz_prev_loc;
        __pmfuzz_prev_loc = elem_id>>1;

        sra_push_back(__pmfuzz_area_ptr, __pmfuzz_map_size, __pmfuzz_sra_elem_size, cur_loc, 0);
    }
}

/** 
 * @brief Hint for a read-only PM access
 * @param rand A compile time random number for identifying a code location
 *
 * **NOTE:** First half of the map is for reads, second half for writes 
 * @return void
 */
void pmfuzz_ro(uint32_t rand) {
    uint32_t loc = rand%(__pmfuzz_map_size/2);

    /* Update the map */
    update_loc(loc);

    return;
}

/** 
 * @brief Hint for a write-only PM access
 * @param rand A compile time random number for identifying a code location
 *
 * **NOTE:** First half of the map is for reads, second half for writes 
 * @return void
 */
void pmfuzz_wo(uint32_t rand) {
    uint32_t loc = rand%((__pmfuzz_map_size/2)-97);

    /* Upper half of the map */
    loc += __pmfuzz_map_size/2;

    /* Update the map */
    update_loc(loc);
    
    return;
}

/** 
 * @brief Hint for a read-write PM access
 * @param rand A compile time random number for identifying a code location
 *
 * **NOTE:** First half of the map is for reads, second half for writes 
 * @return void
 */
void pmfuzz_rw(uint32_t rand) {
    uint32_t loc = rand%((__pmfuzz_map_size/2)-97);

    /* Update the map for read */
    update_loc(loc);

    /* Go to upper half of the map */
    loc += __pmfuzz_map_size/2;

    /* Update the map for write */
    update_loc(loc);

    return;
}

/**
 * @brief Reads the FI_MODE environment and converts it to FIMode
 * Also checks for consistency in environment variables meant for failure
 * injection
 * @return FI_MODE value corresponding to the env var
 */
FIMode_t get_fi_mode() {
    char* mode_str = getenv(FI_MODE_ENV);
    FIMode_t result = FIM_NONE;
    if (mode_str == NULL) {
        result = FIM_NONE;
    } else if (strcmp(mode_str, "") == 0) {
        result = FIM_NONE;
    } else if (strcmp(mode_str, IMG_GEN_MODE) == 0) {
        result = FIM_IMG_GEN;
    } else if (strcmp(mode_str, IMG_REP_MODE) == 0) {
        result = FIM_IMG_REP;
    } else {
        dprintf(2, "Invalid failure injection mode (%s), check documentation\n", 
            mode_str);
        exit(1);
    }

    if (result == FIM_IMG_REP) {
        if (getenv(FAILURE_LIST_ENV) == NULL) {
            dprintf(2, FAILURE_LIST_ENV " env var is needed with img gen mode\n");
            exit(1);
        }
    }
    
    return result;
}

/**
 * @brief Injects a failure point, creating a copy of the PM pool
 * Failure injection works in three modes:
 * 1. `None`: No failure point is injected
 * 2. `IMG_GEN`: Generates crash sites (imgs) by injecting a failure point 
 * 3. `IMG_REP`: todo
 *
 * **NOTE:** Atleast one call to @ref pmfuzz_init() is required before a failure 
 * image will be generated.
 *
 * ### Environment variables read
 * 1. `FI_MODE={<empty or unset>|IMG_GEN|IMG_REP}`
 * 2. `FAILURE_LIST=<path to file to write failure ids to>`
 * 3. `FI_IMG_SUFFIX=<suffix>`: Used for suffixing generated crash sites.
 *
 * ### Modes
 * #### 1. None
 * In case the the PMFUZZ_MODE env variable is not set or is empty, no failure
 * point will be injected and no image will be generated.
 * 
 * #### 2. IMG_GEN
 * In case the the PMFUZZ_MODE env variable is set to "IMG_GEN", a failure 
 * point is injected and the PM Image is dumped if the PM pool has changed
 * since the last failure injection. First failure injection always results
 * in an image dump. Images dump naming pattern: 
 * `<pool file name>.<failure id>`
 * If a failure list file is additionally specified using the env variable,
 * the falure ids that generate dumps are written to that file, one per line.
 *
 * #### 3. IMG_REP
 * todo
 *
 * ### Environment variables set by @ref `pmfuzz_init()`
 * 1. `PM_ADDR=<starting address of PM pool>`
 * 2. `PM_SIZE=<size of PM pool>`
 * 3. `TC_NAME=<testcase name>`
 * @return void
 */
void pmfuzz_inject_failure(char* file, int line) {
    uint8_t inject_failure = 0;

    /* Always increment failure ID first */
    __pmfuzz_failure_id++;

    // Debugging
    if (!getenv("POST_FAILURE"))
        debug("[FI] Failure ID %d at %s : %d\n", __pmfuzz_failure_id, file, line);

    // Debugging
    debug("[FI] Failure injection: pm_addr   = %s\n", getenv("PM_ADDR"));
    debug("[FI] Failure injection: pm_size   = %s\n", getenv("PM_SIZE"));
    debug("[FI] Failure injection: case_name = %s\n", getenv("TC_NAME"));
    debug("[FI] Failure list: %s\n", getenv(FAILURE_LIST_ENV));

    if (!pmfuzz_init_complete) {
        debug("[FI] No failure (PMFUZZ NOT INIT)\n");
        return;
    }

    FIMode_t mode = get_fi_mode();
    debug("Mode = %d\n", mode)
    switch (mode) {
        case FIM_NONE: {
            /* Failure injection is disabled */
            return;
        } 
        case FIM_IMG_REP: {
            /* Generate PM image according to failure list:
                1. Program reproduces PM image (IMG_REP_MODE):
                    Only the failure ID in the list will lead to an image 
                    (Use computation to save storage overhead) */
            if (failure_list[__pmfuzz_failure_id]) {
                /* Enable failure point injection */
                inject_failure = 1;
            } else {
                debug("[FI] No failure (REP_MODE)\n");
            }
            break;
        }
        case FIM_IMG_GEN:  {
            /* Genearte PM image if PM bitmap has changed:
                1. Program generates PM image (IMG_GEN_MODE):
                    Only when PM bitmap has changed */
            int pm_bitmap_diff = memcmp(__pmfuzz_area_ptr, 
                __last_pmfuzz_area_ptr, __pmfuzz_map_size);

            /* Decrease the probablity of a selecting a failure point as the 
            failure id increases until MAX_CRASH_DUMP_ID. Probability is 0 
            after that. */
            uint32_t prob = rand()%MAX_CRASH_DUMP_ID;
            uint32_t divide_factor 
                = __pmfuzz_failure_id == 0 ? 1 : __pmfuzz_failure_id;
            
            char save_img = 0; 
            
            save_img = (prob < 10000/divide_factor) ? 1 : 0;

            if (__pmfuzz_failure_id == 0) {
            	save_img = 0;
            }

            /* If asked for, generated all the crash sites */
            if (getenv(GEN_ALL_CS_ENV) != NULL) {
                if ((__pmfuzz_failure_id < 100) && (__pmfuzz_failure_id%5 == 0)) {
                    save_img = 1;
                } else {
                    save_img = 0;
                }
            }

            if (getenv(IMG_CREAT_FINJ_ENV) != NULL) {
                debug("[FI] Enabling failure image generation for all failure "
                    "points, %s=1\n", IMG_CREAT_FINJ_ENV);
                save_img = 1;
            }

            if (pm_bitmap_diff && save_img) {
                /* PM bit map updated: copy bitmap and inject failure */
                memcpy(__last_pmfuzz_area_ptr, __pmfuzz_area_ptr, __pmfuzz_map_size);

                /* Enable failure point injection */
                inject_failure = 1;
                debug("[FI] Injecting failure\n");
            } else if (!save_img) {
                debug("[FI] Ignoring changes\n");
            } else {
                debug("[FI] Not injecting failure, PM image unchanged\n");
            }
            break;
        } 
        default: {
            return;
        }
    }

    char *tc_suffix = getenv(FI_IMG_SUFFIX_ENV);
    if (tc_suffix == NULL) {
        tc_suffix = "";
    }

    /* Create child process */
    if (inject_failure) {
        if (debug_enabled){
            print_stack_trace();
        }
        
        /* get test case name from env */
        char tc_name[1024];
        strcpy(tc_name, getenv("TC_NAME"));

        /* Remove '.pm_pool' from the string */
        // uint16_t tc_name_len = strlen(getenv("TC_NAME"));
        char *rmstart1 = strstr(tc_name, ".pm_pool");
        char *rmstart2 = strstr(tc_name, ".crash_site");
        if (rmstart1 != NULL)
            *rmstart1 = '\0';
        if (rmstart2 != NULL)
            *rmstart2 = '\0';

        /* Create failure image name */
        char failure_id_str[255];
        sprintf(failure_id_str, ".%s.id=%06d.crash_site", tc_suffix, 
            __pmfuzz_failure_id);
        strcat(tc_name, failure_id_str);
        
        debug("[FI] Saving image to %s\n", tc_name);
        
        if (getenv("USE_FAKE_MMAP") 
                && !strcmp(getenv("USE_FAKE_MMAP"), "1")) {

            FILE *pm_out = fopen(tc_name, "wb");
            if (pm_out) {
                /* Dump pm data to image */
                char *pm_addr_str = getenv("PM_ADDR");
                uint64_t pm_addr = strtoull(pm_addr_str, NULL, 10);
                int pm_size = atoi(getenv("PM_SIZE"));
                fwrite((void*)pm_addr, pm_size, 1, pm_out); 
                fclose(pm_out);
            } else {
                perror("Cannot open output file");
            }
        } else {    
            char cmd[16384];
            /* Copy current PM image */
            sprintf(cmd, "cp '%s' '%s'", getenv("TC_NAME"), tc_name);
            system(cmd);
        }

        if (mode == FIM_IMG_GEN && failure_list_file != NULL) {
            /* Print failure id to failure_list_file */
            fprintf(failure_list_file, "%d\n", __pmfuzz_failure_id);
        }
    }

    // Debugging
    debug("[FI] New failure id is %d \n", __pmfuzz_failure_id);
}

// Read the failure list during init
void pmfuzz_set_addr_env(void* addr, unsigned long size) {
    /* Set PM address env */
    char addr_str[255];
    sprintf(addr_str, "%llu", (unsigned long long)addr);
    setenv("PM_ADDR", addr_str, 1);

    /* Set PM size env */
    char len_str[255];
    sprintf(len_str, "%lu", size);
    setenv("PM_SIZE", len_str, 1);
}

void pmfuzz_set_path_env(char* path) {
    /* Set test case name */
    char tc_str[1024];
    sprintf(tc_str, "%s", path);
    setenv("TC_NAME", tc_str, 1);
}

/** 
 * @brief Initializes PMFuzz failure injection
 * Sets all the environment variables required for injecting failures by 
 * `pmfuzz_inject_failure()`. Should be ideally called before the first call
 * to failure injection.
 * @param addr Starting address of the PM pool
 * @param size Size of the PM Pool
 * @param path path to the PM image on disk/PM device
 * @see pmfuzz_inject_failure()
 * @return void
 */
void pmfuzz_init(void* addr, unsigned long size, char* path) {
    if (pmfuzz_init_complete) 
        return;

    /* Set pm image info */
    pmfuzz_set_addr_env(addr, size);
    pmfuzz_set_path_env(path);
    debug("[FI] Initializing PMFuzz failure injection\n");
    
    FIMode_t mode = get_fi_mode();
    if (getenv(FAILURE_LIST_ENV) 
            && (mode == FIM_IMG_GEN || mode == FIM_IMG_REP)) {
        if (mode == FIM_IMG_GEN) {
            /* Overwrite existing file */
            failure_list_file = fopen(getenv(FAILURE_LIST_ENV), "w+");
        } else { 
            /* Read only */
            failure_list_file = fopen(getenv(FAILURE_LIST_ENV), "r");
            /* Read failure list and update failure_list */
            int failure_id;
            int index = 0;

            while (1) {
                int out = fscanf(failure_list_file, "%d", &failure_id);
                if (out == EOF) {
                    break;
                } else if (out == 0) {
                    perror("Failure file incorret format");
                    abort();
                }
                /* Limit the number of failure points */
                if (index < MAX_FAILURE_COUNT) {
                    failure_list[index++] = failure_id;
                } else {
                    break;
                }
            }
        }
        assert(failure_list_file && "Failure list file not exist");
    }
    pmfuzz_init_complete = 1;
}

void pmfuzz_term() {
    if (getenv(FAILURE_LIST_ENV)) {
        fclose(failure_list_file);
    }
}

#else


#define debug(...)

void pmfuzz_ro(uint32_t rand __attribute__((unused))) {
    debug("RO Function\n");
    return;
}

void pmfuzz_wo(uint32_t rand __attribute__((unused))) {
    debug("WO Function\n");
    return;
}

void pmfuzz_rw(uint32_t rand __attribute__((unused))) {
    debug("RW Function\n");
    return;
}

void pmfuzz_inject_failure(char* file __attribute__((unused)), 
        int line __attribute__((unused))) {
    return;
}

void pmfuzz_set_addr_env(void* addr __attribute__((unused)), 
        unsigned long size __attribute__((unused))) {
    return;
}

void pmfuzz_set_path_env(char* path __attribute__((unused))) {
    return;
}

void pmfuzz_term() {
    return;
}

void pmfuzz_init(void* addr __attribute__((unused)), 
        unsigned long size __attribute__((unused)), 
        char* path __attribute__((unused))) {
    return;
}


#endif // ^DISABLE_PMFUZZ
