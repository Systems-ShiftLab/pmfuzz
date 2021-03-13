""" 
@file       name_handler.py
@details    Contains common functions for working on names
@package    name_handler
@copyright  2020-21 PMFuzz Authors

SPDX-license-identifier: BSD-3-Clause
"""

import doctest
import re
import tempfile

from os import path

from helper.common import *

AFL_DIR_NM      = '.afl-results'
ST2_MIN_DIR     = '@total_min_output'
MIN_TOKEN       = '.min'

# Extensions
TC_EXT                  = 'testcase'
HASH_F_EXT              = 'hash'
CMPR_CRASH_SITE_EXT     = 'crash_site.tar.gz'
CRASH_SITE_EXT          = 'crash_site'
CMPR_PM_IMG_EXT         = 'pm_pool.tar.gz'
PM_IMG_EXT              = 'pm_pool'

EXT_LIST                = [
    TC_EXT, HASH_F_EXT, CMPR_CRASH_SITE_EXT, 
    CRASH_SITE_EXT, CMPR_PM_IMG_EXT, PM_IMG_EXT
]

# Regular expresions
TC_MIN_REGEX            = r'^(id=\d+)(\.id=\d+)*(,id=\d+(\.id=\d+)*)*\.min\.testcase$'
TC_REGEX                = r'^(id=\d+)(\.id=\d+)*(,id=\d+(\.id=\d+)*)*\.testcase$'
MAP_REGEX               = r'^map_(id=\d+)(\.id=\d+)*(,id=\d+(\.id=\d+)*)*\.testcase$'
PM_MAP_REGEX            = r'^pm_map_(id=\d+)(\.id=\d+)*(,id=\d+(\.id=\d+)*)*\.testcase$'
CRASH_SITE_REGEX        = r'^(id=\d+)(\.id=\d+)*(,id=\d+(\.id=\d+)*)*\.crash_site$'
CMPR_CRASH_SITE_REGEX   = r'^(id=\d+)(\.id=\d+)*(,id=\d+(\.id=\d+)*)*\.crash_site.tar.gz$'
PM_IMG_REGEX            = r'^(id=\d+)(\.id=\d+)*(,id=\d+(\.id=\d+)*)*\.pm_pool$'
PM_CMPR_IMG_REGEX       = r'^(id=\d+)(\.id=\d+)*(,id=\d+(\.id=\d+)*)*\.pm_pool.tar.gz$'

def get_outdir_name(stage, iter_id):
    """ Get the name of the output directory for a give stage and iter id """

    abort_if(iter_id < 1, 'iter_id should be greater than 0')
    abort_if(stage < 1,   'stage should be greater than 0')

    return 'stage=' + str(stage) + ',iter=' + str(iter_id)

def get_stage_str(stage, iter_id):
    """ String representing the stage and the iter_id """

    # Currently same as get_outdir_name()
    return get_outdir_name(stage, iter_id)
    
def get_stage_inf(dirname):
    """ Returns stage and iteration id for a give directory name """

    if not 'stage=' in dirname or not ',iter=' in dirname:
        abort('Invalid dirname (%s).' % dirname)
    
    stage = None
    iter_id = None
    
    split = dirname.split(',')

    for token in split:
        if 'stage' in token:
            stage = int(token.split('=')[1])
        elif 'iter' in token:
            iter_id = int(token.split('=')[1])
        else:
            abort('Unkown token %s.' % token)
    
    abort_if(stage==None, 'Unable to extract stage from %s.' % dirname)
    abort_if(iter_id==None, 'Unable to extract iter_id from %s.' % dirname)

    return stage, iter_id

def get_lineage(tc_name):
    """ Returns the ids assigned at different stages of it's life

    @param tc_name str representing the testcase's name or complete path

    @return list of int

    **Example**
    @code{.py}
    
    >>> get_lineage('id=19,id=928,id=193.testcase')
    [19, 928, 193]
    >>> get_lineage('id=19.id=10,id=928,id=193.testcase')
    [19, 928, 193]
    
    @endcode """

    tc_name = path.basename(tc_name)
    tc_name = get_metadata_files(tc_name)['clean']

    tokens = tc_name.split(',')
    
    lineage = []
    for tkn in tokens:
        # If there is a crash image extension, remove it
        clean_tkn = tkn
        if '.' in tkn:
            clean_tkn = tkn[:tkn.find('.')]
            
        value = int(clean_tkn.split('=')[1])
        lineage.append(value)
    
    return lineage

