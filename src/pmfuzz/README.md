# PMFuzz

## 1. Setting up PM Fuzz

Run:
```shell
pip3 install -r src/pmfuzz/requirements.txt
```

## 3. Write a configuration file for your target
`configs/examples` directory contains some examples of configuration that pmfuzz can run. If you are writing your own configuration, please note the following:

#### Include statements
PMFuzz allows importing other configuration files to it (Note: nested includes are not supported). 

#### Variable subtitution
The following variables are automatically subtituted in the config file values:
1. `%ROOT%`:   Points to the PMFuzz root directory (root of this repository)
2. `%BUILD%`:  Points to the %ROOT%/build/
3. `%LIB%`:    Points to the %ROOT%/build/lib
4. `%BIN%`:    Points to the %ROOT%/build/bin

## 2. Running PM Fuzz

To run use the script `pmfuzz-fuzz.py`:

```
usage: PMFuzz [-h] [--force-resp FORCE_RESP] [--cores-stage1 CORES_STAGE1]
              [--cores-stage2 CORES_STAGE2] [--overwrite] [--disable-stage2]
              [--dry-run] [--progress-interval PROGRESS_INTERVAL]
              [--progress-file PROGRESS_FILE] [--checks-only] [--verbose]
              [--version]
              indir outdir config
```

PMFuzz: A Persistent Memory Fuzzer, version 0.0a

### Required positional arguments:

```
  indir                 path to directory containing initial test corpus for
                        stage 1
  outdir                path to directory for generated test cases for stage
                        1, works as input for stage 2
  config                Points to the config file to use, should conform to:
                        configs/default.yaml
```

### Optional named arguments:

```
  -h, --help            show this help message and exit
  --force-resp FORCE_RESP
                        Forces response to questions
  --cores-stage1 CORES_STAGE1, -c1 CORES_STAGE1
                        Maximum cores stage 1 fuzzer can use, default: 1. Can
                        be specified in config.
  --cores-stage2 CORES_STAGE2, -c2 CORES_STAGE2
                        Maximum cores stage 2 fuzzer can use, default: 1. Can
                        be specified in config.
  --overwrite, -o       Overwrite the output directory
  --disable-stage2, -1  Disables stage 2. Can be specified in config.
  --dry-run             Enables dry run, no actual commands are executed
                        (Deprecated)
  --progress-interval PROGRESS_INTERVAL
                        Interval in seconds for recording progress, default:
                        60 seconds. Can be specified in config.
  --progress-file PROGRESS_FILE
                        Output file for writing progress to a file. Can be
                        specified in config.
  --checks-only         Performs startup checks and exits
  --verbose, -v         Enables verbose logging to stdout
  --version             show program's version number and exit
```

