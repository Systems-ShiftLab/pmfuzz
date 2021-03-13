#! /usr/bin/env python3
"""
@file       run_fuzzer.py
@brief      Frontend for PMFuzz
@details    TODO
@author     author
@copyright  2020-21 PMFuzz Authors
@details    Implements the frontend for PMFuzz, parses options and performs 
            basic checks on the input before running PMFuzz.

SPDX-license-identifier: BSD-3-Clause
"""

# Check all the dependencies
import os
if __name__ == "__main__" and os.getenv('DISABLE_CHECK') == None:
    import pkg_resources as pkg_res
    import os, sys
    
    from pkg_resources import DistributionNotFound, VersionConflict

    script_dir = os.path.dirname(os.path.realpath(__file__))
    requirements_file = os.path.join(script_dir, 'requirements.txt')

    if not os.path.isfile(requirements_file):
        print(f"Cannot find {requirements_file}, aborting", file=sys.stderr)
        sys.exit(1)

    with open(requirements_file) as requirements_obj:
        dependencies = requirements_obj.read()
    
        # Make sure all the dependencies are installed
        dependency_check_failed = False
        try:
            pkg_res.require(dependencies)
        except DistributionNotFound as err:
            except_t, except_val, except_tb = sys.exc_info()

            print(f"ERROR: {except_val}")

            dependency_check_failed = True
            pass

        if dependency_check_failed:
            print("", file=sys.stderr)
            print("-" * 10, file=sys.stderr)
            print("Error during initialization, one or more packages are missing.",
                  file=sys.stderr)
            print("Please install all the packages from %s (check README)." \
                  % requirements_file, file=sys.stderr)
            sys.exit(1)
        
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

from core import whatsup as wu

PROG_NAME   = common.get_version()['name']
VERSION_STR = common.get_version()['version']
AUTHORS_STR = common.get_version()['authors']
BUG_LOC_STR = common.get_version()['bug_loc']
DESC_STR    = PROG_NAME + ': A Persistent Memory Fuzzer, version ' \
            + VERSION_STR + ' by ' + AUTHORS_STR \
            + "\n\nReport bugs at: " + BUG_LOC_STR

parent = True
prg_args = None

def sigint_handler(sig, frame):
    name = ''
    if parent:
        name = 'PMFuzz'
        print('Killing child %d' % get_child_pid())
        os.kill(get_child_pid(), signal.SIGINT)
        print('\n\n+++ Exiting %s, SIGINT (Ctrl+C) +++\n' % name)
        sys.exit(0)

def sigusr1_handler(sig, frame):
    """ @breif SIGUSR1 signal handler for killing the child process from 
    parent on abort """

    child_pid = get_child_pid()

    # Handle SIGUSR1 only if a child exists
    if child_pid != None:
        print('Cleaning up: killing child %d.' % get_child_pid())
        os.kill(get_child_pid(), signal.SIGINT)
    sys.exit(0)

def list_open_fd():
    os.close(512)

    pid = os.getpid()
    fd_path = '/proc/' + str(pid) + '/fd'
    fd_dir = os.listdir(fd_path)


    get_tgt = lambda name : os.readlink(os.path.join(fd_path, name))
    
    for f in fd_dir:
        try:
            print(f + ' -> ' + get_tgt(f))
        except FileNotFoundError:
            print(f + ' ~>')

    subprocess.call(' '.join(['ls', '-la', fd_path]), shell=True)

    return fd_dir

def except_hook(exctype, value, tb):
    tb_fmt = traceback.format_exception(exctype, value, tb)[1:-1]
    
    # Too many open files
    if '[Errno 24]' in str(value):
        print('Open files:')
        list_open_fd()

    common.abort('Exception raised: ' + exctype.__name__ + ': ' + str(value), 
                    tb_fmt=tb_fmt)

