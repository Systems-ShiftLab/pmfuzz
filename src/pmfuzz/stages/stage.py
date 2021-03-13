""" 
@file       stage.py
@details    TODO
@copyright  2020-21 University of Virginia

SPDX-license-identifier: BSD-3-Clause
"""

import datetime
import time

from os import path

from helper import common
from helper import config
from helper.bugreport import BugReport
from helper.target import Target as Tgt
from stages.fuzzobj import FuzzObj

class Stage(FuzzObj):
    """ @class Class for creating Stage objects """

    def __init__(self, name, srcdir, outdir, cfg, cores, verbose, 
            force_resp, dry_run):

        super().__init__(name, verbose, force_resp, dry_run)

        self.srcdir             = srcdir
        self.outdir             = outdir
        self.cfg                = cfg
        self.cores              = cores
        self.dry_run            = dry_run

        self.crash_site_db_f    = path.join(self.outdir, '@crashsitehashes.db')

    def save_possible_bug(self, tester_f, imgpath, cmd, env):
        bug_report = BugReport(tester_f, imgpath, cmd, env, self.outdir)
        bug_report.save()

        if self.verbose:
            bug_report.print()

    def check_crash_site(self, cspath):
        """ Check if a crash site works, if it doesn't save the details

        If running the target program using a crash site results in a crash 
        using on of the following signals: SIGILL: 4, SIGFPE: 8, SIGSEGV: 11, 
        SIGBUS: 10, SIGSYS: 12), then we might have hit a bug.

        On a crash of the program, the details related to the crash are saved
        to the global crash database.

        @param cspath str Representing compelete path to the crash site
        @return None"""

        INTERESTING_SIG_NUM = [4, 8, 10, 11, 12]

        tester_f_key = 'pmfuzz.failure_injection.test_with'
        tester_f = self.cfg(tester_f_key)

        common.abort_if(tester_f == 'None', 'Key %s needs to be non None' \
            % tester_f_key)

        tgt = Tgt(tester_f, self.cfg, self.verbose)
        success, exit_code, cmd, env = tgt.test_img(cspath)

        if self.verbose:
            common.printv('Testing %s, success = %s' % (cspath, str(success)))

        # If the program was terminated with a signal
        if exit_code < 0:
            sig_num = -exit_code

            if sig_num in INTERESTING_SIG_NUM:
                self.save_possible_bug(tester_f, cspath, cmd, env)

        return

    @property
    def srcdir(self):
        return self._srcdir

    @srcdir.setter
    def srcdir(self, value):
        self._srcdir = value

    @property
    def outdir(self):
        return self._outdir
    
    @outdir.setter
    def outdir(self, value):
        self._outdir = value

    @property
    def cfg(self):
        return self._cfg
    
    @cfg.setter
    def cfg(self, value):            
        self._cfg = value

    @property
    def cores(self):
        return self._cores
    
    @cores.setter
    def cores(self, value):
        self._cores = value
