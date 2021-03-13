#ifndef PM_TRACE_FUNCTS__
#define PM_TRACE_FUNCTS__

#include <stdint.h>

// PM Address range manipulation
void pm_trace_pm_addr_add(uint64_t addr, uint64_t size);
void pm_trace_pm_addr_remove(uint64_t addr, uint64_t size);

// Transaction annotation
void pm_trace_tx_begin(void);
void pm_trace_tx_end(void);
void pm_trace_tx_addr_add(uint64_t addr, uint64_t size);
void pm_trace_tx_alloc(uint64_t addr, uint64_t size);

void tx_commit_point(void);

/*
// PMDK library TX function annotation
void pm_trace_pmdk_funct_begin(void);
void pm_trace_pmdk_funct_end(void);
*/

#endif // PM_TRACE_FUNCTS__
