import doctest
import sys

import handlers.name_handler as nh

from helper.parallel import Parallel

def test_parallel():
    def dummy(val1, val2):
        print('Val1: %d, val2: %d' % (val1, val2))

    prl_obj = Parallel(dummy, 2)

    for i in range(10):
        prl_obj.run([i, i*i])

    prl_obj.wait()

    return (0, 1)

def main():
    f1, t1 = doctest.testmod(nh, verbose=False)

    f2, t2 = test_parallel()

    failure_count = f1 + f2
    test_count = t1 + t2

    print('%d of %d tests failed.' % (failure_count, test_count))

    exitcode = 0
    if failure_count > 0:
        exitcode = 1

    sys.exit(exitcode)

if __name__  == '__main__': 
    main()