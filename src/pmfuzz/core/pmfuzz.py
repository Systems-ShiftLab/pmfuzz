"""@file pmfuzz.py
@brief PMFuzz implementation file.

PMFuzz is implemented as a state machine.

### State transitions
    * Stage 0 -> Stage 1
    * Stage 1 -> Dedup -> Stage 2
    * Stage 2 -> Dedup -> Stage 2 (new iteration)

_Note_: These states are preserved accross different invocations of this 
        script.

### Directory Structure  

\code{.unparsed}
    outdir
      +-- @info
      +-- @dedup
      |    +-- id=001.pm_pool
      |    +-- id=001.testcase
      |    +-- id=001.min.testcase
      |    +-- ...
      |    +-- id=001,id=001.pm_pool
      |    +-- id=001,id=001.testcase
      |    +-- id=001,id=001.min.testcase
      |    +-- id=001,id=002.pm_pool
      |    +-- id=001,id=002.testcase
      |    +-- id=001,id=002.min.testcase
      |    +-- ...
      +-- stage=1,iter=0
      |    +-- afl-results
      |    |    +-- master_fuzzer
      |    |        +-- queue
      |    |    +-- slave_fuzzer01
      |    |    +-- ...
      |    +-- testcases
      |    |    +-- id=001.testcase
      |    |    +-- ...
      |    +-- pm_images
      |    |    +-- id=001.pm_pool
      |    |    +-- ...
      |    +-- @dedup_sync
      |         +-- id=001.pm_pool 
      |         +-- id=001.testcase
      |         +-- id=001.timer
      |         +-- ... 
      +-- stage=2,iter=1
           +-- afl-results
           |    +-- id=0001/master_fuzzer/queue
           |    +-- id=0002/master_fuzzer/queue
           |    +-- ...
           +-- testcases
           |    +-- id=0001,id=001.testcase
           |    +-- id=0001,id=002.testcase
           |    +-- ...
           |    +-- id=0002,id=001.testcase
           |    +-- id=0002,id=002.testcase
           |    +-- ...
           +-- pm_images
           |    +-- id=0001,id=001.pm_pool
           |    +-- id=0001,id=002.pm_pool
           |    +-- ...
           |    +-- id=0002,id=001.pm_pool
           |    +-- id=0002,id=002.pm_pool
           |    +-- ...
           +-- @dedup_sync
                +-- id=001.pm_pool 
                +-- id=001.testcase
                +-- id=001.timer
                +-- ... 
\endcode

### Testcase naming

If a testcase has multiple IDs, they move down the hierarchy from left to right

E.g.,:  
* id=grand-parent-id,id=parent-id,id=current-id.testcase  
* id=grand-parent-id,id=parent-id,id=current-id.pm_pool  
* map_id=grand-parent-id,id=parent-id,id=current-id.testcase  

@Todo Move all this to a class
"""

import time

from os import path

import handlers.name_handler as nh

from helper.common import *
from helper.prettyprint import *
from helper import config
from helper.ptimer import *
from stages.dedup import *
from stages.stage1 import *
from stages.stage2 import *
from stages.state import *


# Time to wait before starting stage 1
STAGE1_WAITTIME = 5  # sec


def run_stage1(indir:str, outdir:str, cfg, cores:int, 
        verbose:bool=False, force_yes=False, dry_run=False):
    """ @brief Wrapper for running stages.Stage1. """

    stage1 = Stage1('stage1', indir, outdir, cfg, cores, verbose, 
                    force_yes, dry_run)
    
    stage1.run()
    stage1.whatsup()

def run_stage2(indir:str, outdir:str, cfg, cores:int, 
        verbose:bool=False, force_yes=False, dry_run=False):
    """ @brief Wrapper for running stages.Stage2 """

    # Find the youngest stage
    state = State('State', indir, outdir, cfg, cores, verbose, 
                        force_yes, dry_run)
    state.sync()

    stage       = int(state.stage)
    iter_id     = int(state.iter_id)

    # Find the next stage and iter
    next_stage   = stage
    next_iter_id = iter_id

    if stage == 1:
        next_stage = 2
        next_iter_id = 1
    else:
        next_iter_id += 1

    printi('Stage transition: %d.%d -> %d.%d' \
            % (stage, iter_id, next_stage, next_iter_id))

    if stage == 1:
        # Stage 2 hasn't started yet, run the first iteration
        stage2 = Stage2(next_stage, next_iter_id, indir, outdir, 
                        cfg, cores, verbose, force_yes, dry_run)
        stage2.run()

    else:
        # Stage 2 is already running, resume operations
        stage2 = Stage2(stage, iter_id, indir, outdir, 
                        cfg, cores, verbose, force_yes, dry_run)
        
        if stage2.completed:
            printi('Stage %d completed' % stage)
            # If this iteration is completed, terminate it, run deduplication
            # and move on to the next
            stage2.terminate()
            dedup_cfg = cfg['pmfuzz']['stage']['dedup']
            run_dedup(stage, iter_id, indir, outdir, cfg, cores, 
                        verbose, force_yes, dry_run, 
                        min_corpus=dedup_cfg['global']['minimize_corpus'],
                        min_tc=dedup_cfg['global']['minimize_tc'],
                        )
            stage2.clear()
            
            # Create a new stage 2 object for next iteration
            stage2 = Stage2(next_stage, next_iter_id, indir, outdir, 
                        cfg, cores, verbose, force_yes, dry_run)
            stage2.run()

        else:

            # If stage 2 has not completed yet, let it continue
            stage2.resume()


