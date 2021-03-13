""" 
@file       stage2.py
@details    TODO
@copyright  2020-21 PMFuzz Authors

SPDX-license-identifier: BSD-3-Clause
"""

from glob import glob
import re
import pickledb
import psutil
import signal
import sys
import time

from enum import IntEnum, unique
from os import path, makedirs, listdir, remove
from random import randrange
from shutil import which, rmtree

import handlers.name_handler as nh
import interfaces.failureinjection as finj

from core.dedupengine import DedupEngine
from helper import config
from helper.common import *
from helper.parallel import Parallel
from helper.ptimer import PTimer
from interfaces.afl import *
from helper.target import Target as tgt
from helper.prettyprint import *
from .dedup import Dedup
from .stage import Stage

class Stage2(Stage):
    """@brief Implements the loop of the fuzzing process"""

    CS_GEN_THRESH = 2

    @unique
    class RunType(IntEnum):
        TC  = int('0b01', 2)
        CS  = int('0b10', 2)
        ALL = int('0b11', 2)

    def __init__(self, stage, iter_id, srcdir, outdir, cfg, cores, 
            verbose, force_resp, dry_run):
        super().__init__('', srcdir, outdir, cfg, cores, verbose, 
                            force_resp, dry_run)

        stageoutdir = path.join(outdir, nh.get_outdir_name(stage, iter_id))

        self.stage      = stage
        self.iter_id    = iter_id
        self.img_dir    = path.join(stageoutdir, Dedup.PM_IMG_DIR)
        self.tc_dir     = path.join(stageoutdir, Dedup.TESTCASE_DIR)

        if verbose:
            printv('Creating stage %d with iter_id %d' % (stage, iter_id))

        # Initialize an instance of Dedup class to manage the global and local
        # dedup directories
        self.dedup = Dedup(stage, iter_id, srcdir, outdir, cfg, cores, 
            verbose, force_resp, dry_run)

        # Create the directories
        outdir = path.join(self.outdir, 
            nh.get_outdir_name(self.stage, self.iter_id), nh.AFL_DIR_NM)

        self.afl_dir = outdir

        try: 
            makedirs(outdir)
        except OSError as e:
            if path.isfile(outdir):
                abort('%s is not a directory.' % outdir)

        self.tc_timeout = cfg['pmfuzz']['stage']['2']['tc_timeout']

    def get_result_dir(self, name):
        """ Returns the path to the queue directory for a run
        @param name str representing the name of the run 
        @return str representing complete path to the queue dir"""
        
        stage_dir = nh.get_outdir_name(self.stage, self.iter_id)
        tc_dir    = path.join(self.outdir, stage_dir, nh.AFL_DIR_NM, \
                        name)
        outdir    = path.join(tc_dir, 'master_fuzzer')

        return outdir
                
    def kill_all(self):
        printi('Killing stage %d, iter %d' % (self.stage, self.iter_id))

        # Create timers for all the testcases
        for testcasepath, imgpath in self.dedup.local_dedup_list:

            # Get the name to construct a timer for the testcase
            testcasename = path.basename(testcasepath)\
                            .replace(self.dedup.EXT_TC, '')

            
            ptimer = PTimer(self.dedup.dedup_dir_loc, 
                                testcasename, self.verbose)
            
            if not ptimer.is_new(): 
                # If the timer was already started
                if ptimer.expired():

                    # Stop this testcase
                    self._terminate_testcase(testcasename, ptimer)

    def terminate(self):
        """ @brief Terminates the current instance of the stage, by organizing 
        all the generated stuff into local directories. 
        @return None """

        self.kill_all()        
        self.collect()
        
    def clear(self):
        """ @brief Deletes all local files associated with this stage. 
        @return None """

        # Generate the name of the directory to delete
        odir_name = nh.get_outdir_name(self.stage, self.iter_id)
        outdir = path.join(self.outdir, odir_name)

        printw('Removing tree: ' + outdir)
        
        # Delete it
        rmtree(outdir)

    def clean_up_uncmpr_lcl(self):
        """ Removes crash sites and uncompressed pm images left from failure
        injection. 
        
        These images are cleaned here to avoid use of locks and state
        awareness among failure injection instances.
        
        @return None"""
        for fname in os.listdir(self.img_dir):
            if fname.endswith(nh.CRASH_SITE_EXT) \
                    or fname.endswith(nh.PM_IMG_EXT):
                fpath = path.join(self.img_dir, fname)
                
                if self.verbose:
                    printw('Removing file %s' % fpath)

                os.remove(fpath)

    def add_cs_hash_lcl(self):
        """ Adds hashes from .hash files in the self.img_dir to the db 
        @return None """

        hash_db = pickledb.load(self.crash_site_db_f, True)

        for fname in filter(nh.is_hash_f, os.listdir(self.img_dir)):
            hash_f = path.join(self.img_dir, fname)

            with open(hash_f, 'r') as hash_obj:
                hash_k = fname.replace('.' + nh.HASH_F_EXT, '')
                hash_v = hash_obj.read().strip()

                abort_if(hash_v.count('\n') != 0, 
                    'Invalid hash value:' + hash_v)

                hash_db.set(hash_k, hash_v)
                hash_db.dump()

                if self.verbose:
                    printv('Updated HashDB %s: %s' % (hash_k, hash_v))
                    printw('Deleting ' + hash_f)

                os.remove(hash_f)

    def get_img_dir(self, testcasename):
        """ Returns the location of the image for a stage 2 run """
        result = path.join(self.cfg['pmfuzz']['img_loc'], 
                    'stage2-input-'+testcasename + '/')
        return result

    def _terminate_testcase(self, testcasename:str, timer):
        """ @brief Terminates a testcase 
        @return None """

        if self.verbose and timer != None:
            time_delta_str = timer.elapsed_hr()
            printv("Time elapsed: {:0>8}".format(time_delta_str))

        write_state(self.outdir, 'Collecting ' + testcasename)

        # Read the pid
        pid     = None
        q_dir   = path.join(self.get_result_dir(testcasename), 'queue')
        pid_f   = path.join(self.get_result_dir(testcasename), 'pid')

        # abort_if(not path.isfile(pid_f), 'PID file not found at ' + pid_f)
        self.printv('Terminating ' + testcasename + ', checking for pid_f at '\
            + pid_f)

        # Kill only if the pid file exists (indicating a running AFL process)
        if path.isfile(pid_f):
            printi('Killing ' + pid_f) 

            with open(pid_f, 'r') as fobj:
                pid = int(fobj.read().strip())

            # Kill the running AFL instance
            os.kill(pid, signal.SIGTERM) # Send signal 9

            # Remove the pid file
            remove(pid_f)     

            # Remove the image file
            self.printv('Removing directory %s' \
                % self.get_img_dir(testcasename))
            rmtree(self.get_img_dir(testcasename))

            printi('Collecting testcases for ' + testcasename) 
            
            core_count = self.cores//2 if self.cores//2 != 0 else 1

            printi('Using %d cores for collecting results' % core_count)

            # Create a parallel object for collecting testcases
            prl_ct = Parallel(
                self.collect_tc, 
                core_count, 
                transparent_io=True, 
                failure_mode=Parallel.FAILURE_EXIT,
                name='Collect TC',
                verbose=self.verbose,
            )
            
            # Create a parallel object for collecting crash sites
            prl_gen_cs = Parallel(
                self.tc_gen_crash_sites,
                core_count, 
                transparent_io=True,
                failure_mode=Parallel.FAILURE_EXIT,
                name='Gen Crash Site',
                verbose=self.verbose,
            )
            
            q_dir_contents = os.listdir(q_dir)
            q_dir_contents = [f for f in q_dir_contents if f.startswith('id')]

            # Collect the generated testcases
            for childtc in q_dir_contents:
                if childtc != '.state':
                    if self.verbose:
                        printv('Collecting %s from the queue directory' \
                            % childtc)
                    exp_img_path = path.join(self.dedup.dedup_dir_gbl, 
                        testcasename + '.pm_pool.tar.gz')
                    abort_if(not os.path.isfile(exp_img_path),
                        'Sanity check: Compressed image ' + exp_img_path + \
                        ' should exist, but is missing.')

                    clean_name = testcasename + ',' + nh.clean_tc_name(childtc)

                    # Run collect_tc()
                    prl_ct.run([q_dir, childtc, clean_name])

                    # Generate crash sites by injecting failures
                    tcdir = path.join(self.afl_dir, path.basename(testcasename))
                    
                    if self.cfg['pmfuzz']['failure_injection']['enable']:
                        tcdir_path = path.join(tcdir, 'master_fuzzer', 
                                        'queue', childtc)

                        randval = randrange(100)
                        if randval < self.CS_GEN_THRESH:
                            prl_gen_cs.run([tcdir_path])
                        else:
                            self.printv('Skipping cs generation'\
                                +f' ({randval} < {self.CS_GEN_THRESH})')

            prl_ct.wait()
            prl_gen_cs.wait()

            printi('Cleaning up local uncompressed images')
            self.clean_up_uncmpr_lcl()
            self.add_cs_hash_lcl()

            #! Disable this: We don't need to deduplicate the maps
            # # Deduplicate testcases with existing results
            # testcases_path = listdir(self.tc_dir)
            # testcases_path = [path.join(self.tc_dir, fname) \
            #                     for fname in testcases_path]
            # DedupEngine(
            #     testcases_path, 
            #     self.verbose, 
            #     checker=nh.is_map
            # ).run()

            lcl_cfg = self.cfg['pmfuzz']['stage']['dedup']['local']
            write_state(self.outdir, 'Minimizing local')
            self.dedup.run(
                fdedup      = True,
                min_tc      = False, # TODO
                min_corpus  = lcl_cfg['minimize_corpus'], 
                gbl         = False
            )

            printi('Killed testcase %s (pid %d).' % (testcasename, pid))
        else:
            self.printv('Did not kill testcase %s.' % (testcasename))
            

    def _terminate_cs(self, csname:str, timer):
        """ @brief Terminates a crash site run
        
        @return None """

        if self.verbose and timer != None:
            time_delta_str = timer.elapsed_hr()
            printv("Time elapsed: {:0>8}".format(time_delta_str))

        write_state(self.outdir, 'Collecting CS ' + csname)

        # Read the pid
        pid     = None
        q_dir   = path.join(self.get_result_dir(csname), 'queue')
        pid_f   = path.join(self.get_result_dir(csname), 'pid')

        # Kill only if the pid file exists (indicating a running AFL process)
        if path.isfile(pid_f):
            printi('Killing ' + pid_f) 

            with open(pid_f, 'r') as fobj:
                pid = int(fobj.read().strip())

            # Kill the running AFL instance
            os.kill(pid, signal.SIGTERM) # Send signal 9

            # Remove the pid file
            remove(pid_f)     

            # Remove the image file
            imgdir = self.cfg['pmfuzz']['img_loc'] + '/'
            imgpm = path.join(imgdir, 'pmfuzz-cs-run-' + csname)
            dir2del = glob(imgpm+'*')
            abort_if(len(dir2del) == 0, 
                'Unable to find anything with glob ' + imgpm + '*')
            abort_if(len(dir2del) > 1, 
                'Too many matches for glob ' + imgpm + '*')
            if self.verbose:
                printv('Removing image %s' % dir2del[0])
            rmtree(dir2del[0])

            # TODO: Move this to a single function for both _terminate_tc and 
            # _terminate_cs

            printi('Collecting testcases for ' + csname) 
            
            core_count = self.cores//2 if self.cores//2 != 0 else 1
            
            printi('Using %d cores for collecting results' % core_count)

            # Create a parallel object for collecting testcases
            prl_ct = Parallel(
                self.collect_tc, 
                core_count, 
                transparent_io=False, 
                failure_mode=Parallel.FAILURE_EXIT,
                name='Collect TC',
                verbose=self.verbose,
            )
            
            # Create a parallel object for collecting crash sites
            prl_gen_cs = Parallel(
                self.tc_gen_crash_sites,
                core_count, 
                transparent_io=False,
                failure_mode=Parallel.FAILURE_EXIT,
                name='Gen Crash Site',
                verbose=self.verbose,
            )
            
            q_dir_contents = os.listdir(q_dir)
            q_dir_contents = [f for f in q_dir_contents if f.startswith('id')]

            # Collect the generated testcases
            for childtc in q_dir_contents:
                if childtc != '.state':
                    if self.verbose:
                        printv('Collecting %s from the queue directory' \
                            % childtc)

                    exp_img_path = nh.get_parent_img(
                        csname + '.' + nh.TC_EXT, 
                        self.dedup.dedup_dir_gbl, 
                        get='exists',
                        isparent=True
                    )
                    abort_if(not os.path.isfile(exp_img_path),
                        'Sanity check: Compressed image ' + exp_img_path + \
                        ' should exist, but is missing.')

                    clean_name = csname + ',' + nh.clean_tc_name(childtc)

                    # Run collect_tc()
                    prl_ct.run([q_dir, childtc, clean_name])

                    # Generate crash sites by injecting failures
                    tcdir = path.join(self.afl_dir, path.basename(csname))
                    
                    if self.cfg['pmfuzz']['failure_injection']['enable']:
                        tcdir_path = path.join(tcdir, 'master_fuzzer', 
                                        'queue', childtc)

                        randval = randrange(100)
                        if randval < self.CS_GEN_THRESH:
                            prl_gen_cs.run([tcdir_path])
                        else:
                            self.printv('Skipping cs generation'\
                                +f' ({randval} < {self.CS_GEN_THRESH})')

            prl_ct.wait()
            prl_gen_cs.wait()

            printi('Cleaning up local uncompressed images')
            self.clean_up_uncmpr_lcl()
            self.add_cs_hash_lcl()

            # Deduplicate testcases with existing results
            testcases_path = listdir(self.tc_dir)
            testcases_path = [path.join(self.tc_dir, fname) \
                                for fname in testcases_path]
            DedupEngine(
                testcases_path, 
                self.verbose, 
                checker=nh.is_map
            ).run()
 
            lcl_cfg = self.cfg['pmfuzz']['stage']['dedup']['local']
            write_state(self.outdir, 'Minimizing local')
            self.dedup.run(
                fdedup      = True,
                min_tc      = False, # TODO
                min_corpus  = lcl_cfg['minimize_corpus'], 
                gbl         = False
            )

            printi('Killed testcase %s (pid %d).' % (csname, pid))

    def _run_testcase(self, testcasename:str):
        """ @brief Runs a testcase 

        @param testcasename Name of the testcase to run, format: id=<id>
        @return None """

        imgdestdir      = self.get_img_dir(testcasename)

        if path.exists(imgdestdir):
            rmtree(imgdestdir)
        os.makedirs(imgdestdir)

        indir           = self.srcdir
        outdir          = path.join(self.outdir, nh.get_outdir_name(
                            self.stage, self.iter_id), 
                            nh.AFL_DIR_NM, testcasename)

        img_path        = path.join(imgdestdir, 
                            testcasename+self.dedup.EXT_PM_POOL)
        img_path, tgtcmd_loc = nh.set_img_path(self.cfg.tgtcmd, 
                                    img_path, self.cfg)
        img_name        = path.basename(img_path)
        img_src_path    = path.join(self.dedup.dedup_dir_gbl, img_name)

        abort_if(img_path == "", 'Unable to set img path for %s.' % img_path)

        decompress(img_src_path + '.tar.gz', imgdestdir, self.verbose)        

        pids = run_afl(
            indir       = indir,
            outdir      = outdir,
            tgtcmd      = tgtcmd_loc,
            cfg         = self.cfg,
            cores       = 1,            # WARN: Use one core per testcase
            verbose     = self.verbose,
            persist_tgt = False,
            dry_run     = self.dry_run,
            gen_img     = False,
        )

    def _run_cs(self, csname:str):
        """ @brief Runs a testcase 

        @param csname Name of the crash site to run, name conforms to 
                      nh.is_crash_site
        @return None """

        cspath = path.join(self.dedup.dedup_dir_loc, 
            csname + '.' + nh.CMPR_CRASH_SITE_EXT)

        pmdir = self.cfg['pmfuzz']['img_loc']
        imgdir = tempfile.mkdtemp(prefix=('pmfuzz-cs-run-'+csname), dir=pmdir)

        #TODO: Figure out a way to clean this up on completion

        decompress(cspath, imgdir+'/', self.verbose)

        imgpm = path.join(imgdir, csname + '.' + nh.CRASH_SITE_EXT)

        indir           = self.srcdir
        outdir          = path.join(self.outdir, nh.get_outdir_name(
                            self.stage, self.iter_id), 
                            nh.AFL_DIR_NM, csname)

        img_path, tgtcmd_loc = nh.set_img_path(self.cfg.tgtcmd, imgpm, self.cfg)

        abort_if(img_path == "", 'Unable to set img path for %s.' % img_path)

        pids = run_afl(
            indir       = indir,
            outdir      = outdir,
            tgtcmd      = tgtcmd_loc,
            cfg         = self.cfg,
            cores       = 1,            # WARN: Use one core per testcase
            verbose     = self.verbose,
            persist_tgt = False,
            dry_run     = self.dry_run,
            gen_img     = False,
        )

        # Wait for AFL to start and see if it works
        if self.verbose:
            printv('Checking for PID: ' + str(pids))
            
        time.sleep(5)
        for pid in pids:
            abort_if(not psutil.pid_exists(pid), 
                f'AFL crashed for pid {pid}')

    def get_run_count(self, type=RunType.ALL):
        """ Get the total number of runnning testcases """

        result = 0

        if type&Stage2.RunType.TC:
            run_count = 0
            for testcasepath, imgpath in self.dedup.local_dedup_list_st2:
                
                testcasename = path.basename(testcasepath)\
                                .replace(self.dedup.EXT_TC, '')
                
                ptimer = PTimer(self.dedup.dedup_dir_loc, 
                                    testcasename, self.verbose)

                if not ptimer.is_new() and not ptimer.expired():
                    run_count += 1

                    # Check if the process is still running
                    pid_f = path.join(self.get_result_dir(testcasename), 'pid')
                    with open(pid_f, 'r') as obj:
                        pid = int(obj.read())
                        abort_if(not psutil.pid_exists(pid), 
                            f'[TC] AFL crashed for pid {pid}')
                                
            result += run_count

        if type&Stage2.RunType.CS:
            run_count = 0
            for cspath in self.dedup.local_dedup_list_cs_st2:
                
                csname = path.basename(cspath)\
                                .replace('.'+nh.CMPR_CRASH_SITE_EXT, '')
                
                ptimer = PTimer(self.dedup.dedup_dir_loc, 
                                    csname, self.verbose)

                if not ptimer.is_new() and not ptimer.expired():
                    run_count += 1

                    # Check if the process is still running
                    pid_f = path.join(self.get_result_dir(csname), 'pid')
                    with open(pid_f, 'r') as obj:
                        pid = int(obj.read())
                        abort_if(not psutil.pid_exists(pid), 
                            f'[CS] AFL crashed for pid {pid}')
                                
            result += run_count
    
        return result

    def show_progress(self, type):        
        """ Print the progress of currently running instances """

        if type&Stage2.RunType.TC:
            for testcasepath, imgpath in self.dedup.local_dedup_list_st2:
                
                testcasename = path.basename(testcasepath)\
                                .replace(self.dedup.EXT_TC, '')
                
                ptimer = PTimer(self.dedup.dedup_dir_loc, 
                                    testcasename, self.verbose)

                if not ptimer.is_new() and not ptimer.expired():
                    printi('elapsed (tc): ' + str(ptimer.elapsed_hr()) \
                                + ' ' + ptimer.elapsed_pb())

        if type&Stage2.RunType.CS:
            run_count = 0
            for cspath in self.dedup.local_dedup_list_cs_st2:
                
                csname = path.basename(cspath)\
                                .replace('.'+nh.CMPR_CRASH_SITE_EXT, '')
                
                ptimer = PTimer(self.dedup.dedup_dir_loc, 
                                    csname, self.verbose)

                if not ptimer.is_new() and not ptimer.expired():
                    printi('elapsed (cs): ' + str(ptimer.elapsed_hr()) \
                                + ' ' + ptimer.elapsed_pb())
    
    def resume(self):
        """ Resumes a already running stage

        @return None"""

        write_state(self.outdir, 'Running stage 2, iter ' + str(self.iter_id))

        printi(self.outdir, 'Resuming...')

        # Update the local dedup store
        self.dedup.update_local()

        printi('Job status: %d/%d' % \
            (self.get_run_count(type=Stage2.RunType.ALL), self.cores))

        # Get the total number of running testcaess
        run_count = self.get_run_count(type=Stage2.RunType.TC)


        finj_enabled \
            = self.cfg['pmfuzz']['failure_injection']['enable']

        cores_tc = 0
        cores_cs = 0
        half = self.cores//2

        # Distribute the cores equally
        if finj_enabled:
            cores_tc = 1 if half == 0 else half
            cores_cs = 1 if half == 0 else half
        else:
            cores_tc = self.cores

        printi('Slots TC: ' + str(cores_tc))
        printi('Slots CS: ' + str(cores_cs))

        # Create timers for all the testcases
        for testcasepath, imgpath in self.dedup.local_dedup_list_st2:

            # Get the name to construct a timer for the testcase
            testcasename = path.basename(testcasepath)\
                            .replace(self.dedup.EXT_TC, '')
            
            ptimer = PTimer(self.dedup.dedup_dir_loc, 
                                testcasename, self.verbose)
            
            if not ptimer.is_new(): 
                # If the timer was already started
                if ptimer.expired():

                    # Stop this testcase
                    self._terminate_testcase(testcasename, None)
                    #!
                    #! todo: run_count -= 1
            else:

                # Run only if there are cores available 
                if run_count < cores_tc:

                    printi('Starting new testcase: %s' % testcasename)

                    # This testcase was never started
                    ptimer.start_new(self.tc_timeout)
                    self._run_testcase(testcasename)
            
                    run_count += 1

        if finj_enabled:
            run_count = self.get_run_count(type=Stage2.RunType.CS)
            printi('CS occupancy: ' + str(run_count))

            # Create timers for all the crash images
            for cspath in self.dedup.local_dedup_list_cs_st2:

                # Get the name to construct a timer for the testcase
                csname = path.basename(cspath)\
                            .replace('.' + nh.CMPR_CRASH_SITE_EXT, '')

                
                ptimer = PTimer(self.dedup.dedup_dir_loc, csname, self.verbose)
                
                if not ptimer.is_new(): 
                    # If the timer was already started
                    if ptimer.expired():

                        # Stop this testcase
                        self._terminate_cs(csname, None)
                        #!
                        #! todo: run_count -= 1
                else:

                    # Run only if there are cores available 
                    if run_count < cores_cs:

                        printi('Starting new crash site fuzzing: %s' % csname)

                        # This testcase was never started
                        ptimer.start_new(self.tc_timeout)
                        self._run_cs(csname)
                
                        run_count += 1

        self.show_progress(Stage2.RunType.ALL)
            
    def run(self):
        """ Runs stage 2

        todo: Change the input test case directory to local dedup store 
        @return None"""

        # From this point everything works as if this stage already existed
        self.resume()

    def get_o_tc_dirs(self):
        """ Compiles a list of all the afl output directories for this stage 
        
        @return list of complete path to the AFL output directories """

        o_tc_dirs = listdir(self.afl_dir)

        full_path = lambda name: path.join(self.afl_dir, name, 
                                            'master_fuzzer', 'queue')

        return [full_path(o_tc_dir) for o_tc_dir in o_tc_dirs]

    def process_new_crash_sites(self, parent_img, clean_name):
        crash_imgs_pattern = parent_img.replace('.'+nh.CRASH_SITE_EXT, '') \
                                + '.' + clean_name.replace('.testcase', '') \
                                + '.*'

        new_crash_imgs = glob(crash_imgs_pattern)

        if self.verbose:
            printv('Using pattern %s found %d images' \
                % (crash_imgs_pattern, len(new_crash_imgs)))

        for img in new_crash_imgs:
            # Check the crash site for segfaults and non-zero exit codes
            self.check_crash_site(img)

            clean_img = re.sub(r"<pid=\d+>", "", img)

            # Only compress a crash site if it would ever be used
            if self.dedup.should_use_cs(clean_img):
                self.printv(f'Compressing: {img} -> {clean_img}.tar.gz')
                compress(img, clean_img+'.tar.gz', self.verbose, level=3,
                    extra_params=['--transform', r's/<pid=[[:digit:]]\+>//'])

                src = clean_img+'.tar.gz'
                dst = path.join(self.img_dir, path.basename(clean_img+'.tar.gz'))

                self.printv('Copying back: %s -> %s' %\
                    (src, dst))
                copypreserve(src, dst)

                # Save the hash for deduplication
                hash_f = path.join(
                    self.img_dir, 
                    path.basename(clean_img) + '.hash')

                with open(hash_f, 'w') as hash_obj:
                    hash_obj.write(sha256sum(img))

                hash_k = path.basename(img)
                hash_v = sha256sum(img)

                os.remove(src)

            os.remove(img)

    def tc_gen_crash_sites(self, raw_tcname):
        """ Generates crash sites for a testcase

        Testcases is read and crash sites are generated for each of the 
        failure point using the testcase's parent's image. These generated
        results are then sent to the crashsite directory: 
        (e.g., <outdir>/stage=2,iter=1/crashsites/)

        @param raw_tcname Path to a testcase to generate crash sites for
        """

        printi('Generating crash images for testcase: ' + raw_tcname)
        clean_name = nh.clean_tc_name(path.basename(raw_tcname))
        tc_components = os.path.normpath(raw_tcname).split(os.sep)
        parent_name = tc_components[-4] + '.testcase'

        printi('Clean name: ' + clean_name)
        printi('Parent name: ' + parent_name)

        # NOTE:
        # Create image names, *_uniq files are to provide each instance of 
        # tc_gen_crash_sites() with a unique image to work with

        pm_dir = tempfile.mkdtemp(prefix='pmfuzz-cs-gen-st2-', 
            dir=self.cfg('pmfuzz.img_loc'))
        parent_cmpr_img = nh.get_parent_img(
            parent_name, self.dedup.dedup_dir_gbl, 'exists', 
            isparent=True, verbose=self.verbose)

        # Create image path
        parent_img_name = ''
        if parent_cmpr_img.endswith(nh.CMPR_PM_IMG_EXT):
            parent_img_name = nh.get_metadata_files(parent_name)['pm_pool']
        elif parent_cmpr_img.endswith(nh.CMPR_CRASH_SITE_EXT):
            parent_img_name = nh.get_metadata_files(parent_name)['crash_site']

        parent_img_name_uniq = nh.get_metadata_files(parent_name)\
                                ['clean'] + '<pid=' + str(os.getpid()) + '>'\
                                + '.' + nh.CRASH_SITE_EXT

        parent_img = path.join(pm_dir, parent_img_name)
        parent_img_uniq = path.join(pm_dir, parent_img_name_uniq)
        
        # Decompres+Copy the image
        if not os.path.isfile(parent_img):
            decompress(parent_cmpr_img, parent_img, self.verbose)
        printv('tempimg: %s -> %s' % (parent_cmpr_img, parent_img))

        copypreserve(parent_img, parent_img_uniq)
        printv('unique image: %s -> %s' % (parent_img, parent_img))

        finj.run_failure_inj(self.cfg, self.cfg.tgtcmd, parent_img_uniq, raw_tcname, 
            clean_name, self.verbose)

        crash_imgs_pattern = parent_img.replace('.pm_pool', '') + '.' \
                                + clean_name.replace('.testcase', '') + '.*'
        crash_imgs = glob(crash_imgs_pattern)

        if self.verbose:
            printi('Total %d crash images generated.' % len(crash_imgs))
            printw('Deleting %s' % (parent_img))

        os.remove(parent_img_uniq)

        if self.verbose:
            printv('Compressing all the crash sites')

        self.process_new_crash_sites(parent_img_uniq, clean_name)

        if self.verbose:
            printv('Crash sites compressed')

    def collect_tc(self, o_tc_dir:str, source_name:str, clean_name:str):
        """ Copy the testcase from the queue directory to the local tc & img 
        dir and generate images.

        @param o_tc_dir Directory to copy the testcases from
        @param source_name Name of the testcase to copy
        @param clean_name New name of the testcase (supposed to be clean!)
        
        @return None """

        printi('Collecting TC %s.' % clean_name)

        # Copy testcase
        src     = path.join(o_tc_dir, path.basename(source_name))
        dest    = path.join(self.tc_dir, path.basename(clean_name))
        tc_dest = dest
        
        if self.verbose:
            printv('tcpy: %s -> %s' %(src, dest))

        copypreserve(src, dest)

        # Copy map
        src     = path.join(o_tc_dir, 'map_' + path.basename(source_name))
        dest    = path.join(self.tc_dir, 'map_' + path.basename(clean_name))
        
        if path.isfile(src):
            if self.verbose:
                printv('mapcpy: %s -> %s' %(src, dest))

            copypreserve(src, dest)
        else:
            if self.verbose:
                printw('Unable to find exec map: ' + src)

        # Copy PM map
        src     = path.join(o_tc_dir, 'pm_map_' + path.basename(source_name))
        dest    = path.join(self.tc_dir, 'pm_map_' + path.basename(clean_name))
        
        if path.isfile(src):
            if self.verbose:
                printv('pmmapcpy: %s -> %s' %(src, dest))

            copypreserve(src, dest)
        else:
            if self.verbose:
                printw('Unable to find pm map: ' + src)

        # TODO: Remove the output directory since the testcase is now completed

        # Generate and copy testcase
        tgt(tc_dest, self.cfg, self.verbose).gen_img(self.img_dir)

        if self.verbose:
            printv('TC collected')

    def collect_results(self) -> None:
        """ @brief Copies the results from the master fuzzer to local tc & img
        directory. 
        Operations are performed in parallel, using self.cores number of jobs 
        at a time. Only collects the available queue output directories in the
        .afl_results directory. Expects most of the testcases to be already 
        copied on termination. Present solely to collect testcases orphaned
        on the previous instance of PMFuzz.
        
        @return None """

        printi('Collecting stage 2, iter ' + str(self.iter_id))
        
        # Get all the output directories for all the testcases that were run
        o_dirs = self.get_o_tc_dirs()

        # Create a parallel object
        prl = Parallel(
            self.collect_tc, 
            self.cores, 
            failure_mode=Parallel.FAILURE_EXIT,
            transparent_io=False,
            verbose=self.verbose
        )

        cnt = 0
        found_cases = os.listdir(self.tc_dir)

        # Collect testcases from all of them
        for o_dir in o_dirs:
            gen_cases = [name for name in listdir(o_dir) \
                            if name.startswith('id') == True]

            for gen_case in gen_cases:
                
                # Parent name (name of the testcase that generated the image 
                # for this testcase)
                parent_name = path.dirname(path.dirname(o_dir)) + ','

                # Remove unnecessary information from testcase's name and check
                # if this testcase is not already copied 
                clean_name = parent_name + nh.clean_tc_name(gen_case)
                if not path.basename(clean_name) in found_cases:
                    prl.run([o_dir, gen_case, clean_name])
                    cnt += 1
        
        prl.wait()

        if self.verbose:
            printv('%d cases processed (%d already exists).' \
                % (cnt, len(found_cases)))

    def collect(self):
        """ Collects all the testcases in the master_fuzzer's queue and copies
        them to the local tc and img directory 
        
        @return None """
        printi('Collecting stage 2, iter ' + str(self.iter_id))
        write_state(self.outdir, 'Collecting stage 2, iter ' \
                        + str(self.iter_id))

        self.collect_results()

    @property
    def stage(self):
        """ Current stage """
        return self._stage
    
    @stage.setter
    def stage(self, value):
        abort_if(value != 2, 'Invalid stage %d.' % value)
        self._stage = value

    @property
    def iter_id(self):
        """ Current iteration """
        return self._iter_id
    
    @iter_id.setter
    def iter_id(self, value):
        abort_if(value < 1, 'Invalid iter_id %d.' % value)
        self._iter_id = value

    @property
    def completed(self):
        """ @brief Indicates if the stage has all its input run for atleast 
        cfg.tc_timeout seconds 
        
        @return bool value indidcating completion of this stage """
        
        result = True

        if self.verbose:
            printv('Checking for completeness in %d cases' \
                % len(self.dedup.local_dedup_list))

        for testcasepath, _ in self.dedup.local_dedup_list:
            
            # Get the name to construct a timer for the testcase
            testcasename = path.basename(testcasepath)\
                            .replace(self.dedup.EXT_TC, '')
            
            ptimer = PTimer(self.dedup.dedup_dir_loc, 
                                testcasename, self.verbose)
            
            if self.verbose:
                printv('%s: is_new=%s, expired=%s' % \
                    (testcasename, ptimer.is_new(), ptimer.expired()))
            if ptimer.is_new() or not ptimer.expired():
                result = False
                break 

        return result
    
