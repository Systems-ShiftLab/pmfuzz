""" @file config.py 

@brief Configures a run """

import copy
import json
import os
import shlex
import yaml

import hiyapyco as hi

from os import path
from typing import List, Dict, Set

from helper.common import *
from helper.prettyprint import *

DEF_CFG_F = path.join('..', 'configs', 'base.yml')


class Config:
    """ @class Handles configuration """

    def __init__(self, cfg_f, verbose):
        self.pmfuzz_root = path.join(path.realpath(__file__), '../../../..')
        self.pmfuzz_root = path.realpath(self.pmfuzz_root)
        self.constr_path_repl()

        self.cfg_f = cfg_f
        self.verbose = verbose

        self.def_cfg_f = path.join(path.dirname(os.path.realpath(__file__)),
                                    DEF_CFG_F)
        self.def_cfg_content = Config._parse_f(self.def_cfg_f, self.pmfuzz_root, self.verbose)
        self.def_cfg_flat = Config._flatten(self.def_cfg_content)

    @staticmethod
    def subs_path(cfg_content, repl_dict):
        """ Replaces all the path using a dictionary """
        
        result = None
        if isinstance(cfg_content, list):
            result = []
        elif isinstance(cfg_content, dict):
            result = {}
        else:
            abort('Unable to process element of type %s' % (str(cfg_content)))

        for key in cfg_content:
            val = None
            
            if isinstance(cfg_content, list):
                val = key
            elif isinstance(cfg_content, dict):
                val = cfg_content[key]

            if isinstance(val, dict):
                result[key] = Config.subs_path(val, repl_dict)
            elif isinstance(val, list):
                result[key] = [None]*len(val)
                iter = 0
                for iter in range(len(val)):
                    subval = val[iter]
                    if isinstance(subval, str):
                        result[key][iter] = translate(subval, repl_dict)
                    elif isinstance(subval, dict) or isinstance(subval, list):
                        result[key][iter] \
                            = Config.subs_path(subval, repl_dict)
                    elif isinstance(subval, float) or isinstance(subval, int):
                        result[key][iter] = subval
            
            elif isinstance(val, str):
                result[key] = translate(val, repl_dict)
            else:
                result[key] = val
        
        return result


    def constr_path_repl(self):
        """ Replaces predefined variables with corresponding values.
        Check @ref configs/base.yml """

        self.repl_dict = {}

        self.repl_dict['%ROOT%']    = self.pmfuzz_root
        self.repl_dict['%BUILD%']   = path.join(self.pmfuzz_root, 'build')
        self.repl_dict['%LIB%']     = path.join(self.pmfuzz_root, 'build', 'lib')
        self.repl_dict['%BIN%']     = path.join(self.pmfuzz_root, 'build', 'bin')

    @staticmethod
    def _parse_f(cfg_f, root, verbose):
        """ @brief Parses a file and returns a dictionary object, also checks if
        the config file was valid.
        @param cfg_f Str pointing to the configuration file
        
        @return None """

        result = None

        if not path.isfile(cfg_f):
            abort('Unable to read config file: %s' % cfg_f)

        if verbose:
            printv('Parsing config file: ' + cfg_f)

        with open(cfg_f, 'r') as cfg_obj:
            try:
                result = yaml.safe_load(cfg_obj)
            except yaml.YAMLError as e:
                abort('Unable to parse confgig: ' + str(e))
        
        # If the file contains include statement
        if 'include' in result:
            include_list = result['include']
            include_list = [os.path.join(root, 'src', 'pmfuzz', include) for include in include_list]
            abort_if(len(include_list) == 0, 'Empty include list supplied')

            for include_file in include_list:
                if verbose:
                    printv('Found an include: ' + str(include_file))
                if not os.path.isfile(include_file):
                    abort('Included file `%s\' from `%s\' not found' \
                        % (include_file, cfg_f))

            # Current config file takes the highest priority and so should
            # be the last entry
            files_to_read = include_list + [cfg_f]
            result = hi.load(files_to_read, method=hi.METHOD_MERGE)

        # Convert any ordered dictionary to normal dict
        result = json.loads(json.dumps(result))

        if 'include' in result:
            del result['include']

        return result

    def parse(self):
        """ @brief Parses a file and returns a dictionary object, also checks if
        the config file was valid.
        @param cfg_f Str pointing to the configuration file
        
        @return None """

        self.parsed_cfg = Config._parse_f(self.cfg_f, self.pmfuzz_root, self.verbose)
        self.parsed_cfg = Config.subs_path(self.parsed_cfg, self.repl_dict)

    @staticmethod
    def _flatten(d):
        """ @brief Flattens a dictionary 

        https://stackoverflow.com/a/52081812/6556360

        @param d dict to flatten
        @return dict"""

        out = {}
        for key, val in d.items():
            if isinstance(val, dict):
                val = [val]
            if isinstance(val, list):
                for subval in val:
                    if isinstance(subval, list) or isinstance(subval, dict):
                        deeper = Config._flatten(subval).items()
                        out.update(
                            {key + '_' + key2: val2 for key2, val2 in deeper}
                        )
            else:
                out[key] = val
        return out

    def check(self):
        """ Checks if the configuration is valid.
        
        Compared against the default configuration file helper.Config.DEF_CFG_F. 
        Compares keys recursively for all levels.
        
        @param cfg Dict containing the config to compare

        @return None """
        result = True


        cfg_flattened = Config._flatten(self.parsed_cfg)

        for key in self.def_cfg_flat:
            if key not in cfg_flattened:
                if self.verbose:
                    printw('Key %s not found' % key)

                result = False
                break

        abort_if(not result, 'Invalid config ' + self.cfg_f)

    def get_env(self, persist):
        """ Returns an environment for given conditions
        
        @param persist Bool value for configuring persistence of pm image
        @return dict representing the environment for the target """

        result = dict(self.parsed_cfg['target']['env'])

        persist_kv = None
        if persist:
            persist_kv = self.parsed_cfg['target']['persist_enable_env']
        else:
            persist_kv = self.parsed_cfg['target']['persist_disable_env']

        persist_kv = persist_kv.split('=')
        persist_env =  {persist_kv[0]: persist_kv[1]}

        # merge dictionaries
        result.update(persist_env) 
        
        return result

    @property
    def tgtcmd(self):
        result = shlex.split(self.parsed_cfg['target']['cmd'], posix=False)
        return result

    def __str__(self):
        return json.dumps(self.parsed_cfg, indent=2, sort_keys=True)

    def __getitem__(self, key):
        result = None

        try:
            result =  self.parsed_cfg[key]
        except KeyError as e:
            abort('Key `%s\' does not exist in config file: %s' \
                    % (key, self.cfg_f))
                        
        return copy.deepcopy(result)
    
    def get_direct(self, fqname):
        """ Returns the value using a fully qualified name for the 
        corresponding key

        e.g., cfg.get_direct('pmfuzz.failure_injection.enable') would return
              same key as cfg['pmfuzz']['failure_injection']['enable']
        
        @param fqname str representing a fully qualified name for the element
                      to return 
        @return value corresponding to the fqname
        """

        keys = fqname.split('.')

        result = self
        for key in keys:
            result = result[key]
        
        return result

    __call__ = get_direct
