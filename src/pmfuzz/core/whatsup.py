import argparse
import bitarray
import matplotlib
import numpy as np
import os
import pandas as pd
import plotext.plot as plx
import psutil
import shutil
import subprocess
import time

from matplotlib import pyplot as plt
from subprocess import Popen, PIPE

from helper import common

from helper.prettyprint import *
from handlers import name_handler as nh

def get_phys_count():
    process = Popen(['lscpu'], stdout=PIPE)
    (output, err) = process.communicate()

    sockets = None
    cores_per_socket = None
    threads_per_core = None

    for line in output.decode("utf-8").split('\n'):
        tkns = line.split(':')

        for i in range(len(tkns)):
            tkns[i] = tkns[i].strip()

        if 'Socket(s)' in tkns[0]:
            sockets = int(tkns[1])
        elif 'Core(s) per socket' in tkns[0]:
            cores_per_socket = int(tkns[1])
        elif 'Thread(s) per core' in tkns[0]:
            threads_per_core = int(tkns[1])

    return (sockets, cores_per_socket, threads_per_core)

def get_cumulative_map(tcdir, filt, rename):
    """ @brief Gets the combined bitmap for all the testcases in a dir
    
    @param tcdir Complete path to a directory containing paths
    @param filt Use filter on the directory
    @param rename Renames the testcase (useful for PM paths)
    @return BitArray object containing the merged bitmap
    """
    pmfuzzdir_list = os.listdir(tcdir)

    cumulative = None
    for f in filter(filt, pmfuzzdir_list):
        file_path = os.path.join(tcdir, rename(f))

        if cumulative == None:
            with open(file_path, 'rb') as obj:
                cumulative = bitarray.bitarray()
                cumulative.fromfile(obj)
        else:
            with open(file_path, 'rb') as obj:
                cur = bitarray.bitarray()
                cur.fromfile(obj)

                # Combine the maps
                cumulative = cumulative|cur

    return cumulative

def combine_maps(*maps):
    """ @brief Combines maps while ignoring any None values 
    @return BitArray object with all maps combined """

    common.abort_if(len(maps) < 1, 'No map supplied')
    cumulative = maps[0]
    
    for m in maps[1:]:
        if m != None:
            cumulative = cumulative|m

    return cumulative

def count_tuples(map):
    """ @brief counts non zero tuples in a map
    @param map BitArray containing the bitmap
    @return Count of non-zero bytes in the bitmap"""

    count = 0
    
    if map != None:
        for bit in map.tobytes():
            if bit != 0:
                count += 1
    
    return count

def get_total_paths(pmfuzzdir, stage_max, iterid_max):
    total_paths = count_tuples(combine_maps(
        get_cumulative_map(
            os.path.join(pmfuzzdir, '@dedup'), 
            nh.is_map, lambda fname: fname
        ),
        # Incase this is None, it is ignored in combine_maps
        get_inclusive_map(
            pmfuzzdir, stage_max, iterid_max, 
            nh.is_map, lambda fname: fname
        ),
    ))

    return total_paths

def get_total_pm_paths(pmfuzzdir, stage_max, iterid_max):
    total_pm_paths = count_tuples(combine_maps(
        get_cumulative_map(
            os.path.join(pmfuzzdir, '@dedup'), 
            nh.is_pm_map, lambda fname: fname.replace('pm_', '')
        ),
        # Incase this is None, it is ignored in combine_maps
        get_inclusive_map(
            pmfuzzdir, stage_max, iterid_max, 
            nh.is_pm_map, lambda fname: fname.replace('pm_', '')
        ),
    ))

    return total_pm_paths

def get_mqueue_population(cfg, pmfuzzdir):
    tgtdir = os.path.join(pmfuzzdir, 'stage=1,iter=1', '.afl-results', 
        'master_fuzzer', 'queue')

    count = 0
    for file in os.listdir(tgtdir):
        if file.startswith('id:'):
            count += 1

    return count
    

def get_exec_rate(cfg, pmfuzzdir):
    tgtdir = os.path.join(pmfuzzdir, 'stage=1,iter=1', '.afl-results')
    whatsup_cmd = [cfg['pmfuzz']['bin_dir'] + '/afl-whatsup', '-s', tgtdir]
    whatsup_res = subprocess.check_output(whatsup_cmd).decode("utf-8")
    speed = '0'
    for line in whatsup_res.split('\n'):
        if 'Cumulative' in line:
            tokens = line.split(':')
            speed = tokens[1].split()[0]
    return speed

def record_progress(args, total_tc, total_pm_tc, total_paths, total_pm_paths, exec_rate, mq_pop):
    if args.progress_file != None:
        # Create the file
        if not os.path.isfile(args.progress_file):
            with open(args.progress_file, 'w') as obj:
                obj.write('')

        interval = args.progress_interval

        tail_cmd    = ['tail', '-1', args.progress_file]
        last_line   = subprocess.check_output(tail_cmd).decode("utf-8")
        
        last_write  = last_line.split(',')[0]

        if last_write.strip() == '':
            last_write = 0
        else:
            last_write = int(last_write)

        cur_time    = int(time.time())

        if (cur_time - last_write) < 0:
            common.abort('Corrupted progress file: ' + args.progress_file)

        if (cur_time - last_write) > interval:
            with open(args.progress_file, 'a') as obj:
                obj.write(str(cur_time) + ',' + str(total_tc) + ',' \
                    + str(total_pm_tc) + ',' + str(total_paths) + ','\
                    + str(total_pm_paths) + ',' + str(exec_rate) + ','\
                    + str(mq_pop) + '\n')

