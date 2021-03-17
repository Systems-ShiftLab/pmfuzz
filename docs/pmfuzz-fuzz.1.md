---
title: pmfuzz-fuzz
section: 1
header: PMFuzz Programmer's Manual
date: March 2021
---

# NAME
**pmfuzz-fuzz** - Generating high-value testcases for triggering
crash-consistency PM programs.

# SYNOPSIS
**pmfuzz-fuzz** [-h] [--force-resp FORCE_RESP] [--cores-stage1 CORES_STAGE1] [--cores-stage2 CORES_STAGE2] [--overwrite] [--disable-stage2] [--dry-run] [--progress-interval PROGRESS_INTERVAL] [--progress-file PROGRESS_FILE] [--checks-only] [--verbose] [--version] indir outdir config

# DESCRIPTION
PMFuzz: A Persistent Memory Fuzzer, version 1.0 by ShiftLab

# OPTIONS
**indir**
: path to directory containing initial test corpus for stage 1. See [INPUT-DIRECTORY](#INPUT-DIRECTORY).

**outdir**
: path to directory for generated test cases for stage 1, works as input for stage 2.  See OUTPUT-DIRECTORY.

**config** 
: Points to the config file to use, should conform to: configs/default.yaml. See CONFIGURATION-FILE.

**--force-resp** *FORCE_RESP*
: Forces response to questions

**--cores-stage1** *CORES_STAGE1*, **-c1** *CORES_STAGE1*
: Maximum cores stage 1 fuzzer can use, default: 1. Can be specified in config.

**--cores-stage2** *CORES_STAGE2*, **-c2** *CORES_STAGE2*
: Maximum cores stage 2 fuzzer can use, default: 1. Can be specified in config.

**--overwrite**, **-o**
: Overwrite the output directory

**--disable-stage2**, **-1**
: Disables stage 2.  Can be specified in config.

**--dry-run**
: Enables dry run, no actual commands are executed (Deprecated)

**--progress-interval** *PROGRESS_INTERVAL*
: Interval in seconds for recording progress, default: 60 seconds.  Can be specified in config.

**--progress-file** *PROGRESS_FILE*
: Output file for writing progress to a file. Can be specified in config.

**--checks-only**
: Performs startup checks and exits

**--verbose**, **-v**
: Enables verbose logging to stdout

**--version**
: show program's version number and exit

# EXAMPLES
To run PMFuzz without any additional output:

```
pmfuzz-fuzz \
	./input_directory ./output_directory ./configs/default.yml
```

To record fuzzing progress, use:

```
pmfuzz-fuzz \
	--progress-file=/tmp/fuzz_progress
	./input_directory ./output_directory ./configs/default.yml
```

To get verbose output of the PMFuzz´s current step, use:

```
pmfuzz-fuzz \
	--verbose \
	./input_directory ./output_directory ./configs/default.yml
```

# INPUT DIRECTORY
PMFuzz needs a non-empty directory with seed inputs for fuzzing. These
inputs should be command inputs that PMFuzz can execute using the
target program. PMFuzz directly uses these inputs using AFL, see
afl-fuzz(1).

# OUTPUT DIRECTORY
On each run, pmfuzz will write to the following files

1.  **\<output_dirname>/**: Contains all the testcases, pool images, crash sites and other information needed to run PMFuzz.
2.  **\<output_dirname>.progress**: Tracks the progress of the fuzzing.	   
3.  **\<output_dirname>.progress.events**: Tracks events like stage transitions in PMFuzz.

## Output Directory Structure
The output directory has the following structure

```
output directory name
    +-- @info
    +-- @dedup
    |    +-- id=001.pm_pool
    |    +-- id=001.testcase
    |    +-- id=001.min.testcase
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
         |    +-- ...
         |    +-- id=0002,id=002.testcase
         |    +-- ...
         +-- pm_images
         |    +-- id=0001,id=001.pm_pool
         |    +-- ...
         |    +-- id=0002,id=001.pm_pool
         |    +-- ...
         +-- @dedup_sync
              +-- id=001.pm_pool
              +-- id=001.testcase
              +-- id=001.timer
              +-- ...
```

## Progress Report
The output directory is co-located with progress file with the same
name as the output directory but has an file-extension of type
'`.progress`'. The columns represent the following values, in-order they
appear:

```
Current time, Total testcases, Total PM testcases, Total paths, Total
PM paths, Executions/s, internal-execution-parameter
```
## Naming Convention
Each testcase/pm_image/crash_site name is a sequence of one or more
id-tags. Each id-tag is of the format `id=<value>` and a sequence of
id-tags are connected using the characters `.` or `,`. If an id-tag is
after ´.´ this means that the id-tag corresponds to a failure image,
while if an id-tag starts with '`,`', then that id-tag is for a PMFuzz
generated testcase.

If a testcase has multiple IDs, they move down the hierarchy from left
to right. An example fuzzing round and corresponding file name are:

PMFuzz marks all the testcases in the input directory with a unique sequential id starting from 1:

1.  Initial testcases: `id=000001.testcase`, `id=000002.testcase` ...

2.  Next round of fuzzing uses the second testcase `id=000002.testcase`
    to generate 5 new testcases, these testcases will now be named:  
		   
	`id=000002,id=000001.testcase`  
	`id=000002,id=000002.testcase`  
	`id=000002,id=000003.testcase`  
	`id=000002,id=000004.testcase`  
	`id=000002,id=000005.testcase`  

3.  Next, PMFuzzes uses the testcase `id=00002,id=00003.testcase` to randomly generate the following crash sites:  

	`id=000002,id=000002.id=000011.testcase`  
	`id=000002,id=000002.id=000035.testcase`  
	(note the use of both kinds separator)

	Example testcase/pm_pool/crash_site names:
	* `id=000000,id=000199,id=00088.testcase`
	* `id=002310.id=000033mid=000002,id=000002.id=000035_pool`
	* `map_id=000002,id=010199.id=000004.id=000002.testcase`

# CONFIGURATION FILE
PMFuzz uses a YAML based file to configure different parameters.

**configs/examples** directory contains several examples for writing
and organizing configurations that PMFuzz can use. If you want to
write your own configuration file, include **config/default.yml** in your
new config file and change the values you need.

If you are writing your own configuration, please note the following:

## Including Other Configs
PMFuzz supports including one or more configuration files to allow easier customization.

Syntax for including config files is:

```
include:
  - base-config-1.yaml
  - base-config-2.yaml
  .
  .
  - base-config-n.yaml
```

In case of duplicate keys, values are prioritized (and overwritten) in
the order they appear. However, the file including them have highest
priority.

**Note**  
Nested includes are not supported.


## Variable Substitution
The following variables are automatically substituted in the config file values:

**%ROOT%**  
Points to the PMFuzz root directory (root of this repository)

**%BUILD%**  
Points to the `%ROOT%/build/`

**%LIB%**
Points to the `%ROOT%/build/lib`

**%BIN%**
Points to the `%ROOT%/build/bin`

## Example
Here is a simple example that runs PMDK´s RBTree workload in baseline
mode. This configuration overwrites the number of CPU cores used by
the first stage to 4. Note, lines starting with `#` are comments.

```
# Brief:
#   Runs the Baseline for rbtree

include:
  - configs/base.yml
  - configs/workload/mapcli.rbtree.yml
  - configs/run_configs/baseline.yml

pmfuzz:
  stage:
    "1":
      cores: 4
```

# ENVIRONMENT
This section defines several environment variables that may change PMFuzz´s behavior.

Values set and unset describe the behavior when the environment
variable is not set to any value and when the variable is set to any
non-empty string (including 0) respectively.

## USE_FAKE_MMAP
**1**  
Enables fake mmap by copying the contents (using memcpy) of the pool
image to the volatile memory. Mounting the pool to the volatile memory
improves fuzzing performance.

**0**  
Mounts the pool using PMDK´s default mounting functions. Before
invoking the target, PMFuzz would create a copy of the pool image and
call the target on that image. Depending on the output of the
fuzzing,PMFuzz would either save that image for future use, or discard
it.

## PMEM_MMAP_HINT
**addr**  
Address of the mount point of the pool. See libpmem(7).

**unset**  
PMDK decides the mount address of the pool.

## ENABLE_CNST_IMG
**1**  
Disables default PMDK´s behaviour that generates non-identical images for same input.
**0**  
PMFuzz generated images would have random variations that may
negatively affect the fuzzing performance and reproducibility.

## FI_MODE
**"IMG_GEN"**  
In case the the PMFUZZ_MODE env variable is set to "IMG_GEN", a
failure point is injected and the PM Image is dumped if the PM pool
has changed since the last failure injection. First failure injection
always results in an image dump.

Images dump naming pattern: `<pool file name>.<failure id>` If a failure
list file is additionally specified using the env variable, the falure
ids that generate dumps are written to that file, one per line.

**"IMG_REP"**  
Todo

For more information on FI_MODE see libpmfuzz.c.

## FAILURE_LIST
Path to a file that libpmfuzz would write the failure IDs to.

See libpmfuzz.c

## PMFUZZ_DEBUG
**1**  
Enables debug output from libpmfuzz.

**0**  
**unset**  
Disables debug output from libpmfuzz.

## ENABLE_PM_PATH
Enables deep paths in PMFuzz

## GEN_ALL_CS
Forces PMFuzz to generate all crash sites. Use with caution.

## IMG_CREAT_FINJ
Deprecated.

## PMFUZZ_SKIP_TC_CHECK
**set**  
Disable testcase size check in AFL++.

**unset**  
Enables AFL++´s default behaviour to check testcase size.

See afl-fuzz(1).

## PRIMITIVE_BASELINE_MODE
**set**  
Makes workload delete image on start if the pool exists.

# COMMON ERRORS
## FileNotFoundError for instance´s pid file
Raised when AFL cannot bind to a free core or no core is free.

## Random tar command failed
Check if device has any free space left.

## shmget (2): No space left on device
Run the following command in your shell to remove all shared memory segments:

```
$ ipcrm -a
```

**Warning**: This removes all user owned shared memory segments, don´t
run with superuser privilege or on a machine with other critical
applications running.

# PROGRAMMING PMFUZZ
To modify pmfuzz please look into **docs/programming_manual** or **docs/programming_manual.pdf**.

# BUGS
Please report bugs at: ⟨https://github.com/Systems-ShiftLab/pmfuzz/issues⟩

# SEE ALSO
libpmfuzz(7), afl-fuzz(1), afl-cmin(1), afl-tmin(1), afl-gotcpu(1)
   
# AUTHORS
PMFuzz was written by ShiftLab, University of Virginia.  ⟨https://www.cs.virginia.edu/~smk9u/shiftLab.html⟩

# DOCUMENTAION
Complete documentation for PMFuzz can be accessed online at ⟨https://github.com/Systems-ShiftLab/pmfuzz/wiki⟩
