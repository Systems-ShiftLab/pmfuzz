""" 
@file       lcov.py
@details    Interfaces with lcov
@copyright  2020-21 PMFuzz Authors

SPDX-license-identifier: BSD-3-Clause

TODO: Write documentation of functions and overall flow
"""

import os
import glob
import tempfile

from os import path

from handlers import name_handler as nh 
from helper.common import abort, abort_if, exec_shell, decompress
from helper.prettyprint import *

class Lcov:
    """ @class Interfaces with lcov """

    def __init__(self, tc_dirs, img_dirs, cfg, empty_img, verbose):
        self.tc_dirs = tc_dirs
        self.img_dirs = img_dirs
        self.cfg = cfg
        self.verbose = verbose
        self.empty_img = self.cfg['lcov']['empty_img']

        abort_if(len(tc_dirs) != len(img_dirs), '')

    def run_tgt(self, tc, img):
        env = self.cfg.get_env(persist=False)
        cmd = list(self.cfg.tgtcmd)

        _, cmd = nh.set_img_path(cmd, img, self.cfg)
        
        fd, tempf = tempfile.mkstemp(prefix='pmfuzz-gcov-run-')
        os.close(fd)
            
        if self.verbose:
            printv('target run:')
            printv('%20s : %s' % ('env', str(env)))
            printv('%20s : %s' % ('input', tc))
            printv('%20s : %s' % ('output', tempf))
            printv('%20s : %s' % ('cmd', ' '.join(cmd)))

        with open(tc, 'r') as stdin, open(tempf, 'w') as stdout:
            exec_shell(
                cmd     = cmd,
                stdin   = stdin,
                stdout  = stdout,
                stderr  = stdout,
                env     = env,
                wait    = True,
            )

    def capture(self):
        fd, result_f = tempfile.mkstemp(prefix='pmfuzz-lcov-out-')
        os.close(fd)

        lcov_bin    = ['lcov']
        lcov_opts   = self.cfg['lcov']['options'] + ['-c']
        lcov_scd    = ['--directory'] + self.cfg['lcov']['source_code_dirs']
        lcov_out    = ['--output-file', result_f]

        lcov_cmd    = lcov_bin + lcov_opts + lcov_scd + lcov_out

        fd, log_f = tempfile.mkstemp(prefix='pmfuzz-lcov-log-')
        os.close(fd)

        if self.verbose:
            printv('lcov run:')
            printv('%20s : %s' % ('env', str({})))
            printv('%20s : %s' % ('cmd', ' '.join(lcov_cmd)))
            printv('%20s : %s' % ('output', log_f))

        with open(log_f, 'w') as log_obj:
            exec_shell(
                lcov_cmd,
                stdin   = None,
                stdout  = log_obj,
                stderr  = log_obj,
                env     = {},
                wait    = True,
            )

        if self.verbose:
            printv('Coverage information written to ' + result_f)
            f_count = 0
            with open(result_f, 'r') as obj:
                for line in obj:
                    tokens = line.split(':')
                    if tokens[0] == 'FNDA':
                        cur_count = int(tokens[1].split(',')[0])
                        if cur_count > 0:
                            f_count+=1
            printv('Total %d functions hit' % f_count)

        return result_f

    def reset_counters(self):
        fd, result_f = tempfile.mkstemp(prefix='pmfuzz-lcov-out-')
        os.close(fd)

        lcov_bin    = ['lcov']
        lcov_opts   = self.cfg['lcov']['options'] + ['-z']
        lcov_scd    = ['--directory'] + self.cfg['lcov']['source_code_dirs']
        lcov_out    = ['--output-file', result_f]

        lcov_cmd    = lcov_bin + lcov_opts + lcov_scd + lcov_out

        fd, log_f = tempfile.mkstemp(prefix='pmfuzz-lcov-log-')
        os.close(fd)

        if self.verbose:
            printv('counters reset:')
            printv('%20s : %s' % ('env', str({})))
            printv('%20s : %s' % ('cmd', ' '.join(lcov_cmd)))
            printv('%20s : %s' % ('output', log_f))

        with open(log_f, 'w') as log_obj:
            exec_shell(
                lcov_cmd,
                stdin   = None,
                stdout  = log_obj,
                stderr  = log_obj,
                env     = {},
                wait    = True,
            )

        return result_f

    def execute_tcs(self, tc_dir, img_dir):
        tcs = [path.join(tc_dir, fn) for fn in os.listdir(tc_dir)]
        imgs = [path.join(img_dir, fn) for fn in os.listdir(img_dir)]

        iter = 0
        for tc in filter(nh.is_tc, tcs):
            # print(tc)
            # iter += 1
            # if iter > 5:
            #     return
            img = self.empty_img

            if nh.ancestor_cnt(path.basename(tc)) > 0:
                parent = nh.get_testcase_parent(path.basename(tc))
                img = nh.get_metadata_files(parent)['pm_cmpr_pool']
                img = path.join(path.dirname(img_dir), '@dedup', img)

                abort_if(path.basename(img) not in os.listdir(img_dir), 
                    'Img %s not found in %s' % (img, img_dir))

            printi('Running %s with image %s' % (tc, img))
            
            img_cmpr = img.endswith('.tar.gz')
            if img_cmpr:
                decompress(img, '/mnt/pmem0/', verbose=self.verbose)
                img = path.join(
                    '/mnt/pmem0/',
                    path.basename(nh.get_metadata_files(img)['pm_pool'])
                )

            self.run_tgt(tc, img)

            if img_cmpr:
                os.remove(img)
    def remove_captures(self, tracefile):
        fd, result_f = tempfile.mkstemp(prefix='pmfuzz-lcov-out-')
        os.close(fd)

        lcov_bin    = ['lcov']
        lcov_opts   = ['--no-checksum', '-r'] + [tracefile] 
        lcov_opts   += ['/usr/include/*']
        lcov_scd    = []
        lcov_out    = ['--output-file', result_f]

        lcov_cmd    = lcov_bin + lcov_opts + lcov_scd + lcov_out

        fd, log_f = tempfile.mkstemp(prefix='pmfuzz-lcov-log-')
        os.close(fd)

        if self.verbose:
            printv('remove /usr/include:')
            printv('%20s : %s' % ('env', str({})))
            printv('%20s : %s' % ('cmd', ' '.join(lcov_cmd)))
            printv('%20s : %s' % ('output', log_f))

        with open(log_f, 'w') as log_obj:
            exec_shell(
                lcov_cmd,
                stdin   = None,
                stdout  = log_obj,
                stderr  = log_obj,
                env     = {},
                wait    = True,
            )

        return result_f

    def run(self):
        iter = 0

        self.reset_counters()

        for tc_dir in self.tc_dirs:
            img_dir = self.img_dirs[iter]

            self.execute_tcs(tc_dir, img_dir)

            iter += 1

        # Collect the information using lcov
        printi('Capturing coverage information')
        result_f = self.remove_captures(self.capture())

        printi('Result at %s' % result_f)
