---
title: libpmfuzz
section: 7
header: PMFuzz Programmer's Manual
date: March 2021
---

# NAME
**libpmfuzz**, **libfakepmfuzz** - PMFuzz interface library

# SYNOPSIS
```
#include <pmfuzz/pmfuzz.h>

afl-clang ... -lpmfuzz
cc ... -lfakepmfuzz
```

# DESCRIPTION

**libpmfuzz** provides the interface to PMFuzz using a set of
annotations functions and macros. **libpmfuzz** requires the modified
AFL++ clang compiler to compile the linked program.

PMFuzz also provides **libfakepmfuzz** that allows linking with any
C/C++ compilers but doesn't provide any real tracking mechanism.

# VERSIONING

# ENVIRONMENT

# EXAMPLE

# SEE ALSO

