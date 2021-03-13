[![PMFuzz](https://github.com/Systems-ShiftLab/pmfuzz/actions/workflows/python-app.yml/badge.svg)](https://github.com/Systems-ShiftLab/pmfuzz/actions/workflows/python-app.yml)

# PMFuzz

PMFuzz is a testcase generation tool to generate high-value tests cases for PM testing tools (XFDetector, PMDebugger

If you find PMFuzz useful in your research, please cite:

> Sihang Liu, Suyash Mahar, Baishakhi Ray, and Samira Khan  
> [PMFuzz: Test Case Generation for Persistent Memory Programs](https://www.cs.virginia.edu/~smk9u/Liu_PMFuzz_ASPLOS21.pdf)  
> The International Conference on Architectural Support for Programming Languages and Operating Systems (ASPLOS), 2021


<details><summary>*BibTex*</summary>
<p>

```
@inproceedings{liu2021pmfuzz,
  title={PMFuzz: Test Case Generation for Persistent Memory Programs},
  author={Liu, Sihang and Mahar, Suyash and Ray, Baishakhi and Khan, Samira},
  booktitle={Proceedings of the Twenty-sixth International Conference on Architectural Support for Programming Languages and Operating Systems},
  year={2021}
}
```

</p>
</details>

## Dependencies
PMFuzz was tested using the following environment configuration, other versions may work:  
1. Ubuntu 18.04
2. NDCTL v64 or higher
3. libunwind (`libunwind-dev`)
4. libini-config (`libini-config-dev`)
5. Python 3.6
6. GNUMake >= 3.82
7. Kernel version 5.4
8. Anaconda or virtualenv (recommended)

For compiling documentation:  
1. doxygen
2. pdflatex
3. doxypypy

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

## Running custom configuration
PMFuzz uses a YML based configuration to set different parameters for
fuzzing, to write a custom configuration, please follow one of the
existing examples in [src/pmfuzz/configs/examples/][config_examples]
directory.

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

Warning: This removes all user owned shared memory segments, don't run
with superuser privilege or on a machine with other critical
applications running.


## Licensing
PMFuzz is licensed under BSD-3-clause except noted otherwise.

PMFuzz uses of the following open-source software:
1. Preeny (Copy of
   [license](https://github.com/zardus/preeny/blob/ef63823020f373b3729a14ee4106b45eefa3271c/LICENSE))
   Preeny was modified to fix a bug in desock. All changes are
   contained in
   [vendor/pathes/preeny_path](vendor/patches/preeny.git_patch)
2. AFL++ (Copy of [license](vendor/AFLplusplus-2.63c/LICENSE)) AFL++ was modified to include support for
   persistent memory tracking for PMFuzz.

[config_examples]: src/pmfuzz/configs/examples/
[pmfuzz-fuzz.py]: src/pmfuzz/pmfuzz-fuzz.py
[1]: src/pmfuzz/README.md
