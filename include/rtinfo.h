/**
 * Licensed under FreeBSD from 
*/

#pragma once

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
#include <ucontext.h>
#include <unistd.h>
#include <unwind.h>

#define	BACKTRACE_DEPTH	256
#define	NULLSTR	"(null)"

static inline void print_str(int fd, const char *str) {
	if (str == NULL) {
		write(fd, NULLSTR, strlen(NULLSTR));
	} else {
		write(fd, str, strlen(str));
	}
}

void print_unw_error(const char *fun, int error);

int print_stack_trace();
