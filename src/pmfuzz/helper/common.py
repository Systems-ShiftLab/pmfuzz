""" @file common.py 

@brief Contains comman routines like abort, ask_yn... """

import dateutil.relativedelta
import hashlib
import os
import random
import subprocess
import signal
import sys
import time
import tempfile
import traceback

from collections import namedtuple
from datetime import datetime as dt
from datetime import date
from os import path
from shutil import copy2
from typing import List, Dict, Set

from helper.prettyprint import *

PM_IMG_MRK = '__POOL_IMAGE__'
Workload = namedtuple("Workload", "name binary arguments")
PERSIST_IMG_MRK = '__PERSIST_OPT__'

PERSIST_IMG_MRK_KEEP = '0'
PERSIST_IMG_MRK_DELETE  = '1'

def pid_alive(pid):        
    """ Check For the existence of a unix pid. """

    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

def fmt_stacktrace_ln(line):
    tokens = line.split(',')
    
    # Format filename
    tokens[0] = tokens[0].replace('File ', '')
    tokens[0] = tokens[0].replace('"', '')
    tokens[0] = CYELLOW + tokens[0] + ENDC

    # Format line number
    tokens[1] = tokens[1].replace('line ', '').strip()
    tokens[1] = CVIOLET2 + tokens[1] + ENDC
    
    return tokens[0] + ':' + tokens[1] + tokens[2]

def copypreserve(src, dst):
    """ Preserves metadata on copy """
    
    abort_if(os.path.isdir(dst), 
        f'Destination {dst} should not be a directory')
    copy2(src, dst)

def abort(msg=None, excode=1, tb_fmt=None):
    # print("stack received = ", traceback.format_stack()[-2].split('\n'))
    caller = str(traceback.format_stack()[-2].split('\n')[0].strip())

    print('')
    print(  '\t' + CRED2 + ('%25s' % 'Abort reason: ') + ENDC + str(msg))
    
    stacktrace = None
 
    if tb_fmt != None:
        stacktrace = tb_fmt
    else:
        stacktrace = traceback.format_stack()
    

    first_line = fmt_stacktrace_ln(stacktrace[0].split('\n')[0].strip())
    
    padding = '\t' + (' '*25)

    print('\t' + CRED2 + ('%25s' % 'Stacktrace: ') + ENDC + ' 1 ' + first_line)
    print(padding + '\t' + CGREY + stacktrace[0].split('\n')[1].strip() + ENDC)

    iter = 2
    for stuff in stacktrace[1:]:
        line = fmt_stacktrace_ln(stuff.split('\n')[0].strip())
        print(padding + '%2d '%iter + line)
        print(padding + CGREY + '\t' + stuff.split('\n')[1].strip() + ENDC)
        iter += 1

    # Raise SIGUSR1 to let the initial handler kill all sibling threads only 
    # if a handler is installed
    if signal.getsignal(signal.SIGUSR1) != signal.SIG_DFL:
        os.kill(os.getpid(), signal.SIGUSR1)

def abort_if(cond, msg=None, excode=1):
    if cond:
        abort(msg, excode)

def ask_yn(question, force_resp=None):
    resp = ''
    ques_str = CVIOLET2 + '[?] ' + ENDC + format_paths(question) + ' (y/n)? '
    if force_resp == None:
        while resp not in ['y', 'n']:
            resp = input(ques_str)
            resp = resp.lower().strip()
    else:
        resp = force_resp
        print(ques_str + str(resp))
    return (resp == 'y')

