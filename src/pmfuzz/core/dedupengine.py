""" 
@file       dedupengine.py
@details    TODO
@copyright  2020-21 PMFuzz Authors

SPDX-license-identifier: BSD-3-Clause
"""

import re
import sys
import time

from os import path, makedirs, listdir, remove
from shutil import which, rmtree

import handlers.name_handler as nh

from helper.common import *
from helper.prettyprint import *

class DedupEngine:
    """ @class DedupEngine
    @brief Performs deduplication on files """
    def __init__(self, testcase_paths, verbose, checker=None):
        """ @brief create a DedupEngine object

        @param testcase_path List of path pointing to testcases to deduplicate 
        @param checker Function that maps a filename to a boolean indicating if
               that case should be processed, default: None
        """
        self.testcase_paths = testcase_paths
        self.verbose = verbose
        
        if checker == None:
            self.checker = lambda *_: True  
        else:
            self.checker = checker

    def _delete_tcs(self, testcases):
        """ @brief deletes a testcase and all metadata files with it, 
        including images and maps.

        @param testcases List of testcase name or complete path
        @return None"""

        delete_q = []

        # Find all the metadata files associated with all the testcases
        for testcase in testcases:
            metadata_files = nh.get_metadata_files(testcase)
            delete_q += metadata_files.values()

            # Write the placeholder file to indicate that this file is deleted
            placeholder_f \
                = nh.get_metadata_files(testcase, deleted=True)['deleted']
            with open(placeholder_f, 'w') as obj:
                obj.write('Deleted at epoch=%d' % int(time.time()))

        remove_files(delete_q, self.verbose, warn=True, force=True)

    def run(self):
        """ @brief Performs deduplication on testcases using execution map
        
        @return None"""

        # gbl_tc, _ = map(list, zip(*self.global_dedup_list_tc))
        testcases = [tc for tc in self.testcase_paths if self.checker(tc)]

        # Find and collect maps with duplicate hash values
        hash_map = {}
        for tc in testcases:
            sum = sha256sum(tc)

            if not sum in hash_map:
                hash_map[sum] = []
            
            hash_map[sum].append(tc)
        
        # Find the testcase with least number of ancestors for each set of 
        # duplicate testcases
        for key in hash_map:
            ancestor_cnts = [nh.ancestor_cnt(f) for f in hash_map[key]]
            min_indx = ancestor_cnts.index(min(ancestor_cnts))

            # Drop the oldest and remove others
            del hash_map[key][min_indx]
            self._delete_tcs(hash_map[key])
