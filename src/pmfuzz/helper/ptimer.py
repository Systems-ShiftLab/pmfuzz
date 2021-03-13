""" 
@file       ptimer.py
@details    TODO
@copyright  2020-21 University of Virginia

SPDX-license-identifier: BSD-3-Clause
"""
from datetime import timedelta
from os import path
import time

from helper.prettyprint import *
from helper import common

class PTimer:
    """ @brief Persitent timer for preserving timer across invocations 

    #### Usage

    \code{python}
        timer = PTimer(...)
        timer.set(60)
        timer.start()
        while not timer.expired():
            continue
        print('Timer completed (60 secs)')
    \endcode
    """

    # Filename for the timer
    TIMER_FNAME = '.ptimer'
    
    def __init__(self, timer_dir:str, name_prefix:str='', verbose:bool=False):
        self.verbose        = verbose
        self.timer_dir      = timer_dir
        self.state          = {'start': 0, 'length': 0}
        self.name_prefix    = name_prefix

        self.read()
        self._sync()

    def read(self):
        """ @brief Read the state from disk, no changes to self.state if not 
            ptimer found in the location """

        if path.isfile(self.timer_path):
            with open(self.timer_path, 'r') as fobj:
                #! Warn: Executes arbitrary code from the file
                self.state = eval(fobj.read())

    def _sync(self):
        """ @brief Writes the state to disk """

        # Create a file to store the timer value
        with open(self.timer_path, 'w') as fobj:
            fobj.write(str(self.state))

    def set(self, length) -> None:
        """ @brief Set the countdown value
        
        @param length Timer countdown value in seconds 
        @return None"""

        self.state['length'] = length
        self._sync()

    def start(self) -> None:
        """ @brief Start countdown 
        
        @return None"""

        self.state['start'] = time.time()
        self._sync()
    
    def expired(self):
        """ @brief Is countdown completed 
        
        @return A bool value indicating if the timer has expired. """

        time_elapsed = (time.time() - self.state['start'])

        return  time_elapsed > self.state['length']
    
    def clear(self) -> None:
        """ @brief Clears the persistent state 

        @return None"""
        
        self.state = {'start': 0, 'length': 0}
        self._sync()

    def start_new(self, length) -> None:
        """ @brief Resets and starts the timer with a new countdown 
        
        @param length Timer countdown value in seconds
        @return None"""

        self.clear()
        self.set(length)
        self.start()

    def elapsed_hr(self):
        """ @brief Converts elapsed time to a human readable string 
        @return Human readable string representation of the elapsed time """
        
        time_elapsed = int(time.time() - self.state['start'])
        return "{:0>8}".format(str(timedelta(seconds=time_elapsed)))

    def elapsed_pb(self, width=20):
        """ @brief Converts elapsed time to a progress bar 
        @return Human readable string representation of the elapsed time """
        
        time_elapsed = int(time.time() - self.state['start'])
        ratio_done = time_elapsed/float(self.state['length'])
        if ratio_done > 1:
            ratio_done = 1

        return ('▉'*int(ratio_done*width)).ljust(width, '░')

    def is_new(self):
        """ Checks if the timer hasn't been run yet. This could be a completely 
        new timer or an old timer which has been reset. 
        
        @return Bool value indicating if this timer is new or reset. """

        return (self.state['start'] == 0)

    @property
    def timer_dir(self):
        return self._timer_dir
    
    @property
    def timer_path(self):
        return path.join(self._timer_dir, self.name_prefix + PTimer.TIMER_FNAME)
    
    @timer_dir.setter
    def timer_dir(self, value):
        common.abort_if(not path.isdir(value), 
                        '%s is not a directory.' % value)
        self._timer_dir = value

    @property
    def verbose(self):
        return self._verbose
    
    @verbose.setter
    def verbose(self, value):
        self._verbose = value

    @property
    def name_prefix(self):
        return self._name_prefix
    
    @name_prefix.setter
    def name_prefix(self, value):
        self._name_prefix = value