def exec_shell(cmd, stdin=None, stdout=None, stderr=None,
        env=None, cwd=None, wait=False, timeout=None):
    """ @brief Executes a given command with different options 
    
    @param cmd List of string for the command to execute
    @param stdin File handler for command's stdin
    @param stdout File handler for command's stdout
    @param stderr File handler for command's stderr
    @param env Dict with key-value pair of the environment of the target program
    @param cwd Str representing the path of the directory to start the process in
    @param wait Bool indicating to wait for the process to complete execution
    @param timeout int timeout for the process in seconds

    @return int with holding the pid of the process if not waiting, None 
            otherwise
    """

    if timeout != None and float(timeout) < 1:
    	timeout = 1
    	printw('Changing timeout to 1 second')

    printi('--- PMFuzz run info begin ---\n')
    printi('cmd: %s\n' % (' '.join(cmd)))
    printi('env: %s\n' % (str(env)))
    printi('timeout: %s\n' % (str(timeout)))
    printi('---  PMFuzz run info end  ---\n')

    result = None

    exec_f = None
    if wait:
        exec_f = subprocess.call
    else:
        abort_if(timeout != None, 'Timeout not supported with wait=False')
        exec_f = subprocess.Popen

    if cwd != None:
        try: 
            os.makedirs(cwd, exist_ok=True)
        except OSError:
            abort("unable to create %s" % cwd)

    if wait:
        try:
            result = exec_f(cmd, env=env, stdin=stdin, stdout=stdout, \
                stderr=stderr, preexec_fn=os.setpgrp, close_fds=True, 
                timeout=timeout)
        except subprocess.TimeoutExpired:
            printw('Process timed out, setting exit code to 0')
            result = 0 # Currently a timeout results would be same as exit 0
            pass
    else:
        result = exec_f(cmd, env=env, stdin=stdin, stdout=stdout, \
            stderr=stderr, preexec_fn=os.setpgrp, close_fds=True).pid

    return result

def translate_exit_code(exit_code):
    """ @brief Check exit code and convert it to a human readable string
    
    @param exit_code The exit code from a program

    @return tuple containing a human readeable representation of the exit code
            and a boolean value indicating succcess of the exit code, in that
            order
    """
    hr_str = ''
    success = False

    if exit_code == None:
        hr_str = 'Process timed out'
        success = True
    elif exit_code == 0:
        hr_str = 'Process exited with code 0'
        success = True
    elif exit_code < 0:
        signal_name = signal.Signals(abs(exit_code)).name
        hr_str = 'Process exited with Signal ' + signal_name
        success = False
    else:
        hr_str = 'Process exited with a non-zero exit code ' + str(exit_code)
        success = False

    return hr_str, success

def sha256sum(fpath, bs=65536):
    """ @brief returns the sha 256 sum for a file path

    @param fpath Path of the file to calculate hash
    @param bs Block size for calculation
    @return str """

    sha256 = hashlib.sha256()
    with open(fpath, 'rb') as f:
        for block in iter(lambda: f.read(bs), b''):
            sha256.update(block)

    return sha256.hexdigest()

def remove_files(file_list, verbose, warn=False, force=False):
    """@brief Removes multiple files in a single call
    
    @param file_list List of files to remove
    @param warn Warns on every deletion
    @param force Force deletion if file does not exists
    @return None"""

    for file in file_list:
        if path.isfile(file):
            os.remove(file)
            if verbose:
                printv('Deleting ' + file)
                
        elif not force:
            abort('File ' + file + ' does not exists')

def get_compress_cmd(src, dest, verbose):
    src_dir = path.dirname(src)
    src_file = path.basename(src)

    cmd = ['tar', 'vczf', dest, '-C', src_dir, src_file]

    return cmd

def compress(src, dest, verbose, level=6, extra_params=[]):
    """ Compresses a file from src to dest 
    @param src Full path to the source to compress
    @param dest Full path to the destination compressed file
    @param verbose Verbose logging to stdout
    @param level Compression level to use, should belong to [1,9]
    @return None
    """

    cmd = get_compress_cmd(src, dest, verbose) + extra_params

    if verbose:
        printv('Compressing ' + src + ' -> ' + dest)
        printv('Cmd: ' + ' '.join(cmd))

    abort_if(level < 1 or level > 9, 
        'Illegal compression level %d, should ∈ [1,9]' % level)

    env = {
        'GZIP': '-' + str(level),
    }

    subprocess.run(
        cmd, 
        env     = env,
        check   = True, 
        stdout  = subprocess.PIPE, 
        stderr  = subprocess.PIPE,
    )