def write_child_pid(args, pid):
    global prg_args 
    prg_args = args
    with open(os.path.join(args.outdir, '@child_pid'), 'w') as obj:
        obj.write(str(pid))

def get_child_pid():
    result = None

    if prg_args != None:
        with open(os.path.join(prg_args.outdir, '@child_pid'), 'r') as obj:
            result = int(obj.readline().strip())
    
    return result

def collect_statistics(cfg, args):
    time.sleep(1)
    if args.progress_file != None and os.path.isfile(args.progress_file):
        os.remove(args.progress_file)

    last_stage, last_iterid = 1, 1

    event_f = args.progress_file + '.events'
    with open(event_f, 'w') as obj:
        obj.write('')

    # Keeps track of if the tracking has started
    started = False
    while True:
        try:
            pmfuzz_d        = args.outdir
            pmfuzzdir_list  = os.listdir(pmfuzz_d)
    
            stages = {}
            dedupdir_list = []
            for d in pmfuzzdir_list:
                if d.startswith('stage'):
                    stage, iter_id = nh.get_stage_inf(d)

                    if stage not in stages:
                        stages[stage] = []
                    
                    stages[stage].append(iter_id)
                elif d == '@dedup':
                    dedupdir_list = os.listdir(os.path.join(pmfuzz_d, d))

            tc_total_inc    = 0
            tc_total_inc_pm = 0

            if len(stages) > 0:
                stage_max       = max(stages.keys())
                iterid_max      = max(stages[stage_max])
                tc_total_inc    = wu.get_inclusive_tc_cnt(pmfuzz_d, stage_max, 
                                    iterid_max, nh.is_tc)
                tc_total_inc_pm = wu.get_inclusive_tc_cnt(pmfuzz_d, stage_max, 
                                    iterid_max, nh.is_pm_map)

                if stage_max != last_stage or iterid_max != last_iterid:
                    wu.record_stage_transitions(args, stage_max, iterid_max)
                    last_stage, last_iterid = stage_max, iterid_max

            tc_total    = len(list(filter(nh.is_tc, dedupdir_list))) \
                            + tc_total_inc
            pm_tc_total = len(list(filter(nh.is_pm_map, dedupdir_list))) \
                            + tc_total_inc_pm
            total_paths = wu.get_total_paths(pmfuzz_d, stage_max, iterid_max)
            total_pm_paths \
                = wu.get_total_pm_paths(pmfuzz_d, stage_max, iterid_max)
            exec_rate = wu.get_exec_rate(cfg, pmfuzz_d)
            exec_rate = wu.get_exec_rate(cfg, pmfuzz_d)
            master_q_tc_total = wu.get_mqueue_population(cfg, pmfuzz_d)

            started = True

            wu.record_progress(
                args, tc_total, pm_tc_total, total_paths, total_pm_paths, 
                exec_rate, master_q_tc_total
            )
        except FileExistsError as e:
            if not started:
                wu.record_progress(args, 0, 0, 0, 0, 0, 0)
            pass
        except FileNotFoundError as e:
            if not started:
                wu.record_progress(args, 0, 0, 0, 0, 0, 0)
            pass
        except Exception as e:
            traceback.print_exc()
        time.sleep(args.progress_interval)
    
def perform_checks():
    """ @brief Performs a series of checks to make sure basic AFL requirements
    are met 
    @return None
    """
    
    # Check for core dump notification
    printi('Checking for core dump notification')
    with open('/proc/sys/kernel/core_pattern', 'r') as obj:
        content = obj.read().strip()
        if content != 'core':
            print()
            printi('Run "sudo bash -c \'echo core >/proc/sys/kernel/core_pattern\'"', 
                format_path=False)
            common.abort('Incorrectly configured core dump notifications')

    # Check if ASLR is enabled
    printi('Checking for ASLR')
    with open('/proc/sys/kernel/randomize_va_space', 'r') as obj:
        content = obj.read().strip()
        if content != '0':
            print()
            printi('Run "sudo bash -c \'echo 0 >/proc/sys/kernel/randomize_va_space\'"', 
                format_path=False)
            common.abort('ASLR should be disabled for image deduplication to work.')

    printi('Checking for Python version')
    PY_MAJOR = sys.version_info[0]
    PY_MINOR = sys.version_info[1]

    if (PY_MAJOR != 3 or PY_MINOR < 6):
        common.abort("Python 3.6+ required.")

