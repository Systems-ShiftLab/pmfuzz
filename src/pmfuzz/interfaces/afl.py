""" 
@file       afl.py
@details    TODO
@copyright  2020-21 University of Virginia

SPDX-license-identifier: BSD-3-Clause
"""
import os
import tempfile

from io import StringIO
from itertools import chain
from glob import glob

from helper.common import *
from handlers import name_handler as nh

def get_fuzzer_stats(outdir):
    result = (chain.from_iterable(glob(x[0] + '/fuzzer_stats', recursive=True) for x in os.walk(outdir)))
    return result

def gen_afl_cmd(indir:str, outdir:str, cfg:dict, tgtcmd:list, slave:bool=False, 
                coreid:int=0, persist_tgt:bool=False, verbose:bool=False):
    """ @brief Generates an AFL command using configuration and parameters 
    
    @return A tuple with enivronment and cmd for give afl parameters """

    env: dict = cfg.get_env(persist=False)

    prioritize_pm_path = cfg('afl.prioritize_pm_path.enable')
    ppp_env = None
    if prioritize_pm_path:
        ppp_env = cfg('afl.prioritize_pm_path.env.enable').split('=')
    else:
        ppp_env = cfg('afl.prioritize_pm_path.env.disable').split('=')
    
    env.update({ppp_env[0]: ppp_env[1]})
    
    afl_bin     = [os.path.join(cfg('pmfuzz.bin_dir'), 'afl-fuzz')]
    afl_indir   = ['-i', indir]
    afl_outdir  = ['-o', outdir]
    afl_tmout   = ['-t', cfg('target.tmout')]
    afl_mlimit  = ['-m', cfg('target.mlimit')]
    afl_srand   = ["-s", "1024"]
    afl_name    = []

    if slave:
        afl_name = ['-S', 'slave_fuzzer_' + str(coreid)]
    else:
        afl_name = ['-M', 'master_fuzzer']

    fuzz_tgt    = ["--"] + tgtcmd

    cmd: List = afl_bin + afl_indir + afl_outdir + afl_srand + afl_tmout \
                + afl_mlimit + afl_name + fuzz_tgt

    return (env, cmd)

def gen_afl_tmin_cmd(indir, outdir, cfg, tgtcmd, persist_tgt=False, 
        verbose=False):
    """ @brief Generates an afl-tmin command using configuration and parameters
    
    @Return A tuple with enivronment and cmd for afl-tmin parameters """

    env: dict = cfg.get_env(persist=persist_tgt)

    afl_bin     = [os.path.join(cfg['pmfuzz']['bin_dir'], 'afl-tmin')]
    afl_indir   = ['-i', indir]
    afl_outdir  = ['-o', outdir]
    afl_tmout   = ['-t', cfg['target']['tmout']]
    afl_mlimit  = ['-m', cfg['target']['mlimit']]


    fuzz_tgt    = ["--"] + tgtcmd

    cmd: List = afl_bin + afl_indir + afl_outdir + afl_tmout \
                + afl_mlimit + fuzz_tgt

    return (env, cmd)

def gen_afl_cmin_cmd(indir, outdir, cfg, tgtcmd, verbose=False, mapdir=None):
    """ @brief Generates an afl-cmin command using configuration and parameters
    
    @Return A tuple with enivronment and cmd for afl-cmin parameters """

    cur_env = os.environ.copy()
    env: dict = cfg.get_env(persist=False)
    env['AFL_KEEP_TRACES'] = '1'
    cur_env.update(env)
    
    afl_bin     = [cfg('afl.cmin')]
    afl_indir   = ['-i', indir]
    afl_outdir  = ['-o', outdir]
    # afl_cfgdir  = ['-c', cfgdir] # Parameter for modified afl-cmin
    afl_tmout   = ['-t', cfg['target']['tmout']]
    afl_mlimit  = ['-m', cfg['target']['mlimit']]
    afl_mapdir  = ['']
    afl_cp_map  = ['']

    if mapdir != None:
        afl_mapdir  = ['-M', mapdir]
        afl_cp_map  = ['-c', cfg('afl.cpmap')]

    fuzz_tgt    = ["--"] + tgtcmd

    cmd: List = afl_bin + afl_indir + afl_outdir + afl_tmout \
                + afl_mlimit + afl_mapdir + afl_cp_map + fuzz_tgt

    return (cur_env, cmd)