def get_decompress_cmd(src, dest, verbose):
    dest_dir = path.dirname(dest)

    cmd = ['tar', 'xzf', src, '-C', dest_dir]

    return cmd    

def decompress(src, dest, verbose, verify=False):
    """ Deompresses a file from src to dest 
    @param src Path to the compressed file
    @param dest Path to the decompressed file
    @param verbose Path to the compressed file
    @param verify Bool value indicating if the decompressed file should be 
           checked if it exists
    @return None
    """

    cmd = get_decompress_cmd(src, dest, verbose)

    if verbose:
        printv('Decompressing ' + src + ' -> ' + dest)
        printv('Cmd: ' + ' '.join(cmd))
        
    subprocess.run(
        cmd, 
        check   = True, 
        stdout  = subprocess.PIPE, 
        stderr  = subprocess.PIPE,
        env     = {
            'GZIP':'-f'
        },
    )

    if verify:
        abort_if(not os.path.isfile(dest), 'Dest %s was not created' % dest)

def get_version():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    ver_f = os.path.join(script_dir, '..', '..', '..', 'VERSION')

    ver_data = {}

    with open(ver_f, 'r') as ver_obj:
        for line in ver_obj:

            # Skip comments
            if line.strip().startswith('//'):
                pass
            else:
                tkns = line.strip().split(' "')
                tkns[0] = tkns[0].replace('#define ', '')

                ver_data[tkns[0].strip()] = tkns[1].replace('"', '')

    result = {}

    result['name'] = ver_data['PMFUZZ_NAME']
    result['version'] = ver_data['PMFUZZ_VERSION']
    result['authors'] = ver_data['PMFUZZ_AUTHORS']
    result['bug_loc'] = ver_data['PMFUZZ_BUG_LOC']
    result['website'] = ver_data['PMFUZZ_WEBSITE']

    return result

def write_state(outdir, state):
    state_f = path.join(outdir, '@info', 'currentstate')
    
    with open(state_f, 'w') as obj:
        obj.write(str(state))

            
def epoch_diff_to_human(old_t, new_t):
    dt1 = dt.fromtimestamp(old_t)
    dt2 = dt.fromtimestamp(new_t)
    rd = dateutil.relativedelta.relativedelta(dt2, dt1)

    years_str   = '%d years, '
    months_str  = '%d months, '
    days_str    = '%d days, '
    hours_str   = '%d hours, '
    minutes_str = '%d minutes '

    if new_t - old_t < 60:
        seconds_str = '%d seconds'
    else:
        seconds_str = 'and %d seconds'

    get_seconds = lambda rd: seconds_str % rd.seconds
    get_minutes = lambda rd: minutes_str % rd.minutes + get_seconds(rd)
    get_hours   = lambda rd: hours_str % rd.hours + get_minutes(rd)
    get_days    = lambda rd: days_str % rd.days + get_hours(rd)
    get_months  = lambda rd: months_str % rd.months + get_days(rd)
    get_years   = lambda rd: years_str % rd.years + get_months(rd)

    result = ''
    if rd.years == 0:
        if rd.months == 0:
            if rd.days == 0:
                if rd.hours == 0:
                    if rd.minutes == 0:
                        result = get_seconds(rd)
                    else:
                        result = get_minutes(rd)
                else:
                    result = get_hours(rd)
            else:
                result = get_days(rd)
        else:
            result = get_months(rd)
    else:
        result = get_years(rd)

    return result

def translate(text, conversion_dict, before=lambda _: _):
    """ Translate words from a text using a conversion dictionary

    @brief text The text to be translated
    @brief conversion_dict The conversion dictionary
    @brief before A function to transform the input
    """
    # if empty:
    if not text: return text
    # preliminary transformation:
    before = before or str.lower
    t = before(text)
    for key, value in conversion_dict.items():
        t = t.replace(key, value)
    return t