def get_argument_parser():  
    parser = argparse.ArgumentParser(prog=PROG_NAME, description=DESC_STR, 
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     add_help=False)

    # Required positional arguments
    reqPos = parser.add_argument_group('Required positional arguments')

    reqPos.add_argument('indir', type=str,
                        help='path to directory containing initial test corpus'
                            + ' for stage 1')
    reqPos.add_argument('outdir', type=str,
                        help='path to directory for generated test cases for '
                            + 'stage 1, works as input for stage 2')
    reqPos.add_argument('config', type=str,
                        help='Points to the config file to use, should' \
                                + ' conform to: configs/default.yaml')

    optNam = parser.add_argument_group('Optional named arguments')

    # Optional arguments/switches
    optNam.add_argument('-h', '--help', action='help', 
                        default=argparse.SUPPRESS,
                        help='show this help message and exit')
    optNam.add_argument('--force-resp', nargs=1, type=str, default=None,
                        help='Forces response to questions')
    optNam.add_argument('--cores-stage1', '-c1', type=int, nargs=1, 
                        default=None, help='Maximum cores stage 1 fuzzer '+\
                        'can use, default: 1. Can be specified in config.')
    optNam.add_argument('--cores-stage2', '-c2', type=int, nargs=1, 
                        default=None, help='Maximum cores stage 2 fuzzer '+\
                        'can use, default: 1. Can be specified in config.')
    optNam.add_argument('--overwrite', '-o', action='store_true',
                        help='Overwrite the output directory')
    optNam.add_argument('--disable-stage2', '-1', action='store_true', 
                        default=None,
                        help='Disables stage 2.  Can be specified in config.')
    optNam.add_argument('--dry-run', action='store_true',
                        help='Enables dry run, no actual commands are '+\
                        'executed (Deprecated)')
    optNam.add_argument('--progress-interval', type=int, default=0,
                        help='Interval in seconds for recording progress, '\
                        + 'default: 60 seconds.  Can be specified in config.')
    optNam.add_argument('--progress-file', type=str, default=None,
                        help='Output file for writing progress to a file. '\
                        + 'Can be specified in config.')
    optNam.add_argument('--checks-only', action='store_true',
                        help='Performs startup checks and exits')
    optNam.add_argument('--verbose', '-v', action='store_true',
                        help='Enables verbose logging to stdout')
    optNam.add_argument('--version', action='version', version='%(prog)s ' 
                        + VERSION_STR)

    return parser

def get_options():
    """ Returns parsed arguments """

    args, unparsed = get_argument_parser().parse_known_args()

    if (args.cores_stage1 != None) and (args.cores_stage1[0] <= 0):
        parser.error('Core count cannot be less than 1')
    if (args.cores_stage2 != None) and (args.cores_stage2[0] <= 0):
        parser.error('Core count cannot be less than 1')

    if args.verbose:
        print('Argument values:     ')
        print('\tindir:             ', args.indir)
        print('\toutdir:            ', args.outdir)
        print('\tconfig:            ', args.config)
        if args.cores_stage1 != None:
            print('\tcores (stage1):    ', args.cores_stage1[0])
        if args.cores_stage2 != None:
            print('\tcores (stage2):    ', args.cores_stage2[0])
        print('\tdisable stage 2:   ', args.disable_stage2)
        print('\tprogress_interval: ', args.progress_interval)
        print('\tprogress_file:     ', args.progress_file)
        print('\tverbose:           ', args.verbose)
        print('\tforce-resp:        ', args.force_resp)
        print('\tdry-run:           ', args.dry_run)

    return args, unparsed

