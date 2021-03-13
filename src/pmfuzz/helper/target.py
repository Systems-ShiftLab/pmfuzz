""" 
@file       target.py
@details    TODO
@copyright  2020-21 University of Virginia

SPDX-license-identifier: BSD-3-Clause
"""
import handlers.name_handler as nh

from helper.common import abort
from helper.common import abort_if
from helper.common import compress
from helper.common import exec_shell
from helper.common import translate_exit_code
from helper.prettyprint import printv
from helper.prettyprint import printw
from stages.fuzzobj import FuzzObj

import os
import subprocess
import tempfile

from os import path, remove

class Target(FuzzObj):
    """ @brief Class for handling the PMFuzz's target program 

    Todo: Use this instead of passing around tgtcmd """

    def __init__(self, testcase_f, cfg, verbose):
        super().__init__('', verbose, None, False)
        
        self.testcase_f = testcase_f
        self.cfg        = cfg
        self.verbose    = testcase_f

    def gen_img(self, dest_dir, compress_img=True, img_path=None):
        """ @brief Generate image for a testcase file 
        
        @param testcase_f str that points to the testcase to use for generation
        @param dest_dir str Directory to store the resulting image
        @param tgtcmd List of str for the command for running the target prog
        @param cfg Config for setting up the target process' environment

        @return None """

        testcase_f = self.testcase_f
        cfg        = self.cfg
        verbose    = self.verbose

        tgtcmd = cfg.tgtcmd

        tgtcmd_loc = None
        if img_path == None:
            img_name = path.basename(nh.get_metadata_files(testcase_f)['pm_pool'])

            # Get the command for generating the image
            img_path, tgtcmd_loc = nh.set_img_name(tgtcmd, img_name, cfg)

            abort_if(img_path=='', 'Unable to parse image path, tgtcmd=' + \
                                    str(tgtcmd) + ', img_name=' + img_name)
        else:
            img_name = path.basename(img_path)

            # Get the command for generating the image
            img_path, tgtcmd_loc = nh.set_img_path(tgtcmd, img_path, cfg)

            abort_if(img_path=='', 'Unable to parse image path, tgtcmd=' + \
                                    str(tgtcmd) + ', img_name=' + img_name)


        # Enable persistence for image in the environment
        env = cfg.get_env(persist=True)

        if verbose:
            printv('cmd: %s' % (' '.join(tgtcmd_loc)))
            printv('env: %s' % (str(env)))
            printv('stdin: %s' % testcase_f)

        # Create a tempfile for writing run output
        fd, tmp = tempfile.mkstemp(prefix='pmfuzz-img-gen-output-')
        os.close(fd)

        if verbose:
            printv('Writing image generation output to ' + tmp)

        with open(tmp, 'w') as out:
            with open(testcase_f, 'r') as testcase_obj:
                exit_code = exec_shell(
                    cmd=tgtcmd_loc,
                    stdin=testcase_obj,
                    stdout=out,
                    stderr=subprocess.STDOUT,
                    env=env,
                    wait=True,
                    timeout = 30 # Set a generous timeout of 30 seconds so things don't crash
                )

                code_desc, success = translate_exit_code(exit_code)
                if not success:
                    abort('Image generation failed: ' + code_desc)
                    
        if not path.isfile(img_path):
            abort('Image generation failed (%s).' % img_path)
        
        # Copy the file back to the pmfuzz result directory
        if compress_img:
            src = img_path
            dest = path.join(dest_dir, path.basename(img_path))
            dest = nh.get_metadata_files(dest)['pm_cmpr_pool']

            compress(src, dest, verbose)
            remove(src)
            
            if verbose:
                printw('Deleting: ' + src)

    def test_img_gen(self, imgpath):
        """ @brief Tests the process of creating a new image with the testcase 
        by checking return code of the target

        @param imgpath str representing the complete path of the image to test,
               the path should not exist
        @return bool value indicating success """

        # Create a tempfile for writing run output
        fd, tmp = tempfile.mkstemp(prefix='pmfuzz-test-img-output-')
        os.close(fd)

        tgtcmd_loc = list(self.cfg.tgtcmd)
        imgpath, tgtcmd_loc = nh.set_img_path(tgtcmd_loc, imgpath, self.cfg)

        env = self.cfg.get_env(persist=False)

        if self.verbose:
            printv('Writing run output to ' + tmp)

        success, exit_code = None, None
        with open(tmp, 'w') as out:
            with open(self.testcase_f, 'r') as testcase_obj:
                exit_code = exec_shell(
                    cmd     = tgtcmd_loc,
                    stdin   = testcase_obj,
                    stdout  = out,
                    stderr  = subprocess.STDOUT,
                    env     = env,
                    wait    = True
                )

                code_desc, success = translate_exit_code(exit_code)

                if not success and self.verbose:
                    printv('Image failed.')

        if success == None:
            abort('Test run failed, unable to check image.')

        return success, exit_code, tgtcmd_loc, env

    def test_img(self, imgpath):
        """ @brief Tests an image with the testcase by checking return code of 
        the target

        @param imgpath str representing the complete path of the image to test
        @return bool value indicating success """
        
        # Create a tempfile for writing run output
        fd, tmp = tempfile.mkstemp(prefix='pmfuzz-test-img-output-')
        os.close(fd)

        tgtcmd_loc = list(self.cfg.tgtcmd)
        imgpath, tgtcmd_loc = nh.set_img_path(tgtcmd_loc, imgpath, self.cfg)

        env = self.cfg.get_env(persist=False)

        if self.verbose:
            printv('Writing run output to ' + tmp)

        success, exit_code = None, None
        with open(tmp, 'w') as out:
            with open(self.testcase_f, 'r') as testcase_obj:
                exit_code = exec_shell(
                    cmd     = tgtcmd_loc,
                    stdin   = testcase_obj,
                    stdout  = out,
                    stderr  = subprocess.STDOUT,
                    env     = env,
                    wait    = True
                )

                code_desc, success = translate_exit_code(exit_code)

                if not success and self.verbose:
                    printv('Image failed.')

        if success == None:
            abort('Test run failed, unable to check image.')

        return success, exit_code, tgtcmd_loc, env

class TempEmptyImage(Target):
    """ @brief Class to create a temporary empty image 
    
    This image lives until the context or cleanup is called """

    def __init__(self, cfg, verbose):
        img_dir = cfg['pmfuzz']['img_loc']
        self.img_dir = img_dir

        fd, tcf = tempfile.mkstemp(prefix='pmfuzz-tmp-tc-in-')
        os.close(fd)

        tcf_content = '\n'
        if 'empty_img' in cfg['target']:
            tcf_content = cfg['target']['empty_img']['stdin'] + '\n'

        with open(tcf, 'w') as obj:
            obj.write(tcf_content)

        if verbose:
            printv("Using '%s' in file '%s' as input for empty image gen"\
                % (tcf_content, tcf))

        super().__init__(tcf, cfg, verbose)

        fd, self.tmp_img = tempfile.mkstemp(prefix='pmfuzz-tmp-img-', 
                            dir=img_dir, suffix='.pm_pool')
        os.close(fd)
        os.remove(self.tmp_img)

    def generate(self):
        """ @brief Generates the empty image 

        @return Path to the empty image """

        if self.verbose:
            printv('Creating temporary image at %s' % (self.tmp_img))

        super().gen_img(self.img_dir, compress_img=False, 
            img_path=self.tmp_img)

        return self.tmp_img

    def cleanup(self):
        self.printv('Deleting temporary image at %s' % (self.tmp_img))

        os.remove(self.tmp_img)

    def __enter__(self):
        return self.generate()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
