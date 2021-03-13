""" 
@file       failureinjection.py
@details    TODO
@copyright  2020-21 PMFuzz Authors

SPDX-license-identifier: BSD-3-Clause
"""
import os
import subprocess
import sys
import tempfile

import handlers.name_handler as nh

from helper.common import abort
from helper.common import abort_if
from helper.common import exec_shell
from helper.common import translate_exit_code
from helper.prettyprint import printv

def get_failure_inj_env(cfg, create):
    env:dict = {}

    env = cfg('target.env')
    if create:
        env.update(cfg('pmfuzz.failure_injection.img_gen_mode.create_env'))
    else:
        env.update(cfg('pmfuzz.failure_injection.img_gen_mode.dont_create_env'))

    return env

def gen_failure_inj_cmd(cfg, tgtcmd, imgpath, create, verbose=False):
    """ @brief Generates an target only command using configuration and parameters
    
    @Return A tuple with enivronment and cmd for afl-cmin parameters """

    env: dict = get_failure_inj_env(cfg, create)
    
    _, tgtcmd_loc = nh.set_img_path(list(tgtcmd), imgpath, cfg)

    cmd: List = tgtcmd_loc

    return (env, cmd)

def run_failure_inj(cfg, tgtcmd, imgpath, testcase_f, clean_name, 
        create, verbose=False):
    """ @brief Run failure injection on an image 
    @param create If true, inject the failure to the process of creating the
                  image
    @return None"""

    if not create and not os.path.isfile(imgpath):
        abort('Image path %s does not exist' % imgpath)

    env, cmd = gen_failure_inj_cmd(cfg, cfg.tgtcmd, imgpath, create, verbose)
    env.update({"FI_IMG_SUFFIX": clean_name.replace('.testcase', '')})

    if verbose:
        printv('Failure Injection:')
        printv('%20s : %s' % ('env', str(env)))
        printv('%20s : %s' % ('cmd', ' '.join(cmd)))
        printv('%20s : %s' % ('stdin', testcase_f))
        

    fd, out_file = tempfile.mkstemp(prefix='pmfuzz-img-gen-out-')
    printv('Redirecting output to ' + out_file)

    exit_code = None
    with open(out_file, 'w') as stdout, open(testcase_f, 'r') as stdin:
        exit_code = exec_shell(
            cmd     = cmd,
            stdin   = stdin,
            stdout  = stdout,
            stderr  = subprocess.STDOUT,
            env     = env,
            wait    = True,
            timeout = 30 # Set a generous timeout of 30 seconds so things don't crash
        )
    
    os.close(fd)

    descr_str, success = translate_exit_code(exit_code)
    if not success:
        abort('Failure injection for pid %d failed: %s' \
            % (os.getpid(), descr_str))