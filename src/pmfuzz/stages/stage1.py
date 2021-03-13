""" 
@file       stage1.py
@details    TODO
@copyright  2020-21 PMFuzz Authors

SPDX-license-identifier: BSD-3-Clause
"""

import pickledb
import re 
import sys

from os import path, makedirs, listdir
from random import randrange
from shutil import which, rmtree

import handlers.name_handler as nh
import interfaces.failureinjection as finj

from .dedup import Dedup
from .stage import Stage
from interfaces.afl import *
from helper import config
from helper import parallel
from helper.common import *
from helper.prettyprint import *
from helper.target import Target as Tgt
from helper.target import TempEmptyImage

class Stage1(Stage):
    """ Runs AFL on the initial set of example testcases without using an 
    input image. """

    # Result directory name for stage 1 directory
    def __init__(self, name, srcdir, outdir, cfg, cores, verbose, 
            force_resp, dry_run):
        
        # Create an outdir
        afloutdir = path.join(outdir, nh.get_outdir_name(1, 1), nh.AFL_DIR_NM)
        stageoutdir = path.join(outdir, nh.get_outdir_name(1, 1))

        self.afloutdir = afloutdir

        try:
            makedirs(afloutdir)
        except OSError:
            if path.isfile(afloutdir):
                abort('%s is not a directory.' % afloutdir)

        # Call the parent constructor
        super().__init__(name, srcdir, outdir, cfg, cores, verbose, 
                            force_resp, dry_run)

        # TODO: Share these values between dedup and Stage1
        # self.resultdir  = path.join(self.afloutdir, nh.get_outdir_name(1, 1))
        self.o_tc_dir   = path.join(self.afloutdir, 'master_fuzzer/queue')
        self.img_dir    = path.join(stageoutdir, Dedup.PM_IMG_DIR)
        self.tc_dir     = path.join(stageoutdir, Dedup.TESTCASE_DIR)
        self.map_dir    = path.join(stageoutdir, Dedup.MAP_DIR)

        try: 
            makedirs(self.tc_dir)
        except OSError as e:
            if path.isfile(self.tc_dir):
                abort('%s is not a directory.' % self.tc_dir)
        
        try:
            makedirs(self.img_dir)
        except OSError as e:
            if path.isfile(self.img_dir):
                abort('%s is not a directory.' % self.img_dir)

        try:
            makedirs(self.o_tc_dir)
        except OSError as e:
            if path.isfile(self.o_tc_dir):
                abort('%s is not a directory.' % self.o_tc_dir)

        try:
            makedirs(self.map_dir)
        except OSError as e:
            if path.isfile(self.map_dir):
                abort('%s is not a directory.' % self.map_dir)

    def run(self):
        """ Run stage 1, since it is run only once in the current design, 
        there are lot of corners that have been cut """
        
        run_afl(
            indir       = self.srcdir, 
            outdir      = self.afloutdir, 
            tgtcmd      = self.cfg.tgtcmd, 
            cfg         = self.cfg, 
            cores       = self.cores, 
            persist_tgt = False,
            verbose     = self.verbose,
            dry_run     = self.dry_run,
        )

        self.test_img_creation()

    def whatsup(self):
        """ Function that calls afl's whats-up tool on the result directory """        

        afl_whatsup_bin = path.join(self.cfg['pmfuzz']['bin_dir'], 'afl-whatsup') 

        if which('watch') is None:
            abort('`watch\' not found, is it included in the $PATH?')

        afl_whatsup_cmd = [afl_whatsup_bin, '-s', self.afloutdir]
        printi('Use the following command to track progress:'
                + '\n\t\twatch --color -n0.1 -d \'' 
                + ' '.join(afl_whatsup_cmd) + '\'')
        exec_shell(afl_whatsup_cmd, wait=True)

    def test_img_creation(self):
        """ Generates crash sites for testing image creation process """

        fd, imgpath = tempfile.mkstemp(dir=self.cfg('pmfuzz.img_loc'), 
            prefix='img_creation_test_img')
        os.close(fd)
        os.remove(imgpath)
        
        # Create the testcase file for generating an empty image
        fd, testcase_f = tempfile.mkstemp(prefix='pmfuzz-img-creation-input-')
        os.close(fd)

        if 'empty_img' in self.cfg('target') != 'None':
            with open(testcase_f, 'w') as obj:
                obj.write(self.cfg('target.empty_img.stdin') + '\n')

        finj.run_failure_inj(
            cfg         = self.cfg,
            tgtcmd      = self.cfg.tgtcmd,
            imgpath     = imgpath,
            testcase_f  = testcase_f,
            clean_name  = 'id=000000',
            create      = True,
            verbose     = self.verbose,
        )

        for img in glob(imgpath + '*'):
            self.check_crash_site(img)

    def _collect_map(self, source_name, clean_name):
        """ Copy the maps from the queue directory to the local map directory 

        @param source_name Orignal name of the map's testcase to copy
        @param clean_name Clean name of the map's testcase to copy (at dest)
        
        @return None """

        # Copy execution map
        src_nm  = 'map_' + source_name.replace('.testcase', '')
        dest_nm = 'map_' + clean_name

        src     = path.join(self.o_tc_dir, src_nm)
        dest    = path.join(self.tc_dir, dest_nm)

        if path.isfile(src):
            if self.verbose:
                printv('mapcpy %s -> %s' %(src, dest))

            copypreserve(src, dest)
        else:
            abort(f'Cannot find {src}')
        
        # Copy PM map
        src_nm  = 'pm_map_' + source_name.replace('.testcase', '')
        dest_nm = 'pm_map_' + clean_name

        src     = path.join(self.o_tc_dir, src_nm)
        dest    = path.join(self.tc_dir, dest_nm)

        if path.isfile(src):
            if self.verbose:
                printv('pmmapcpy%s -> %s' %(src, dest))

            copypreserve(src, dest)
        else:
            printw('Unable to find PM map: ' + src)

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
                    printv('Updated HashDB at %s with %s: %s' \
                        % (self.crash_site_db_f, hash_k, hash_v))
                    printw('Deleting ' + hash_f)

                os.remove(hash_f)

    def compress_new_crash_site(self, img):
        """ Compresses a specific crash site """

        clean_img = re.sub(r"<pid=\d+>", "", img)
        crash_img_name = path.basename(clean_img)

        # Remove the initial random part from the name
        crash_img_name = crash_img_name[crash_img_name.index('.')+1:]

        clean_img = path.join(self.img_dir, crash_img_name)

        # Check if this crash site works before compressing it
        self.check_crash_site(img)

        compress(img, clean_img+'.tar.gz', self.verbose, level=3, 
            extra_params=['--transform', 's/pmfuzz-tmp-img-.........//'])

    def compress_new_crash_sites(self, parent_img, clean_name):
        """ Compresses the crash sites generated for the parent img """

        crash_imgs_pattern = parent_img.replace('.'+nh.PM_IMG_EXT, '') \
                                + '.' + clean_name.replace('.'+nh.TC_EXT, '')\
                                + '.*'

        new_crash_imgs = glob(crash_imgs_pattern)

        if self.verbose:
            printv('Using pattern %s found %d images' \
                % (crash_imgs_pattern, len(new_crash_imgs)))

        hashdb = pickledb.load(self.crash_site_db_f, True)

        def get_hash(img):
            clean_img = re.sub(r"<pid=\d+>", "", img)
            crash_img_name = path.basename(clean_img)

            # Remove the initial random part from the name
            crash_img_name = crash_img_name[crash_img_name.index('.')+1:]

            hash_v = sha256sum(img)
            hash_f = path.join(self.img_dir, crash_img_name + '.hash')
            with open(hash_f, 'w') as hash_obj:
                hash_obj.write(hash_v)

        # Generate the hash of all the crash sites
        prl_hash = parallel.Parallel(
            get_hash, 
            self.cores, 
            transparent_io=True, 
            failure_mode=parallel.Parallel.FAILURE_EXIT
        )

        for img in new_crash_imgs:
            if self.verbose:
                printv('Running hash collection for ' + img)
            prl_hash.run([img])

        prl_hash.wait()

        if self.verbose:
            printv('Now left: %d images' % (len(new_crash_imgs)))

        # Compress the images in parallel
        prl = parallel.Parallel(
            self.compress_new_crash_site, 
            self.cores,
            transparent_io=True,
            failure_mode=parallel.Parallel.FAILURE_EXIT
        )
        for img in new_crash_imgs:
            prl.run([img])

        if self.verbose:
            printv('Waiting for compression to complete')

        prl.wait()

        for img in new_crash_imgs:
            os.remove(img)

    def tc_gen_crash_sites(self, raw_tcname):
        """ Generates crash sites for a testcase

        Testcases is read and crash sites are generated for each of the 
        failure point using the testcase's parent's image. These generated
        results are then sent to the crashsite directory: 
        (e.g., <outdir>/stage=1,iter=1/crashsites/)

        @see Stage2.tc_gen_crash_sites()

        @param raw_tcname Path to a testcase to generate crash sites for
        """

        printi('Generating crash images for testcase: ' + raw_tcname)
        clean_name = nh.clean_tc_name(path.basename(raw_tcname))

        # Create an empty image to run failure injection
        crash_img_prefix = None
        with TempEmptyImage(self.cfg, self.verbose) as tmp_img:
            crash_img_prefix = tmp_img

            if self.verbose:
                printv('Generating crash images for image %s' % crash_img_prefix)

            finj.run_failure_inj(self.cfg, self.cfg.tgtcmd, tmp_img, raw_tcname, 
                clean_name, create=False, verbose=self.verbose)

        crash_imgs_pattern = crash_img_prefix.replace('.pm_pool', '') + '.' \
                                + clean_name.replace('.testcase', '') + '.*'
        crash_imgs = glob(crash_imgs_pattern)

        if self.verbose:
            printi('Total %d crash images generated.' % len(crash_imgs))
            printv('Compressing all the crash sites')

        self.compress_new_crash_sites(crash_img_prefix, clean_name)
        self.add_cs_hash_lcl()

        if self.verbose:
            printv('Crash sites compressed')

    def collect_tc(self, source_name, clean_name):
        """ Copy the testcase from the queue directory to the local tc & img 
        dir and generate images 

        @param source_name Orignal name of the testcase to copy
        @param clean_name Clean name of the testcase to copy (at dest)
        
        @return None """
        
        write_state(path.dirname(path.dirname(self.afloutdir)), 'Running stage 1')

        if self.verbose:
            printv('Processing testcase: ' + path.basename(source_name))

        orig_tc_path    = path.join(self.o_tc_dir, source_name)

        src             = orig_tc_path
        dest            = path.join(self.tc_dir, clean_name)
        
        if self.verbose:
            printv('tc: %s -> %s' %(src, dest))

        copypreserve(src, dest)

        # Collect the map and generate the image of this testcase
        self._collect_map(source_name, clean_name)

        if self.verbose:
            printv('Generating PM img in %s using tc %s' % (self.img_dir, dest))

        Tgt(dest, self.cfg, self.verbose).gen_img(self.img_dir)
        
        if self.cfg['pmfuzz']['failure_injection']['enable']:
            randval = randrange(100)
            thresh = 5
            if randval < thresh:
                self.tc_gen_crash_sites(orig_tc_path)
            else:
                self.printv('Skipping cs generation'\
                    +f' ({randval} < {thresh})')


    def collect_results(self) -> None:
        """ Copies the results from the master fuzzer to local tc & img 
        directory 
        
        @return None """
        
        found_cases = os.listdir(self.tc_dir)
        gen_cases = [name for name in listdir(self.o_tc_dir) \
                        if name.startswith('id') == True]

        cnt = 0
        
        for gen_case in gen_cases:

            # Remove unnecessary information from testcase's name and check if 
            # this testcase is not already copied 
            clean_name = nh.clean_tc_name(gen_case)
            if not clean_name in found_cases:
                self.collect_tc(gen_case, clean_name)
                cnt += 1

        if self.verbose:
            printv('%d cases processed (%d already exists).' \
                % (cnt, len(found_cases)))

    def collect(self):
        """ Collects all the testcases in the master_fuzzer's queue and copies
        them to the local tc and img directory 
        
        @return None """

        if self.verbose:
            printv('Collecting results from stage 1')

        self.collect_results()