def clean_tc_name(tc_name):
    """ Removes extra information from testcase's name.
    
    Only accepts name, no paths.
    @return None"""

    tokens = tc_name.split(',')
    id_tk = tokens[0]
    id = id_tk.split(':')[1]

    return 'id=' + id + '.testcase'

def set_img_name(tgtcmd, new_img_name, cfg):
    """ Replace the image name with new_img_name in the program's command
    and returns the path of the new output image. 
    
    str is empty if the match failed

    @param tgtcmd Command of the target program as a list
    @param new_img_name New name for the PM image
    
    @return Tuple with first element the new image path and second element the
            new command 

    **Example**

    @code{.py}
    
    >>> tgtcmd = ['a', '__POOL_IMAGE__', 'pslab_force']
    >>> cfg = lambda key: '/mnt/pmem0'
    >>> set_img_name(tgtcmd, 'test_name', cfg)
    ('/mnt/pmem0/test_name', ['a', '/mnt/pmem0/test_name', 'pslab_force'])

    @endcode """

    tgtcmd_loc = list(tgtcmd)
    img_path = ""


    # Replace image marger with image name
    for tcl_iter in range(len(tgtcmd_loc)):
        if PM_IMG_MRK in tgtcmd_loc[tcl_iter]:
            replaced = True

            # Add a random prefix to the image name
            img_path = path.join(cfg('pmfuzz.img_loc'), new_img_name)

            tgtcmd_loc[tcl_iter] = tgtcmd_loc[tcl_iter].replace(
                PM_IMG_MRK, img_path)

            break

    result = (img_path, tgtcmd_loc)
    return result

def set_img_path(tgtcmd, new_img_path, cfg) -> (str, list):
    """ Replace the image path with new_img_path in the program's command
    and returns the path of the new output image. 
    
    str is empty if the match failed

    @return Tuple with first element the new image path and second element the
            new command 
            
    **Example**
    @code{.py}
    
    >>> tgtcmd = ['a', '__POOL_IMAGE__', 'pslab_force']
    >>> cfg = lambda key: '/mnt/pmem0'
    >>> set_img_path(tgtcmd, '/tmp/', cfg)
    ('/tmp/', ['a', '/tmp/', 'pslab_force'])

    @endcode """

    img_path, tgtcmd_loc = set_img_name(tgtcmd, 'DUMMY_NAME', cfg)
    
    for i in range(len(tgtcmd_loc)):
        if img_path in tgtcmd_loc[i]:
            tgtcmd_loc[i] = tgtcmd_loc[i].replace(img_path, new_img_path)

    result = (new_img_path, tgtcmd_loc)
    return result

def get_extension(testcase):
    """ @brief Returns the extension of a testcase

    @param testcase Str representing the name or the complete path of the 
           testcase

    **Example**
    @code{.py}
    
    >>> get_extension('id=1,id=2,id=2.testcase')
    '.testcase'
    >>> get_extension('map_id=1.id=98,id=2,id=2.testcase')
    '.testcase'

    @endcode """

    basename    = path.basename(testcase)
    result      = ''

    for ext in EXT_LIST:
        if ext in basename:
            result = '.' + ext
            break

    return result

def get_testcase_parent(testcase):
    """ @brief Returns the parent testcase name, else returns an empty string 

    @param testcase Str representing the name or the complete path of the 
           testcase

    **Example**
    @code{.py}
    
    >>> get_testcase_parent('id=1,id=2,id=2.testcase')
    'id=1,id=2.testcase'
    >>> get_testcase_parent('map_id=1,id=2,id=2.testcase')
    'map_id=1,id=2.testcase'
    >>> get_testcase_parent('id=2.testcase')
    ''
    >>> get_testcase_parent('id=010.id=016,id=012.id=516,id=013.testcase')
    'id=010.id=016,id=012.id=516.testcase'
    >>> get_testcase_parent('id=010.id=016,id=012.id=516,id=013.testcase')
    'id=010.id=016,id=012.id=516.testcase'
    >>> get_testcase_parent('id=010.id=016,id=012.id=516.id=013.testcase')
    'id=010.id=016,id=012.id=516.testcase'

    @endcode """

    result = ''

    basename = path.basename(testcase)

    # Separate the ids and the file extension
    ext = get_extension(basename)
    clean_name = basename.replace(ext, '')

    ids = re.split(',|\.', clean_name)
    
    # Collect the delimiters:
    delims = []
    for char in clean_name:
        if char in ['.', ',']:
            delims.append(char)

    # Count the number of ids
    id_cnt = len(ids)

    # If there are more than 1 ids, set the result value
    if id_cnt > 1:
        parent_ids = ids[:-1]

        # Reconstruct the name with the delimiters and the parent ids
        result = parent_ids[0]
        iter = 0
        for elem in parent_ids[1:]:
            result += delims[iter] + elem
            iter += 1
        result += ext

    return result