def record_stage_transitions(args, stage, iterid):
    if args.progress_file != None:
        event_f     = args.progress_file + '.events'
        cur_time    = int(time.time())

        # Create the file
        if not os.path.isfile(event_f):
            with open(event_f, 'w') as obj:
                obj.write('')

        with open(event_f, 'a') as obj:
            obj.write(str(cur_time)+','+str(stage)+','+str(iterid)+'\n')

def plot(progress_file, to_stdout=True, to_img=True, title='Progress plot'):
    if progress_file != None:
        df = pd.read_csv(progress_file, 
                names=['tc_total', 'pm_tc_total', 'total_path', 'total_pm_paths'])
        events_df = pd.read_csv(progress_file + '.events', 
                names=['stage', 'iterid'])
                
        divide_factor = 1
        scale = 'seconds'

        events_df.index = (events_df.index - np.min(df.index))
        df.index        = (df.index - np.min(df.index))
        interval        = np.max(df.index)

        # Scale the x-axis
        if interval > 60*60*24*2: # 2 days
            divide_factor = 60*60*24
            scale = 'days'
        elif interval > 60*60*2: # 2 hours
            divide_factor = 60*60
            scale = 'hours'
        elif interval > 0: # 0 minute
            divide_factor = 60
            scale = 'minutes'

        w, h = plx.get_terminal_size()
        
        rolling_window = 4
        N = rolling_window

        if len(events_df) != 0:        
            events_df.index = events_df.index/divide_factor
        x = np.float_(df.index)
        x = x[:-rolling_window+1]
        y = np.float_(df['tc_total'])
        y = np.convolve(y, np.ones((N,))/N, mode='valid')

        if to_img:
            # Configure Matplotlib and figure
            matplotlib.use('Agg')
            matplotlib.rcParams.update({'font.size': 22})

            plt.figure(figsize=(20,10))
            ax = plt.gca()

            # Plot stuff
            plt.plot(x/divide_factor, y, label='All Paths', zorder=3)
            ax.set_ylim(0,np.max(y)*1.2)

            # Get axis dimensions
            xmin, xmax, ymin, ymax = plt.axis()

            # Plot stage transitions
            cnt = 0
            for index, row in events_df.iterrows():
                plt.axvline(x=index, linestyle='-', color='black', linewidth=0.1)

                # Plot label for only the last entry
                if cnt == (len(events_df)-1):
                    plt.text(index+xmax*0.025, ymax*0.92, ' Stage %s, Iter %s ⟶ ' % (row[0], row[1]))
                cnt += 1
            
            plt.grid()
            plt.legend(loc='best')
            
            plt.title(title)

            ax.set_xlabel('Time elapsed (%s)' % scale)

            plt.savefig('progress.pdf')
            plt.savefig('progress.png')
            plt.savefig('progress.svg')

        if len(x) > 100:
            x = x[len(x)%100:]/divide_factor
            y = y[len(y)%100:]
            
            x = x.reshape((-1, int(len(x)/100))).mean(axis=1)
            y = y.reshape((-1, int(len(y)/100))).mean(axis=1)

        if to_stdout:
            print()
            print('PC Path Plot')
            print('============')

            print('_'*w)
            print(' ')
            plx.scatter(
                x, 
                y, 
                line=True, 
                cols=w, 
                rows=int(0.3*h), 
                axes=True,
                axes_color='blue',
            )
            plx.show()
            print('X units = ' + scale)

def get_inclusive_map(pmfuzz_d, cur_stage, cur_iterid, filt, rename):
    """ @brief Returns the cumulative map for the currently running stage, 
    returns 0 if the currently running stage is stage 1"""
    cumulative = None

    if cur_stage != 1:
        stage_d = nh.get_outdir_name(cur_stage, cur_iterid)
        testcase_d = os.path.join(pmfuzz_d, stage_d, 'testcases')
        
        cumulative = get_cumulative_map(testcase_d, filt, rename)
    return cumulative

def get_inclusive_tc_cnt(pmfuzz_d, cur_stage, cur_iterid, filt):
    """ @brief Returns the total count of testcases for the currently 
    running stage, returns 0 if the currently running stage is stage 1
    @param pmfuzz_d
    @param cur_stage
    @param cur_iterid
    @param filt"""
        
    count = 0

    if cur_stage != 1:
        stage_d = nh.get_outdir_name(cur_stage, cur_iterid)
        testcase_d = os.path.join(pmfuzz_d, stage_d, 'testcases')
        
        for fname in filter(filt, os.listdir(testcase_d)):
            count += 1

    return count
