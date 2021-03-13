""" @file parallel.py
@brief Helps with parallel processing """

import os
import sys
import tempfile
import traceback

from helper.common import *
from multiprocessing import Process

class Parallel:
    """ @class Runs a function in parallel """

    # Flags for failure mode
    FAILURE_EXIT = 0
    FAILURE_CONT = 1

    def __init__(self, func, cores, transparent_io=False, 
            failure_mode=FAILURE_CONT, name='', verbose=False):
        """ @brief Initialize parallel object
        
        @param func Function to execute
        @param cores CPU cores to use
        @param transparent_io Boolean indicating if the output should be 
               redirected to stdout and stderr instead of a log file
        @param failure_mode Specifies behaviour of parallel object on one of
               processes run fails, possible options:\n 
               *FAILURE_EXIT*: Exit on failure (exit code != 0)\n 
               *FAILURE_CONT*: Ignore failure and continue execution
        @param verbose Enable verbose mode """

        abort_if(cores < 1, 'Core count should be a non-zero positive integer')

        self.func = func
        self.cores = cores
        self.running = 0
        self.pobjs = []
        self.transparent_io = transparent_io
        self.name = name
        self.failure_mode = failure_mode
        self.verbose = verbose

    def alive_cnt(self):
        """@brief Returns the total number of processes alive 
        @return int """
        cnt = 0

        idx_to_delete = []

        idx = 0
        for process in self.pobjs:
            if process.is_alive():
                cnt += 1
            else:
                if self.failure_mode == Parallel.FAILURE_EXIT \
                        and process.exitcode != 0:

                    hr_code = translate_exit_code(process.exitcode)
                    abort('%s: Child with PID %d failed: %s' \
                        % (self.name, process.pid, hr_code[0]))
                
                try:
                    process.close()
                except AttributeError as e:
                    # printw('Process already completed, catched %s: %s' \
                    #     % (type(e).__name__, e.args))
                    pass

                idx_to_delete.append(idx)
            idx += 1

        for i in sorted(idx_to_delete, reverse=True):
            del self.pobjs[i]

        return cnt

    def _wrapper(self, *args, **kwargs):
        """ @brief Wrapper function for redirecting I/O 
        @param *args
        @param **kwargs
        @return None"""

        pid = os.getpid()

        # Create a temporary file
        prefix = 'pmfuzz-subprocess-%d.out.'%pid
        fd, fname = tempfile.mkstemp(prefix=prefix)
        
        if self.verbose:
            printi('%s: Writing output to %s args = %s kwargs = %s' \
                % (self.name, fname, str(args), str(kwargs)))
        
        sys.stdout.flush()
        sys.stderr.flush()

        stdout_bak = sys.stdout
        stderr_bak = sys.stderr

        with open(fd, 'w') as f:
            #  Set the temporary files as as stdout and stderr
            if not self.transparent_io:
                sys.stdout = f
                sys.stderr = f
            
            # Execute the function
            try:
                printi('Starting execution for %s' % (str(self.func)))
                printi('args: ' + str(args))
                self.func(*args, **kwargs)
                printi('Done with execution')
                sys.stdout.flush()
                sys.stderr.flush()

            except Exception as e:
                print('Unexpected exception: ' + str(e))
                print('Stack: ')
                traceback.print_exc()
                raise
                abort('Exiting on Exception')
        
        # Restore IO
        if not self.transparent_io:
                sys.stdout = stdout_bak
                sys.stderr = stderr_bak

        if self.verbose:
            printv('%s: Completed execution' % self.name)

    def run(self, params):
        """ @brief Runs a single instance of the function with the suplied 
        parameters
        @param params Parameter to call the function with
        @return None """

        # If processes are already at capacity, wait
        while (self.alive_cnt() == self.cores):
            pass

        proc = Process(target=self._wrapper, args=params)
        proc.start()
        self.pobjs.append(proc)

    @property
    def alive(self):
        """ @brief Is atleast one job alive
        @return bool """

        result = False

        for pid in self.pobjs:
            if pid.is_alive():
                result = True
                break

        return result
    
    def wait(self):
        """ @brief Wait for all jobs to complete """
        while self.alive:
            pass