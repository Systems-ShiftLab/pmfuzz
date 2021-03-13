""" 
@file       fuzzobj.py
@details    TODO
@copyright  2020-21 PMFuzz Authors

SPDX-license-identifier: BSD-3-Clause
"""

import time

from os import path
import datetime

from helper import common
from helper import prettyprint
from helper import config

class FuzzObj:
    """ @class Class for creating pmfuzz objects """

    # Holds the suffix for output directory of all the stages
    SUFFIX = '.pmfuzz-outdir'

    def __init__(self, name, verbose, force_resp, dry_run):
        self.force_resp = force_resp    # Force resp needs to be set first 
                                        # for others to use it
                                        
        self.name               = name
        self.verbose            = verbose
        self.dry_run            = dry_run

    def printv(self, msg):
        if self.verbose:
            prettyprint.printv(msg)

    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, value):
        self._name = value

    @property
    def verbose(self):
        return self._verbose
    
    @verbose.setter
    def verbose(self, value):
        self._verbose = value

    @property
    def force_resp(self):
        return self._force_resp
    
    @force_resp.setter
    def force_resp(self, value):
        self._force_resp = value

    @property
    def dry_run(self):
        return self._dry_run
    
    @dry_run.setter
    def dry_run(self, value):
        self._dry_run = value
