""" 
@file       bugreport.py
@details    TODO
@copyright  2020-21 University of Virginia

SPDX-license-identifier: BSD-3-Clause
"""
import datetime
import time

from os import path

class BugReport:
    """ Class representing a bug report """

    def __init__(self, tester_f, imgpath, cmd, env, outdir):
        self.tester_f   = tester_f
        self.imgpath    = imgpath
        self.cmd        = cmd
        self.env        = env
        self.outdir     = outdir

        self.bug_db_f           = path.join(self.outdir, '@bugs.db')
        self.bug_hr_f           = path.join(self.outdir, '@bugs.human_readable')

    def fmt_report(self):
        result = ''

        value = datetime.datetime.fromtimestamp(time.time())
        hr_time = value.strftime('%Y-%m-%d %H:%M:%S')

        result += '=== Possible bug report ===\n'
        result += '\t' + 'At:            ' + hr_time + '\n'
        result += '\t' + 'Using image:   ' + self.imgpath + '\n'
        result += '\t' + 'With testcase: ' + self.tester_f + '\n'
        result += '\t' + 'Cmd:           ' + (' '.join(self.cmd)) + '\n'
        result += '\t' + 'Env:           ' + str(self.env) + '\n'

        return result

    def print(self):
        print(self.fmt_report())

    def save(self):
        """ @brief Saves the bug report in humand and machine readable format 

        Machine readable format:
            
            [record]
            timestamp = <value>
            testerfile = <value>
            imgpath = <value>
            cmd = <value>
            env = <value>
        """

        with open(self.bug_db_f, 'a') as obj:
            obj.write('[record]' + '\n')
            obj.write('timestamp=' + str(time.time()) + '\n')
            obj.write('testerfile=' + self.tester_f + '\n')
            obj.write('imgpath=' + self.imgpath + '\n')
            obj.write('cmd=' + (' '.join(self.cmd)) + '\n')
            obj.write('env=' + str(self.env) + '\n')
            obj.write('\n')

        with open(self.bug_hr_f, 'a') as obj:
            obj.write(self.fmt_report())
            obj.write('\n')