def get_img_dir(tgtcmd):
    """ @brief Returns the image directory from a target command 
    
    @return Path of the pm image directory as str, 'None' if no PM_IMG_MARKER 
            is found

    **Example**
    @code{.py}
    
    >>> get_img_dir(['something', 'some other thing', '/mnt/pmem0/__POOL_IMAGE__'])
    '/mnt/pmem0'
    >>> get_img_dir(['something', 'some other thing'])
    
    @endcode """

    result = None

    for token in tgtcmd:
        if PM_IMG_MRK in token:
            result = path.dirname(token)

    return result
            
def get_tc_min(testcase, tc_ext):
    """ @brief Converts testcase name/path to minimized testcase name/path 
    
    @param testcase Name/path of testcase to process
    @param tc_ext   Extension of testcase (stage.dedup.Dedup.EXT_TC)
    @return str

    **Example**  
    @code{.py}

    >>> get_tc_min('id=010.testcase', '.testcase')
    'id=010.min.testcase'

    @endcode"""

    return testcase.replace(tc_ext, '') + MIN_TOKEN + tc_ext

def is_regex(filename, regex):
    """ @brief Checks if a filename/file path follows the given regex naming 
    pattern.
    
    @return Bool"""

    basename = path.basename(filename)
    match = re.search(regex, basename)

    return match != None

def is_tc(filename, all=False):
    """ @brief Checks if a filename/file path follows the testcase naming 
    pattern.

    @param filename Filename or complete path to test
    @param all Includes both testcases and min testcases

    **Example**  
    @code{.py}

    >>> is_tc('id=010,id=012,id=013.testcase')
    True
    >>> is_tc('id=010.id=19,id=012,id=013.testcase')
    True
    >>> is_tc('id=010id=19,id=012,id=013.testcase')
    False
    >>> is_tc('id=010.id=19,id=012,id=013.min.testcase')
    False
    >>> is_tc('id=010.id=19,id=012,id=013.min.testcase', all=True)
    True

    @endcode
    
    @return Bool"""

    return is_regex(filename, TC_REGEX) \
        or (all and is_regex(filename, TC_MIN_REGEX))

def is_min_tc(filename, all=False):
    """ @brief Checks if a filename/file path follows the min testcase naming 
    pattern.

    @param filename Filename or complete path to test
    @param all Includes both testcases and min testcases

    @return Bool"""

    return is_regex(filename, TC_MIN_REGEX)

def is_generic_tc(filename):
    return is_tc(filename, all=True)

def is_cmpr_img(filename):
    """ @brief Checks if a filename/file path follows the cmpr PM img naming 
    pattern.

    **Example**  
    @code{.py}

    >>> is_cmpr_img('/mnt/tmpfs/results/@dedup/id=000069.pm_pool.tar.gz')
    True
    >>> not_cmpr_map = lambda name: not is_cmpr_img(name);
    >>> not_cmpr_map('/mnt/tmpfs/results/@dedup/id=000069.pm_pool.tar.gz')
    False
    
    @endcode
    
    @return Bool"""

    return is_regex(filename, PM_CMPR_IMG_REGEX)
    
def is_img(filename):
    """ @brief Checks if a filename/file path follows the PM img naming 
    pattern.
    @return Bool"""

    return is_regex(filename, PM_IMG_REGEX)

def is_map(filename):
    """ @brief Checks if a filename follows the map naming pattern
    @return Bool"""

    return is_regex(filename, MAP_REGEX)

def is_pm_map(filename):
    """ @brief Checks if a filename follows the pm map naming pattern
    @return Bool"""

    return is_regex(filename, PM_MAP_REGEX)

def is_hash_f(filename):
    """ @brief Checks if a filename is for a hash file
    @return Bool"""

    return filename.endswith('.' + HASH_F_EXT)

def is_crash_site(filename):
    """ @brief Checks if a filename follows the crash site naming pattern
    @return Bool"""

    return is_regex(filename, CRASH_SITE_REGEX)