def update_args_with_cfg(args, cfg):
    """ Update the argument values (if not set) from config """

    if args.cores_stage1 == None:
        args.cores_stage1 = cfg['pmfuzz']['stage']['1']['cores']
    else:
        args.cores_stage1 = args.cores_stage1[0]

    if args.cores_stage2 == None:
        args.cores_stage2 = cfg['pmfuzz']['stage']['2']['cores']
    else:
        args.cores_stage2 = args.cores_stage2[0]

    if args.disable_stage2 == None:
        args.disable_stage2 = not cfg['pmfuzz']['stage']['2']['enable']

    if args.progress_interval == 0:
        args.progress_interval = int(cfg['pmfuzz']['progress_interval'])

    if args.progress_file == None:
        args.progress_file = cfg['pmfuzz']['progress_file']

    if args.force_resp == None:
        args.force_resp = cfg['pmfuzz']['force_resp']
    else:
        args.force_resp = args.force_resp[0]

def main():
    global parent
    global child_pid

    # Register signal handlers
    signal.signal(signal.SIGINT, sigint_handler)
    signal.signal(signal.SIGUSR1, sigusr1_handler)
    
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

    # Update arguments from config
    update_args_with_cfg(args, cfg)

    # Update rest of the args
    cores1          = args.cores_stage1
    cores2          = args.cores_stage2
    force_resp      = args.force_resp
    dry_run         = args.dry_run
    tgtcmd          = cfg.tgtcmd

    if verbose:
        printv('Updated arguments:')
        printoff(
            "cores1      = " + str(args.cores_stage1) + '\n' + \
            "cores2      = " + str(args.cores_stage2) + '\n' + \
            "force_resp  = " + str(args.force_resp) + '\n' + \
            "dry_run     = " + str(args.dry_run) + '\n' + \
            "disable_st2 = " + str(args.disable_stage2) + '\n' + \
            "prg_file    = " + str(args.progress_file) + '\n' + \
            "tgtcmd      = " + str(cfg.tgtcmd) + '\n' + \
            "prg_int     = " + str(args.progress_interval) + '\n'
        )

    printi('PID: ' + str(os.getpid()))

    # Print out the config
    if verbose:
        printv('Contents: ')
        printoff(str(cfg), CBEIGE2)

    # Check for image marker in the target command
    pm_img_marker = False
    for keywrd in tgtcmd:
        if common.PM_IMG_MRK in keywrd:
            pm_img_marker = True 
    
    if not pm_img_marker:
        parser.error('--wrkld-cmd option needs the marker ' + common.PM_IMG_MRK
                    + ' to mark location of the pool image. e.g., '
                    + '/mnt/pmem0/__POOL_IMAGE__')

    if force_resp != None:
        force_resp = force_resp[0]

    # Overwrite the output directory
    if os.path.isdir(args.outdir):
        printw('Overwriting output directory: ' + args.outdir)
        shutil.rmtree(args.outdir)
    elif os.path.isfile(args.outdir):
        printw('Overwriting output directory: ' + args.outdir)
        os.remove(args.outdir)
    
    os.makedirs(args.outdir)

    perform_checks()
    if args.checks_only:
        printi('All checks completed')
        exit(0)

    # Fork here to run pmfuzz in one thread and statistics collection in the 
    # other thread
    pid = os.fork()
    
    if pid != 0: # Run pmfuzz
        write_child_pid(args, pid)
        pmfuzz.run_pmfuzz(args.indir, args.outdir, cfg, cores1=cores1,
                            cores2=cores2, verbose=verbose, force_yes=force_resp, 
                            dry_run=dry_run, disable_stage2=args.disable_stage2)
    else: # Run statistics collection
        parent = False
        collect_statistics(cfg, args)

if __name__ == '__main__':
    main()
