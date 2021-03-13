""" 
@file       stage.py
@details    TODO
@copyright  2020-21 PMFuzz Authors

SPDX-license-identifier: BSD-3-Clause
"""
from helper import common
import handlers.name_handler as nh

from helper import config
from helper.prettyprint import *
from .stage import Stage

import os

class State(Stage):
    """ Class for handling current pmfuzz state. Object holds the state of 
    specified outdir when the last sync was called.

    ## Usage
    
    \code{python}
        obj = State(...)
        
        obj.sync()
        stage, iter_id = obj.stage, obj.iter_id
        
        ...
        
        obj.sync()
        new_stage, new_iter_id = obj.stage, obj.iter_id
    \endcode
    """

    def __init__(self, name, srcdir, outdir, cfg, cores, verbose, 
            force_resp, dry_run):
        super().__init__(name, srcdir, outdir, cfg, cores, verbose, 
                            force_resp, dry_run)
        self._dedup_exists = False

    def sync(self):
        """ Updates the class' knowledge of the changes in the outdir """
                
        dirs = os.listdir(self.outdir)

        # Maximum value of stage and iter_id seen until now
        stage_m = 0
        iter_id_m = 0

        # Find all the stages and iterations to find the maximum value
        cur_stages = {}
        for dir in dirs:
            if '@' == dir[0]: # Special directory
                if dir == '@dedup':
                    self._dedup_exists = True
                
            else: # Stage information directory
                stage, iter_id = nh.get_stage_inf(dir)

                if stage not in cur_stages:
                    cur_stages[stage] = []
                cur_stages[stage].append(iter_id)
                
                # Find the largest stage and iter_id until now
                if stage > stage_m:
                    stage_m = stage
                    iter_id_m = iter_id
                elif stage == stage_m and iter_id > iter_id_m:
                    iter_id_m = iter_id

        if self.verbose:
            printv('Found (stage: [iter_id,...]): ' + str(cur_stages))

        self._stage = stage_m
        self._iter_id = iter_id_m

    @property
    def stage(self):
        """ Returns the highest stage for the outdir, requires a call to
        sync() before the first use. Each subsequent calls would require
        sync() calls to retrieve lates `outdir` state. """

        if not hasattr(self, '_stage'):
            common.abort('No state found, was sync() called?')
        return self._stage
    
    @property
    def iter_id(self):
        """ Returns the highest iter_id for the highest stage in the outdir, 
        requires a call to sync() before the first use. Each subsequent calls 
        would require sync() calls to retrieve latest `outdir` state. """

        if not hasattr(self, '_iter_id'):
            common.abort('No state found, was sync() called?')
        return self._iter_id

    @property
    def dedup_exists(self):
        """ Returns boolean value denoting the existence of deduplication 
        directory in the outdir, requires a call to sync() before the first
        use. Each subsequent calls would require sync() calls to retrieve
        lates `outdir` state. """

        if not hasattr(self, '_dedup_exists'):
            common.abort('No state found, was sync() called?')
        return self._dedup_exists
    