def is_cmpr_crash_site(filename):
    """ @brief Checks if a filename follows the compressed crash site naming 
    pattern

    **Example**  
    @code{.py}

    >>> is_cmpr_crash_site('id=000011.id=000046.79.crash_site.tar.gz')
    False
    >>> is_cmpr_crash_site('id=000033.id=000027.crash_site.tar.gz')
    True

    @endcode

    @return Bool"""

    return is_regex(filename, CMPR_CRASH_SITE_REGEX)

def iter_cnt(filename):
    """@brief returns the number of iterations a testcase has been passed 
    through for filename or a file path.
    @return str
    
    **Example**  
    @code{.py}

    >>> iter_cnt('id=010,id=012,id=013.testcase')
    3

    @endcode"""

    return ancestor_cnt(filename) + 1

def ancestor_cnt(filename):
    """@brief returns the number of ancestors for filename or a file path
    @return str
    
    **Example**  
    @code{.py}

    >>> ancestor_cnt('id=010,id=012,id=013.testcase')
    2
    >>> ancestor_cnt('id=010.id=016,id=012.id=516,id=013.testcase')
    2

    @endcode"""

    basename = path.basename(filename)

    clean_name = get_metadata_files(basename)['clean']

    # Separate the ids and the file extension
    ids = clean_name.split(',')
    
    # Count the number of ids
    id_cnt = len(ids)

    return id_cnt-1

def get_metadata_files(testcase, deleted=False):
    """ @brief Takes a testcase and generates a list of metadata files 
    associated with that file 
    
    @param testcase Testcase name or complete path
    @param deleted Generates an entry for the deleted place holder file
    @return List of str

    **Example**  
    @code{.py}

    >>> def match_dict(dict1, dict2):
    ...     for key in dict1:
    ...         if not key in dict2 or dict1[key] != dict2[key]:
    ...             print('Key %-20s missing/mismatch in dict2, val=%s' % (str(key), str(dict1[key])))
    ...     for key in dict2:
    ...         if not key in dict1 or dict1[key] != dict2[key]:
    ...             print('Key %-20s missing/mismatch in dict1, val=%s' % (str(key), str(dict2[key])))
    ...     print(dict1 == dict2)
    >>> expected = {'testcase':       'id=010.testcase', 
    ...             'clean':          'id=010', 
    ...             'min_testcase':   'id=010.min.testcase', 
    ...             'pm_map':         'pm_map_id=010.testcase', 
    ...             'map':            'map_id=010.testcase', 
    ...             'deleted':        'id=010.deleted', 
    ...             'crash_site':     'id=010.crash_site',
    ...             'crash_cmpr_site':'id=010.crash_site.tar.gz',
    ...             'pm_pool':        'id=010.pm_pool',
    ...             'pm_cmpr_pool':   'id=010.pm_pool.tar.gz'}
    >>> match_dict(get_metadata_files('map_id=010.testcase', deleted=True), expected)
    True
    >>> match_dict(get_metadata_files('id=010.testcase', deleted=True), expected)
    True
    >>> match_dict(get_metadata_files('id=010.pm_pool', deleted=True), expected)
    True
    >>> match_dict(get_metadata_files('id=010.pm_pool.tar.gz', deleted=True), expected)
    True
    >>> expected = {'testcase':         '/a/id=010.testcase', 
    ...             'clean':            '/a/id=010', 
    ...             'min_testcase':     '/a/id=010.min.testcase', 
    ...             'pm_map':           '/a/pm_map_id=010.testcase', 
    ...             'map':              '/a/map_id=010.testcase', 
    ...             'crash_site':       '/a/id=010.crash_site',
    ...             'crash_cmpr_site':  '/a/id=010.crash_site.tar.gz',
    ...             'pm_pool':          '/a/id=010.pm_pool',
    ...             'pm_cmpr_pool':     '/a/id=010.pm_pool.tar.gz'}
    >>> match_dict(get_metadata_files('/a/id=010.pm_pool', deleted=False), expected)
    True
    >>> expected = {'testcase':       '/a/id=010.id=000.testcase', 
    ...             'clean':          '/a/id=010.id=000', 
    ...             'min_testcase':   '/a/id=010.id=000.min.testcase', 
    ...             'pm_map':         '/a/pm_map_id=010.id=000.testcase', 
    ...             'map':            '/a/map_id=010.id=000.testcase', 
    ...             'crash_site':     '/a/id=010.id=000.crash_site',
    ...             'crash_cmpr_site':'/a/id=010.id=000.crash_site.tar.gz',
    ...             'pm_pool':        '/a/id=010.id=000.pm_pool',
    ...             'pm_cmpr_pool':   '/a/id=010.id=000.pm_pool.tar.gz'}
    >>> match_dict(get_metadata_files('/a/id=010.id=000.pm_pool', deleted=False), expected)
    True

    @endcode"""

    basename = path.basename(testcase)
    dirname = path.dirname(testcase)

    if 'pm_map' in basename:
        basename = basename.replace('pm_map_', '')
    elif 'map' in basename:
        basename = basename.replace('map_', '')
    elif '.pm_pool.tar.gz' in basename:
        basename = basename.replace('.pm_pool.tar.gz', '.testcase')
    elif '.pm_pool' in basename:
        basename = basename.replace('.pm_pool', '.testcase')
    elif '.crash_site.tar.gz' in basename:
        basename = basename.replace('.crash_site.tar.gz', '.testcase')
    elif '.crash_site' in basename:
        basename = basename.replace('.crash_site', '.testcase')
    elif '.min' in basename:
        basename = basename.replace('.min', '')

    abort_if(not is_tc(basename), 'Cannot convert ' + testcase + ' to a valid '\
        + 'testcase name, got: ' + basename)

    bare_name = basename.replace('.testcase', '')

    result = {
        'testcase':         path.join(dirname, basename),
        'clean':            path.join(dirname, bare_name),
        'min_testcase':     path.join(dirname, bare_name + '.min.testcase'),
        'pm_map':           path.join(dirname, 'pm_map_' + basename),
        'map':              path.join(dirname, 'map_' + basename),
        'deleted':          path.join(dirname, bare_name + '.deleted'),
        'crash_site':       path.join(dirname, bare_name + '.crash_site'),
        'crash_cmpr_site':  path.join(dirname, bare_name + '.crash_site.tar.gz'),
        'pm_pool':          path.join(dirname, bare_name + '.pm_pool'),
        'pm_cmpr_pool':     path.join(dirname, bare_name + '.pm_pool.tar.gz'),
    }

    if not deleted:
        del result['deleted']

    return result