def run_dedup(stage:int, iter_id:int, indir:str, outdir:str, 
        cfg=None, cores:int=1, verbose:bool=False, force_resp=False, 
        dry_run=False, gbl=True, fdedup=True, min_corpus=True, min_tc=True):
    """ Wrapper for running deduplication on last run stages. 

    @return None """

    dedup = Dedup(stage, iter_id, indir, outdir, cfg, cores, verbose, 
                    force_resp, dry_run)

    # Do not minimize the global corpus
    dedup.run(
        fdedup      = fdedup,
        min_corpus  = min_corpus,
        min_tc      = min_tc,
        gbl         = gbl,
    )


def collect_stage1(indir:str, outdir:str, cfg, cores1:int, cores2:int, 
        disable_stage2, verbose:bool=False, force_resp=False, dry_run=False):
    """ Wrapper for running collection on stage 1.
    
    @return None """

    stage1 = Stage1('', indir, outdir, cfg, cores1, verbose, force_resp, 
                    dry_run)

    run_dedup(1, 1, indir, outdir, cfg, cores2, verbose, force_resp, 
                    dry_run, gbl=False, fdedup=False, min_corpus=False, 
                    min_tc=False)

    stage1.collect()

    dedup = Dedup(1, 1, indir, outdir, cfg, cores1, verbose, 
                    force_resp, dry_run)
                    
    # Minimize the crash images for stage 1 before copying it to global
    dedup.run(
        fdedup      = False,
        min_corpus  = False, # 'True' for local not implemented 
        min_tc      = cfg('pmfuzz.stage.dedup.local.minimize_tc'),
        gbl         = False,
    )
    
    dedup.update_global()
                   
    # Minimize the global corpus if stage 2 is disabled
    if disable_stage2:
        dedup.run(
            fdedup      = False,
            min_corpus  = True,
            min_tc      = False,
            gbl         = True,
        )

def update_info(outdir):
    inf_dir = path.join(outdir, '@info')

    try:
        makedirs(inf_dir)
    except OSError as e:
        # printw('Handling exception: %s' % str(e))
        if path.isfile(inf_dir):
            abort('%s is not a directory.' % inf_dir)

    starttime_f = path.join(inf_dir, 'starttime')
    cmd_f       = path.join(inf_dir, 'cmd')
    state_f     = path.join(inf_dir, 'currentstate')

    if not path.isfile(starttime_f):
        with open(starttime_f, 'w') as obj:
            obj.write(str(int(time.time())))

    if not path.isfile(cmd_f):
        with open(cmd_f, 'w') as obj:
            obj.write(' '.join(sys.argv))

    if not path.isfile(state_f):
        with open(state_f, 'w') as obj:
            obj.write('Starting...')


def run_pmfuzz(indir, outdir, cfg, cores1=1, cores2=1,
        verbose:bool=False, force_yes=False, dry_run=False, 
        disable_stage2=False):
    """ PMFuzz entry point """

    update_info(outdir)

    state = State('State', indir, outdir, cfg, 
                            cores1, verbose, force_yes, dry_run)

    state.sync()

    stage_id    = int(state.stage)
    iter_id     = int(state.iter_id)

    # Deduplication output should always exist on completing stage 1
    if stage_id > 1 and not state.dedup_exists:
        abort('Result directory corrupted, deduplication is absent with'
                ' stage(%d) > 1' % stage_id)

    # Give an option to resume from the saved state
    if stage_id != 1 and stage_id != 0:
        resp = ask_yn('Running PMFuzz found: stage %d, iter %d, ' \
                            %(stage_id, iter_id) + 'resume', force_yes)
        if not resp:
            abort('Resume cancelled.')

    # Run the state machine
    while True:

        # Update state        
        state.sync()

        stage_id    = int(state.stage)
        iter_id     = int(state.iter_id)

        if stage_id != 0:
            # Always run deduplication on stage 1 first
            collect_stage1(indir, outdir, cfg, cores1, cores2, disable_stage2,
                verbose, force_yes, dry_run)
        
        # No stage is running
        if stage_id == 0:
            run_stage1(indir, outdir, cfg, cores1, verbose, force_yes, 
                dry_run)

            # Create a timer for future
            ptimer = PTimer(path.join(outdir, nh.get_outdir_name(1, 1)))
            ptimer.start_new(STAGE1_WAITTIME)
        
        # Stage 1 is already is running
        elif stage_id == 1 and not disable_stage2:

            # Continue to stage 2 if stage 1 timer has expired
            timer = PTimer(path.join(outdir, nh.get_outdir_name(1, 1)))
            if timer.expired():
                printi('Starting to stage 2 (elapsed: %s)' % timer.elapsed_hr())
                run_stage2(indir, outdir, cfg, cores2, verbose, 
                            force_yes, dry_run)

        elif stage_id == 2 and not disable_stage2:
            # Run/resume stage 2
            run_stage2(indir, outdir, cfg, cores2, verbose, 
                        force_yes, dry_run)

        elif not disable_stage2:
            abort('Unimplemented')

        time.sleep(2)

if __name__ == '__main__':
    abort('Cannot run %s directly, check README.' % sys.argv[0])