def gen_tgt_img(tgtcmd:list, cfg, verbose:bool=False):
    """ @brief Generate a target image """

    tgtcmd_loc = list(tgtcmd)

    env = cfg.get_env(persist=True)
    fd, tempf = tempfile.mkstemp(prefix='pmfuzz-gen-tgt-img-')

    stdin = os.devnull
    # Create the command file for generating empty image
    if 'empty_img' in cfg['target']:
        content = cfg['target']['empty_img']['stdin'] + '\n'
        fd_stdin, stdin = tempfile.mkstemp(prefix='pmfuzz-temp-input-')
        os.close(fd_stdin)

        with open(stdin, 'w') as stdin_obj:
            stdin_obj.write(content)

    if verbose:
        printv('Image generation:')
        printv('%20s : %s' % ('env', str(env)))
        printv('%20s : %s' % ('input', stdin))
        printv('%20s : %s' % ('cmd', ' '.join(tgtcmd_loc)))

    if verbose:
        printv('Writing run output to ' + tempf)

    with open(tempf, 'w') as stdout, open(stdin, 'r') as stdin:
        exec_shell(
            cmd         = tgtcmd_loc,
            stdin       = stdin,
            stdout      = stdout,
            stderr      = subprocess.STDOUT,
            env         = env,
            wait        = True,
            timeout     = 30 # Set a generous timeout of 30 seconds so things don't crash
        )

    stdin.close()
    os.close(fd)

def run_afl(indir:str, outdir:str, tgtcmd:list, cfg:dict, cores:int=1, 
            verbose:bool=False, persist_tgt=False, dry_run=False, gen_img=True):
    """ @brief Run AFL """

    pids = []
    for coreid in range(cores):
        fd, imgname = tempfile.mkstemp(prefix='pmfuzz-tmp-img-', 
            dir=cfg['pmfuzz']['img_loc'])
        os.close(fd)
        os.remove(imgname)

        # Generate the target image
        tgtcmd_loc = list(tgtcmd)

        for tgtcmd_iter in range(len(tgtcmd_loc)):
            if PM_IMG_MRK in tgtcmd_loc[tgtcmd_iter]:
                tgtcmd_loc[tgtcmd_iter] = tgtcmd_loc[tgtcmd_iter] \
                    .replace(PM_IMG_MRK, imgname)

        if gen_img:
            printi('Generating an image')
            gen_tgt_img(tgtcmd_loc, cfg, verbose=verbose)
            
        tf = tempfile.NamedTemporaryFile(prefix='pmfuzz-out.', delete=False)

        slave: bool = False
        fuzzer_name:str = ''
        if coreid == 0:
            slave = False
            fuzzer_name = 'master_fuzzer'
        else:
            slave = True
            fuzzer_name = 'slave_fuzzer_' + str(coreid)

        env, cmd = gen_afl_cmd(indir, outdir, cfg, tgtcmd_loc, slave, 
                                coreid=coreid, persist_tgt=False, verbose=verbose)
        
        tf.write(bytearray('Output from coreid %d\nenv:%s\ncmd:%s\n' 
                    % (coreid, str(env), str(cmd)), encoding='ascii'))
        tf.flush()
        
        if verbose:
            printv('Generations for core %d:' % coreid)
            printv('\tEnvironment:               ' + str(env))
            printv('\tCommand:                   ' + ' '.join(cmd))
            printv('\tReading testcases from:    ' + indir)
            printv('\tWriting testcases to:      ' + outdir)

        if not dry_run:
            pid = exec_shell(cmd=cmd, stdout=tf, stderr=tf, env=env)
            pids.append(pid)
            printi('Writing output to: '+ tf.name + ' for core ' + str(coreid) + ' (' + fuzzer_name + '), pid = ' + str(pid))
            
            # Wait 5 seconds between invocations to avoid multiple afl binding
            # to a single core
            if coreid != 0:
                time.sleep(5)
            else:
                time.sleep(1)

            # Write the PID to file 'pid'
            pid_f = os.path.join(outdir, fuzzer_name, 'pid')
                
            with open(pid_f, 'w') as fobj:
                fobj.write(str(pid))
                
            if verbose:
                printv('Writting pid to ' + pid_f)

    return pids