def get_parent_img(testcasepath, dir, get, isparent=False, verbose=True):
    """ Returns the name of the testcase parent image, CS or complete present
    in a directory.

    Helpful for finding the parent of the image, without checking every time if
    it would be a CS or a complete image.

    @param testcasepath Full path or name of the testcase
    @param dir Path to the directory to check for the image in
    @param get {'exists'|'complete'|'cs'}
    @param isparent Tells if the testcasepath is already a parent
    @return Full path or name of the parent image 
    
    **Example**  
    @code{.py}

    >>> get_parent_img('id=010.id=010.min.testcase', dir='/tmp', get='cs', verbose=False)
    '/tmp/id=010.crash_site.tar.gz'
    >>> get_parent_img('id=010.id=010.min.testcase', dir='/tmp', get='complete', verbose=False)
    '/tmp/id=010.pm_pool.tar.gz'
    >>> get_parent_img('id=010.id=010.testcase', dir='/tmp', get='complete', 
    ...     isparent=True, verbose=False)
    '/tmp/id=010.id=010.pm_pool.tar.gz'

    @endcode
    
    """

    if verbose:
        printv(f'testcasepath: {testcasepath}')
        printv(f'dir: {dir}')
        printv(f'get: {get}')
        printv(f'isparent: {isparent}')
        printv(f'verbose: {verbose}')

    VALID_GET_VALS = ['exists', 'complete', 'cs']
    if get not in VALID_GET_VALS:
        abort(f'Value {get} is not one of the following: ' \
            + ' '.join(VALID_GET_VALS))

    cleanname = get_metadata_files(path.basename(testcasepath))['testcase']
    basename = ''

    if isparent:
        basename = cleanname
    else:
        basename = get_testcase_parent(cleanname)

    csname = get_metadata_files(basename)['crash_cmpr_site']
    completename = get_metadata_files(basename)['pm_cmpr_pool']

    cs_exists = False
    complete_exists = False
    check_path_cs = path.join(dir, csname)
    check_path_complete = path.join(dir, completename)

    if get == 'exists':
        cs_exists = path.isfile(check_path_cs)
        complete_exists = path.isfile(check_path_complete)

        abort_if(cs_exists and complete_exists, 
            f'Both images cannot exists: {check_path_cs} and {check_path_complete}')
    elif get == 'cs':
        cs_exists = True
    elif get == 'complete':
        complete_exists = True

    result = ''

    if cs_exists:
        result = check_path_cs
    elif complete_exists:
        result = check_path_complete
    else:
        abort(f'Unable to find any image for {basename} in {dir}')

    return result