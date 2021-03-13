""" @file pretty_print.py 

@brief Print functions """

import datetime
import os
import inspect
import shlex
import sys
import time


CBLACK  = '\33[30m'
CRED    = '\33[31m'
CGREEN  = '\33[32m'
CYELLOW = '\33[33m'
CBLUE   = '\33[34m'
CVIOLET = '\33[35m'
CBEIGE  = '\33[36m'
CWHITE  = '\33[37m'

CGREY    = '\33[90m'
CRED2    = '\33[91m'
CGREEN2  = '\33[92m'
CYELLOW2 = '\33[93m'
CBLUE2   = '\33[94m'
CVIOLET2 = '\33[95m'
CBEIGE2  = '\33[96m'
CWHITE2  = '\33[97m'

CGREYBG    = '\33[100m'
CREDBG2    = '\33[101m'
CGREENBG2  = '\33[102m'
CYELLOWBG2 = '\33[103m'
CBLUEBG2   = '\33[104m'
CVIOLETBG2 = '\33[105m'
CBEIGEBG2  = '\33[106m'
CWHITEBG2  = '\33[107m'

ENDC = '\033[0m'
BOLD = '\033[1m'
UNDERLINE = '\033[4m'


OFFSET = 60

def format_paths(text):
    tokens = shlex.split(text)
    result = []
    for token in tokens:
        token_utf8 = token.encode('utf-8')
        if (os.path.exists(token_utf8) or os.access(os.path.dirname(token_utf8), \
                                        os.W_OK)):
            result.append(CGREY + token + ENDC)
        else:
            result.append(token)
    return ' '.join(result)

def curtime():
    result = str(datetime.datetime.now().strftime(' <%H:%M:%S> '))
    return result

def pid():
    return '%5d' % os.getpid()

def caller_name():
    """ @brief Returns the class name of the object that called the caller 
    function """

    class_nm = CVIOLET2 + '<unknown>' + ENDC
    method_nm = CYELLOW2 + '' + ENDC
    stack = inspect.stack()

    if 'self' in stack[2][0].f_locals:
        class_nm = CVIOLET2 + stack[2][0].f_locals['self'].__class__.__name__ \
                    + ENDC
    
    if hasattr(stack[2][0], 'f_code'):
        method_nm = ':' + CYELLOW2 + stack[2][0].f_code.co_name + '()' + ENDC

    return ('%' + str(OFFSET) + 's: ') % (class_nm + method_nm)

def printi(msg, emph=False, format_path=True):
    """ Information """
    
    msg_ = msg
    if format_path:
        msg_ = format_paths(str(msg))
        
    emph_s = ENDC if not emph else ''
    print(caller_name() + CGREEN2 + curtime() + pid() + '[' + 'i' + '] '\
        + emph_s + msg_ + ENDC)

def printp(msg, countdown=None):
    """ Progress """
    msg_ = format_paths(str(msg))
    sys.stdout.write(caller_name() + CBLUE + curtime() + pid() + '[' + '*' + '] '\
        + ENDC + msg_)
    cur = countdown
    if countdown != None:
        while cur > 0:
            cur -= 1
            time.sleep(1)
            sys.stdout.write('\r' + CBLUE + curtime() + pid() + '[' + '*' + '] ' \
                + ENDC + '(' + str(cur) + 's) ' + msg_)
            sys.stdout.flush()
    sys.stdout.write('\n')


def printw(msg, emph=False):
    """ Warning """
    msg_ = format_paths(str(msg))
    emph_s = ENDC if not emph else ''
    print(caller_name() + CYELLOW2 + curtime() + pid() + '[' + '!' + '] '\
        + emph_s + msg_ + ENDC )

def printe(msg):
    """ Error """
    msg_ = format_paths(str(msg))
    print(caller_name() + CRED2 + curtime() + pid() + '[' + 'E' + '] '\
        + ENDC + msg_)

def printv(msg):
    """ Verbose """
    msg_ = format_paths(str(msg))
    print(caller_name() + CBEIGE2 + curtime() + pid() + '[' + 'V' + '] '\
        + msg_ + ENDC)

def printoff(msg, color=CWHITE):
    """ Print with offset """
    print(color)
    for line in msg.split('\n'):
        print((' ' * (OFFSET-4*len(ENDC))) + line)
    print(ENDC)