def run_afl_tmin(in_tc, out_tc, tgtcmd, cfg, verbose=False, persist_tgt=False, 
        dry_run=False):
    """ @brief Run AFL tmin """

    create_temp = tempfile.NamedTemporaryFile

    with create_temp(prefix='pmfuzz-out.', delete=False) as tf:    
        tgtcmd_loc = list(tgtcmd)

        env, cmd = gen_afl_tmin_cmd(in_tc, out_tc, cfg, tgtcmd_loc, 
                        persist_tgt=False, verbose=verbose)
        
        tf.write(bytearray('Output for afl-tmin:\nenv:%s\ncmd:%s\n' \
                    % (str(env), str(cmd)), encoding='ascii' + \
                    '\n-------------\n\n'))
        tf.flush()

        if verbose:
            printv('Generations afl-tmin:        ')
            printv('\tEnvironment:               ' + str(env))
            printv('\tCommand:                   ' + ' '.join(cmd))
            printv('\tReading testcases from:    ' + in_tc)
            printv('\tWriting testcases to:      ' + out_tc)

        if not dry_run:
            printi('(Sync) Writing output to: '+ tf.name)
            exec_shell(cmd=cmd, stdout=tf, stderr=tf, env=env, wait=True)

def run_afl_cmin(indir, pmfuzzdir, tgtcmd, cfg, verbose=False, 
        dry_run=False, mapdir=None):
    """ @brief Run AFL cmin 
    Returned minimized corpus needs to be manually cleanedup.

    @param indir Path to dir containing input corpus
    @param pmfuzzdir Path to the pmfuzz result directory
    @param tgtcmd
    @param cfg
    @param cfgdir Directory containing command for each testcase
    @param verbose
    @param dry_run

    @return Path to the output directory containing minimized corpus"""

    tmpdir      = path.join(pmfuzzdir, '@temp') 
    
    create_temp = tempfile.NamedTemporaryFile
    outdir = tempfile.mkdtemp(dir=tmpdir, prefix='cmin-out-')

    with create_temp(prefix='pmfuzz-out.', delete=False) as tf:    
        env, cmd = gen_afl_cmin_cmd(
            indir=indir, 
            outdir=outdir, 
            cfg=cfg, 
            tgtcmd=list(tgtcmd), 
            # cfgdir=cfgdir,
            verbose=verbose,
            mapdir=mapdir,
        )

        tf.write(bytearray('Output for afl-cmin:\nenv:%s\ncmd:%s\n' \
                    % (str(env), str(cmd)), encoding='ascii' + \
                    '\n-------------\n\n'))
        tf.flush()

        if verbose:
            printv('Generations afl-cmin:        ')
            printv('\tEnvironment:               ' + str(env))
            printv('\tCommand:                   ' + ' '.join(cmd))
            printv('\tReading testcases from:    ' + indir)
            printv('\tWriting testcases to:      ' + outdir)
            printv('\tRun output to:             ' + tf.name)

        if not dry_run:
            printi('(Sync) Writing output to: '+ tf.name)
            cObj = exec_shell(cmd=cmd, stdout=tf, stderr=tf, env=env, wait=True)
            exit_code_descr, success = translate_exit_code(cObj)
            abort_if(not success, 'afl-cmin: ' + exit_code_descr)
            
    return outdir