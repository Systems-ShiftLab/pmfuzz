# PMFuzz

## Dependencies
To compile, you'd need to install the following dependencies (instructions in the next step):  
1. Ubuntu 18.04¹
2. NDCTL v64 or higher
3. libunwind (`libunwind-dev`)
4. libini-config (`libini-config-dev`)
5. Python 3.6
6. GNUMake >= 3.82
7. Bash >= 4.0¹ (For workload scripts)
8. Kernel version 5.4²
9. autoconf (For PMDK)
10. bash-completions (For PMDK)

¹Required for workload scripts  
²Required for the evaluation configuration  

For compiling documentation:  
1. doxygen
2. pdflatex

## Compiling AFL and workloads
#### Step 1: Install PMDK and other dependencies
To purge existing `libdaxctl*`, `libndctl*` and install ndctl 68 and other dependencies, run:
``` shell
scripts/install-dependencies.sh
```

#### Step 2: Compile everything
To compile everything, run Make from the root of the repository:

```
make all workloads -j100
```

#### Step 3: Install python dependencies
To install python3 dependencies, run:
```shell
pip3 install -r src/pmfuzz/requirements.txt
```

## Compiling Documentation
Run `make docs` from the root, and all the documentation will be
linked in the `docs/` directory.

## Running workloads
To Run the workloads, use the `run-workloads.sh` script, e.g.,

```shell
# For running btree in baseline mode  
scripts/run-workloads.sh btree baseline
# For running btree in pmfuzz mode
scripts/run-workloads.sh btree pmfuzz
# To see all the options, run:
scripts/run-workloads.sh --help
```

These commands will run pmfuzz [pmfuzz-fuzz.py][pmfuzz-fuzz.py] with correct configuration used for the evaluation section, you might need to change the number of cores to adjust it for your machine.

## Running custom configuration
PMFuzz uses a YML based configuration to set different parameters for fuzzing, to write a custom configuration, please follow one of the existing examples in [src/pmfuzz/configs/examples/][config_examples] directory.

More information on PMFuzz's syntax is [here][1].

## Other useful information
### Env variables
**NOTE**: If a variable doesn't have a possible value next to it, that variable would be enabled by setting
it to any non-empty value (including `0`).  
1. `USE_FAKE_MMAP`=(0,1): Enables fake mmap which mounts an image in the volaile memory.
2. `PMEM_MMAP_HINT`=`<addr>`: Address of the mount point of the pool.
3. `ENABLE_CNST_IMG`=(0,1): Disables default PMDK's behaviour that generates non-identical images for same input.
4. `FI_MODE`=`(<empty or unset>|IMG_GEN|IMG_REP)`: See libpmfuzz.c
5. `FAILURE_LIST`=`<path-to-output-file>`: See libpmfuzz.c
6. `PMFUZZ_DEBUG`=(0,1): Enables debug output from libpmfuzz
6. `ENABLE_PM_PATH`: Enables deep paths in PMFuzz
7. `GEN_ALL_CS`: Partially disables the probabilistic generation of crash sites and more of them are generated from `libpmfuzz.c`
8. `IMG_CREAT_FINJ`: Disables the probabilistic generation of crash sites and all of them are generated from `libpmfuzz.c`
9. `PMFUZZ_SKIP_TC_CHECK`: Disable testcase size check in AFL++
10. `PRIMITIVE_BASELINE_MODE`: Makes workload delete image on start if the pool exists

## Adding git hook for development
Following command adds a pre-commit hook to check if the tests pass:

``` shell
git config --local core.hooksPath .githooks/
```

## Reasons for Common errors
#### 1. FileNotFoundError for instance's pid file
Raised when AFL cannot bind to a free core or no core is free.
#### 2. Random tar command failed
Check if no free disk space is left on the device
#### 3. shmget (2): No space left on device
Run:
```
ipcrm -a
```
Warning: This removes all user owned shared memory segments, don't run with superuser privilege or on a machine with other critical applications running.

[config_examples]: src/pmfuzz/configs/examples/
[pmfuzz-fuzz.py]: src/pmfuzz/pmfuzz-fuzz.py
[1]: src/pmfuzz/README.md
