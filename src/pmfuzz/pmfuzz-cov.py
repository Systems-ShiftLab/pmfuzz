#! /usr/bin/env python3
"""
@file       pmfuzz-cov.py
@brief      Coverage for PMFuzz
@details    TODO
@copyright  2020-21 PMFuzz Authors
@details    TODO

SPDX-license-identifier: BSD-3-Clause
"""

import argparse
import json
import os
import pprint
import psutil
import shutil
import signal
import subprocess
import sys
import time
import traceback
import textwrap

from core import pmfuzz
from handlers import name_handler as nh
from helper import common
from helper.config import Config
from helper.prettyprint import *
from interfaces.lcov import Lcov
from stages.state import State

from core import whatsup as wu

PROG_NAME   = common.get_version()['name']
VERSION_STR = common.get_version()['version']
AUTHORS_STR = common.get_version()['authors']
DESC_STR    = PROG_NAME + ': A Persistent Memory Fuzzer, version ' \
            + VERSION_STR + ' by ' + AUTHORS_STR

prg_args = None

def sigint_handler(sig, frame):
    print('\n\n+++ Exiting, SIGINT (Ctrl+C) +++\n')
    sys.exit(0)

def except_hook(exctype, value, tb):
    tb_fmt = traceback.format_exception(exctype, value, tb)[1:-1]
    
    # Too many open files
    if '[Errno 24]' in str(value):
        print('Open files:')
        list_open_fd()

    common.abort('Exception raised: ' + exctype.__name__ + ': ' + str(value), 
                    tb_fmt=tb_fmt)

def get_options():
    """ Returns parsed arguments """
    parser = argparse.ArgumentParser(prog=PROG_NAME, description=DESC_STR, 
                formatter_class=argparse.RawDescriptionHelpFormatter,
                add_help=False)

    # Required positional arguments
    reqPos = parser.add_argument_group('Required positional arguments')

    reqPos.add_argument('indir', type=str,
                        help='path to pmfuzz output directory')
    reqPos.add_argument('outdir', type=str,
                        help='path to directory for generated report')
    reqPos.add_argument('config', type=str,
                        help='Points to the config file to use, should' \
                                + ' conform to: configs/base.yml')

    optNam = parser.add_argument_group('Optional named arguments')

    # Optional arguments/switches
    optNam.add_argument('-h', '--help', action='help', 
                        default=argparse.SUPPRESS,
                        help='show this help message and exit')
    optNam.add_argument('--overwrite', '-o', action='store_true',
                        help='Overwrite the output directory')
    optNam.add_argument('--verbose', '-v', action='store_true',
                        help='Enables verbose logging to stdout')
    optNam.add_argument('--version', action='version', version='%(prog)s ' 
                        + VERSION_STR)

    args, unparsed = parser.parse_known_args()

    if args.verbose:
        print('Argument values:     ')
        print('\tindir:             ', args.indir)
        print('\toutdir:            ', args.outdir)
        print('\tconfig:            ', args.config)
        print('\tverbose:           ', args.verbose)

    return args, unparsed

def run_lcov(indir, outdir, cfg, verbose):
    gbl_dedup   = os.path.join(indir, '@dedup')
    tc_dirs     = [gbl_dedup]
    img_dirs    = [gbl_dedup]

    state       = State('State', '/dev/null', indir, cfg, 0, verbose, 
                    force_resp=None, dry_run=False)
    state.sync()

    stage       = int(state.stage)
    iterid      = int(state.iter_id)

    if stage == 2:
        stage_d = nh.get_outdir_name(stage, iterid)
        tc_dirs.append(os.path.join(indir, stage_d, 'testcases'))
        img_dirs.append(gbl_dedup)
    print(tc_dirs)
    lcov = Lcov(
        tc_dirs     = tc_dirs,
        img_dirs    = img_dirs,
        cfg         = cfg,
        empty_img   = '/mnt/pmem0/__empty_img__',
        verbose     = verbose,
    )

    lcov.run()

def main():
    # Register signal handlers
    signal.signal(signal.SIGINT, sigint_handler)

    # Register exception handler
    sys.excepthook = except_hook

    # Read the important options first    
    args, unparsed  = get_options()
    cfg_f           = args.config
    verbose         = args.verbose

    # Read the config file, 
    cfg = Config(cfg_f, verbose)
    cfg.parse()
    cfg.check()

    # Print out the config
    if verbose:
        printv('Contents: ')
        printoff(str(cfg), CBEIGE2)

    # Overwrite the output directory
    if os.path.isdir(args.outdir):
        printw('Overwriting output directory: ' + args.outdir)
        shutil.rmtree(args.outdir)
    elif os.path.isfile(args.outdir):
        printw('Overwriting output directory: ' + args.outdir)
        os.remove(args.outdir)

    run_lcov(args.indir, args.outdir, cfg, verbose)

if __name__ == '__main__':
    main()