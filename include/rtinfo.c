#include "rtinfo.h"
#include <stdio.h>
#include <stdlib.h>
#include <sys/prctl.h>
#include <sys/wait.h>
#include <unistd.h>

void print_trace() {
    char pid_buf[30];
    sprintf(pid_buf, "%d", getpid());
    char name_buf[512];
    name_buf[readlink("/proc/self/exe", name_buf, 511)]=0;
	prctl(PR_SET_PTRACER, PR_SET_PTRACER_ANY, 0, 0, 0);
    int child_pid = fork();
    if (!child_pid) {           
        execlp("gdb", "gdb", "--batch", "-n", "-ex", "thread", "-ex", "bt", name_buf, pid_buf, NULL);
        abort(); /* If gdb failed to start */
    } else {
        waitpid(child_pid,NULL,0);
    }
}

int print_stack_trace() {
    print_str(STDERR_FILENO, "--- Begin stacktrace ---\n");

	print_trace();

    print_str(STDERR_FILENO, "--- End stacktrace ---\n");
	
    return (0);
}
