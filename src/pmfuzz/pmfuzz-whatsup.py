#! /usr/bin/env python3

import argparse
import bitarray
import os
import psutil
import shutil
import subprocess
import time

from subprocess import Popen, PIPE

from helper import common
from helper.prettyprint import *

from core import whatsup as wu
from handlers import name_handler as nh

PROG_NAME   = common.get_version()['name']
VERSION_STR = common.get_version()['version']
AUTHORS_STR = common.get_version()['authors']
DESC_STR    = PROG_NAME + ': A Persistent Memory Fuzzer, version ' \
            + VERSION_STR + ' by ' + AUTHORS_STR

def parse_args():
    parser = argparse.ArgumentParser(prog=PROG_NAME, description=DESC_STR, 
            formatter_class=argparse.RawDescriptionHelpFormatter,
            add_help=False)

    # Required positional arguments
    reqPos = parser.add_argument_group('Required positional arguments')

    reqPos.add_argument('pmfuzzdir', type=str,
                        help='path to directory where pmfuzz is generating' + \
                            ' output')

    optNam = parser.add_argument_group('Optional named arguments')

    # Optional arguments/switches
    optNam.add_argument('--plot-from', type=str, default=None,
                        help='plot progress from a progress file, cannot be ' \
                                + 'used along with progress record')
    optNam.add_argument('--progress-interval', type=int, default=60,
                        help='interval for recording progress')
    optNam.add_argument('--progress-file', type=str, default=None,
                        help='output file for writing progress to a file')
    optNam.add_argument('-h', '--help', action='help', default=argparse.SUPPRESS,
                        help='show this help message and exit')

    args = parser.parse_args()

    if args.progress_file != None and args.plot != None:
        abort('Plotting and recording progress is not supported, use the pmfuzz' \
                +' flag for recording progress')

    return args

def main():
    args = parse_args()
    pmfuzz_d = args.pmfuzzdir

    pmfuzzdir_list = os.listdir(pmfuzz_d)
    
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

    try:
        stage_max           = max(stages.keys())
        iterid_max          = max(stages[stage_max])
        tc_total            = sum('.min.testcase' in f for f in dedupdir_list)
        tc_total_inc        = wu.get_inclusive_cnt(pmfuzz_d, stage_max, iterid_max)
        pm_tc_total         = sum('pm_map' in f for f in dedupdir_list)
        runtime             = 0
        cpu_usage           = str(psutil.cpu_percent()) + ' %'
        cpu_usage_str       = ''
        load_avgs           = str(os.getloadavg())
        state               = '<unknown>'
        dir_size            = subprocess.check_output(['du','-sh', pmfuzz_d])
        dir_size            = dir_size.split()[0].decode('utf-8')
        disk_usage          = shutil.disk_usage(pmfuzz_d)
        disk_usage_percent  = (disk_usage[1]/float(disk_usage[0]))*100
        dir_size            = dir_size + ' (disk: ' + '%.1f%%)' % disk_usage_percent
        total_paths         = wu.get_total_paths(args.pmfuzzdir, 'map_')
        total_pm_paths      = wu.get_total_paths(args.pmfuzzdir, 'pm_map_')
    except FileNotFoundError as e:
        print('Caught exception: ' + str(e))
        print()
        print('Possible reasons:')
        print('\t1. Fuzzer is not running.')
        print('\t2. Directory path doesn\'t exists.')
        print('\t3. PMFuzz has not constructed all the directories yet.')
        exit(1)

    diff                = float(cpu_usage.replace('%', '').strip())

    phys_count          = wu.get_phys_count()[0]*wu.get_phys_count()[1]
    _, _, threads_per_core = wu.get_phys_count()

    if diff*float(threads_per_core) > 140:
        cpu_usage_str = CRED2 + '(high)' + ENDC
    elif diff*float(threads_per_core) < 60:
        cpu_usage_str = CBLUE2 + '(low)' + ENDC
    else:
        cpu_usage_str = CGREEN2 + '(looks good)' + ENDC

    cpu_usage += ' ' + cpu_usage_str

    with open(os.path.join(pmfuzz_d, '@info', 'starttime'), 'r') as obj:
        starttime = int(obj.read())

        old_t = starttime
        new_t = int(float(time.time()))

        runtime = common.epoch_diff_to_human(old_t, new_t)

    with open(os.path.join(pmfuzz_d, '@info', 'currentstate')) as obj:
        state = str(obj.read().strip())

    FMT         = '%50s : '
    SEPARATOR   = '%50s   %s' % ('', '')

    print(PROG_NAME + ' whatsup tool v' + VERSION_STR + ' by ' + AUTHORS_STR)
    
    print()
    print('Summary stats')
    print('=============')
    print()

    print((FMT + '%s')          % ('Wall clock runtime', runtime))
    print((FMT + '%s')          % ('Total CPU usage', cpu_usage))
    print((FMT + '%s')          % ('Load averages', load_avgs))
    print(SEPARATOR)
    print((FMT + '%s')          % ('Total paths', str(total_paths)))
    print((FMT + '%s')          % ('Total PM paths', str(total_pm_paths)))
    print((FMT + '%s')          % ('Total testcases', str(tc_total) \
                                    + ' minimized'))
    print((FMT + '%s')          % ('Total testcases (inclusive)', 
                                    str(tc_total_inc+tc_total) + ' minimized'))
    print((FMT + '%d (%.2f %%)')% ('Total PM testcases', pm_tc_total, 
                                    pm_tc_total/tc_total*100.0))
    print(SEPARATOR)
    print((FMT + '%d, %d')      % ('Running/last run stage and iter', stage_max, 
                                iterid_max))
    print((FMT + '%s')          % ('Currently', state))
    print(SEPARATOR)
    print((FMT + '%s')          % ('Output dir size', dir_size))
    print((FMT + '%s')          % ('Progress file:', args.progress_file))
    print((FMT + '%s')          % ('Plotting from:', args.plot_from))

    wu.record_progress(args, tc_total, pm_tc_total, total_paths, total_pm_paths)
    wu.plot(args.plot_from, title=('Progress for '+args.pmfuzzdir+'\n'))

if __name__ == '__main__':
    main()