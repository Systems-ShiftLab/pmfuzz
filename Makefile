#* file                    Makefile
#* details                 Build script for building workloads and pmfuzz. Use
#*                         make help to list all targets
#* SPDX-License-Identifier BSD-3-Clause
#* copyright               2020-21 PMFuzz Authors

DIR			:= $(dir $(realpath $(firstword $(MAKEFILE_LIST))))

INCLUDE_DIR		:= $(DIR)include/
VENDOR_DIR		:= $(DIR)vendor/
BUILD_DIR		:= $(DIR)build/
LIBS_DIR		:= $(BUILD_DIR)lib/
BIN_DIR 		:= $(BUILD_DIR)bin/


OS			= $(shell lsb_release -si)
ARCH			= $(shell uname -m | sed 's/x86_//;s/i[3-6]86/32/')
VER  			= $(shell lsb_release -sr)

REDCOLOR		= "\033[91;1m"
CCCOLOR			= "\033[34m"
LINKCOLOR		= "\033[34;1m"
SRCCOLOR 		= "\033[33m"
BINCOLOR 		= "\033[37;1m"
MAKECOLOR		= "\033[32;1m"
ENDCOLOR		= "\033[0m"

##
## Configure the compiler
##
ifneq ($(ENABLE_GCOV),)

warning_msg = $(shell echo $(REDCOLOR)WARN Enabling compilation using gcov, \
	AFL will be disabled$(ENDCOLOR))
$(info $(warning_msg))
warning_msg = $(shell echo $(REDCOLOR)\>\>\>\> Use \`make clean\` if a \
	different version was compiled earlier \<\<\<\<$(ENDCOLOR))
$(info $(warning_msg))

AFL_CC					= $(CC)
AFL_CXX					= $(CXX)
PMFUZZ_CFLAGS				= -coverage -DDISABLE_PMFUZZ
PMFUZZ_LIBS				= -lgcov --coverage
else

AFL_CC					= afl-clang-fast
AFL_CXX					= afl-clang-fast++

# Enable LAF-Intel
export AFL_LLVM_LAF_SPLIT_SWITCHES = 1
export AFL_LLVM_LAF_TRANSFORM_COMPARES = 1
export AFL_LLVM_LAF_SPLIT_COMPARES = 1

# Enable InsTrim: 
# 	InsTrim: Lightweight Instrumentation for Coverage-guided Fuzzing
# export AFL_LLVM_INSTRUMENT = CFG

# Enable ngram: 
# 	"Be Sensitive and Collaborative: Analzying Impact of Coverage Metrics
#        in Greybox Fuzzing", by Jinghan Wang, et. al.
export AFL_LLVM_NGRAM_SIZE = 4

endif

ifndef V
QUIET_LN = @printf '    %b %b\n' \
	$(LINKCOLOR)LN$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR) 1>&2;
endif

##
## Basic checks
##
ifneq ($(OS),Ubuntu)
$(error This makefile currently only works on Ubuntu 18.X/20.X)
endif

ifneq ($(VER),18.04)
ifneq ($(VER),18.10)
ifneq ($(VER),20.04)
ifneq ($(VER),20.10)
$(error This makefile currently only works on Ubuntu 18.X/20.X)
endif
endif
endif
endif

##
## Binutils configuration
##
MKINFO		:= $(shell makeinfo --version 2> /dev/null)
BINUTILS_DIR	:= $(BUILD_DIR)binutils-2.34/

##
## PMFuzz configuration
##
PMFUZZ_DIR	:= $(DIR)src/pmfuzz/

##
## Annotation pass configuration
##
PASS_DIR	:= $(DIR)src/annotation-pass/

##
## AFL configuration
##
LLVM_DIR 	:= $(BUILD_DIR)llvm-9/
AFL_DIR		:= $(DIR)vendor/AFLplusplus-2.63c/
export AFL_LLVM_CFLAGS 	:= 

##
## XFD configuration
##
XFD_DIR		= $(DIR)vendor/xfdetector/

##
## Preeny configuration
##
PREENY_DIR	= $(DIR)vendor/preeny/

##
## Redis configuration
##
REDIS_DIR	= $(DIR)vendor/redis-3.2-nvml/

##
## Docs
##
DOCS_DIR		:= $(DIR)docs/

export REDIS_CFLAGS	= -I$(INCLUDE_DIR) $(PMFUZZ_CFLAGS)

export REDIS_LIBS	= -L$(LIBS_DIR)
export REDIS_LIBS	+= -lxfdetector_interface
export REDIS_LIBS	+= -lpmtracefuncts
export REDIS_LIBS	+= -lpmfuzz
export REDIS_LIBS	+= -Wl,-R$(LIBS_DIR)

ifneq ($(ENABLE_GCOV),)
REDIS_TGT		= noopt
endif

##
## Memcached configuration
##
MEMCACHED_DIR	 	:= $(DIR)vendor/memcached-pmem/

##
## MariaDB configuration
##
MARIA_DB_DIR	 	:= $(DIR)vendor/pmem-mariadb/

##
## PMDK configuration
##
PMDK_DIR	 	= $(DIR)vendor/pmdk/

export EXTRA_CFLAGS	+= $(PMFUZZ_CFLAGS)
export EXTRA_CFLAGS 	+= -I$(DIR)include/
export EXTRA_CFLAGS 	+= -I$(DIR)vendor/xfdetector/xfdetector/include
export EXTRA_CFLAGS 	+= -DPMFUZZ
export EXTRA_CFLAGS 	+= -Wno-error
export EXTRA_CFLAGS 	+= -O0
export EXTRA_CFLAGS 	+= -g
export EXTRA_CXXFLAGS 	+= $(PMFUZZ_CFLAGS)
export EXTRA_CXXFLAGS 	+= $(EXTRA_CFLAGS)

export EXTRA_LDFLAGS	+= -L$(LIBS_DIR)
export EXTRA_LDFLAGS	+= -Wl,--no-fatal-warnings
export EXTRA_LDFLAGS	+= -Wl,-R$(LIBS_DIR)

export EXTRA_LIBS	+= -lxfdetector_interface
export EXTRA_LIBS	+= -lpmtracefuncts
export EXTRA_LIBS	+= -lpmfuzz
export EXTRA_LIBS	+= $(PMFUZZ_LIBS)
export AFL_PATH		= $(AFL_DIR)

#HEADER: Targets
#BRIEF: Builds everything except for non-PMDK workloads
all:
	$(MAKE) basic

basic:
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	$(MAKE) builddir
	$(MAKE) pmdk
	@echo $(DIR)

#HEADER: Workloads
#BRIEF: Builds workloads not included with PMDK
workloads: redis memcached preeny
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	@echo "All workloads compiled"

$(BIN_DIR)redis-%:
	$(QUIET_LN)ln -Lfs ${subst $(BIN_DIR),$(REDIS_DIR)src/,$@} $@

$(BUILD_DIR).redis_deps:
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	$(MAKE) -C $(REDIS_DIR)deps linenoise hiredis geohash-int lua jemalloc \
		CFLAGS+="-no-pie"
	@touch $@

#BRIEF: Builds Redis
redis: $(BUILD_DIR).redis_deps
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	$(MAKE) $(REDIS_TGT) PATH=$(LLVM_DIR)bin:$(BIN_DIR):$(PATH) \
		-C $(REDIS_DIR) USE_PMDK=yes STD=-std=gnu99 \
		CC=$(AFL_CC) CXX=$(AFL_CXX) \
		PMFUZZ_CFLAGS="$(EXTRA_CFLAGS) -DPMFUZZ" PMFUZZ_LIBS="$(EXTRA_LIBS)\
		$(EXTRA_LDFLAGS)"
	$(MAKE) $(BIN_DIR)redis-server $(BIN_DIR)redis-cli

$(BIN_DIR)memcached:
	$(QUIET_LN)ln -Lfs ${subst $(BIN_DIR),$(MEMCACHED_DIR),$@} $@

$(BUILD_DIR).memcached_configured:
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	(cd $(MEMCACHED_DIR) && CFLAGS="$(EXTRA_CFLAGS)" LDFLAGS="$(EXTRA_LDFLAGS)"\
		LIBS="$(EXTRA_LIBS)" ./configure --enable-pslab --disable-coverage)
	@touch $@

#BRIEF: Builds Memcached
memcached: $(BUILD_DIR).memcached_configured
	$(MAKE) PATH=$(LLVM_DIR)bin:$(BIN_DIR):$(PATH) -C $(MEMCACHED_DIR)\
		CC=$(AFL_CC) CXX=$(AFL_CXX)
	$(MAKE) $(BIN_DIR)memcached

##
## General Rules
##
builddir:
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	$(shell mkdir -p $(BUILD_DIR))
	$(shell mkdir -p $(LIBS_DIR))
	$(shell mkdir -p $(BIN_DIR))


##
## Preeny rules
##
$(LIBS_DIR)%.so:
	$(QUIET_LN)ln -Lfs ${subst $(LIBS_DIR),$(PREENY_DIR)build/lib/,$@} $@

#HEADER: Tools
#BRIEF: Builds preeny
preeny:
	git submodule update --init
	- (cd $(PREENY_DIR) && git apply ../patches/preeny.git_patch)
	mkdir -p $(PREENY_DIR)build
	(cd $(PREENY_DIR)build && cmake $(PREENY_DIR))
	$(MAKE) -C $(PREENY_DIR)build
	$(MAKE) $(subst $(PREENY_DIR)build/lib/,$(LIBS_DIR),\
		$(shell find $(PREENY_DIR)build/lib/*.so \
		-maxdepth 1 -executable -type f,l))

##
## Rules for building PMFuzz's LLVM annotation pass 
##
$(LIBS_DIR)pmfuzz_annot_pass.so: $(BUILD_DIR)llvm-9 
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	$(QUIET_LN)ln -fs $(PASS_DIR)pmfuzz_annot_pass.so $@

pmfuzz_annot_pass: $(LLVM_DIR)
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	@echo $(LIBS_DIR)
	@PATH=$(BUILD_DIR)llvm-9/bin:$(PATH); $(MAKE) -C src/annotation-pass
	$(MAKE) $(LIBS_DIR)pmfuzz_annot_pass.so

##
## Rules for building AFL
##
$(BIN_DIR)afl-%:
	$(QUIET_LN)ln -Lfs ${subst $(BIN_DIR),$(AFL_DIR),$@} $@

gen-afl-links:
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	$(MAKE) $(subst $(AFL_DIR),$(BIN_DIR),\
		$(shell find $(AFL_DIR)afl-* -maxdepth 1 -executable -type f,l))

# Download and extract LLVM 9.0.0
$(LLVM_DIR):
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	@echo 'Donwloading LLVM'
	wget -P $(BUILD_DIR) -c \
		'https://releases.llvm.org/9.0.0/clang+llvm-9.0.0-x86_64-linux-gnu-ubuntu-18.04.tar.xz'
	mkdir -p $(LLVM_DIR)
	tar -C $(LLVM_DIR) --strip-components=1 -xf \
		$(BUILD_DIR)clang+llvm-9.0.0-x86_64-linux-gnu-ubuntu-18.04.tar.xz

# Download, extract and compile binutils
$(BINUTILS_DIR):
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
ifndef MKINFO
	@echo Installing texinfo for compiling binutils
	sudo apt-get install texinfo
endif
	@echo
	@echo 'Downloading binutils'
	@echo
	wget -P $(BUILD_DIR) -c 'https://ftp.gnu.org/gnu/binutils/binutils-2.34.tar.gz'
	tar -C $(BUILD_DIR) -xf $(BUILD_DIR)/binutils-2.34.tar.gz
	(cd $(BINUTILS_DIR) && $(BINUTILS_DIR)/configure --without-gas --enable-gold \
			--without-bfd --without-gprof --without-ld --without-libctf \
			--without-opcodes --without-zlib --prefix=$(BUILD_DIR) )
	$(MAKE) -C $(BINUTILS_DIR)
	$(MAKE) -C $(BINUTILS_DIR) install

#BRIEF: Builds AFL (depends on pmfuzz_annot_pass)
afl: pmfuzz_annot_pass
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	$(MAKE) -C $(AFL_DIR) all
	@PATH=$(BUILD_DIR)llvm-9/bin:$(PATH); \
		$(MAKE) -C $(AFL_DIR)llvm_mode CC=clang CXX=clang++ 
	$(MAKE) gen-afl-links

##
## Rules for building XFDetector
##
$(BIN_DIR)xfdetector:
	$(QUIET_LN)ln -fs $(XFD_DIR)/xfdetector/build/app/xfdetector $@

gen-xfdetector-links:
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	$(MAKE) $(BIN_DIR)xfdetector
	$(QUIET_LN)ln -fs $(shell find $(XFD_DIR)/xfdetector/build/lib/*.so \
		-maxdepth 1 -type f,l) $(LIBS_DIR)

#BRIEF: Builds XFD
xfdetector:
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
ifeq ($(PIN_ROOT),)
	@printf ' %b %b %b\n' $(REDCOLOR)ERROR$(ENDCOLOR) \
		$(BINCOLOR)'PIN_ROOT env variable not set,'\
		'PMFuzz needs it to compile XFDetector. Check readme.'$(ENDCOLOR)
	@exit 1
endif
	$(MAKE) -C $(XFD_DIR)
	$(MAKE) gen-xfdetector-links
##
## XFD Trace functions
##
gen-trace-functs-links:
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	$(QUIET_LN)ln -fs $(shell find $(DIR)include/*.so -maxdepth 1 -type f,l) \
		$(LIBS_DIR)

#BRIEF: Builds tracing functions
trace-functs:
	$(MAKE) -C $(DIR)include/ PMFUZZ_CFLAGS="$(PMFUZZ_CFLAGS)"
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	$(MAKE) gen-trace-functs-links

##
## Rules for building PMDK
##

## Builds PMDK (depends on: afl, XFD, trace-functs)
pmdk: afl xfdetector preeny trace-functs # $(BINUTILS_DIR) 
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	$(MAKE) PATH=$(BIN_DIR):$(LLVM_DIR)bin:$(PATH) -C $(PMDK_DIR) \
		CC=$(AFL_CC) CXX=$(AFL_CXX) OBJCOPY=llvm-objcopy
	sudo AFL_PATH=$(AFL_PATH) PMFUZZ_LIBS="$(PMFUZZ_LIBS)" \
		PATH=$(LLVM_DIR)bin:$(BIN_DIR):$(PATH) $(MAKE) -C $(PMDK_DIR) \
		install  CC=$(AFL_CC) CXX=$(AFL_CXX) OBJCOPY=llvm-objcopy


#HEADER: Tests
#BRIEF: Runs tests
check:
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	$(MAKE) -C $(PMFUZZ_DIR) tests

$(DOCS_DIR)programming_manual:
	$(QUIET_LN)ln -fs $(PMFUZZ_DIR)docs/html  $(DOCS_DIR)programming_manual

$(DOCS_DIR)programming_manual.pdf:
	$(QUIET_LN)ln -fs $(PMFUZZ_DIR)docs/latex/refman.pdf  \
		$(DOCS_DIR)programming_manual.pdf

gen-docs-links: $(DOCS_DIR)programming_manual $(DOCS_DIR)programming_manual.pdf
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)

#HEADER: Documentation
#BRIEF: Compiles documentation
docs:
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	$(MAKE) -C $(PMFUZZ_DIR) docs
	$(MAKE) gen-docs-links

#HEADER: Installation
#BRIEF: Installs PMFuzz to system path
install:
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	sudo cp $(DIR)docs/manpages/pmfuzz-fuzz.1 /usr/local/share/man/man1/

#BRIEF: Uninstalls PMFuzz to system path
uninstall:
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	-sudo rm /usr/local/share/man/man1/pmfuzz-fuzz.1

#HEADER: Cleanup
#BRIEF: Remove all generated files, including build directory
clean-all: clean
	-rm -rf $(BUILD_DIR)

#BRIEF: Remove all generated files, excluding build directory
clean:
	@printf '%b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	-$(MAKE) -C $(AFL_DIR) clean
	-$(MAKE) -C $(PMDK_DIR) clobber
	-$(MAKE) -C $(DIR)include/ clean
	-$(MAKE) -C $(PASS_DIR) clean
	-$(MAKE) -C $(REDIS_DIR) clean dist-clean
	-$(MAKE) -C $(MEMCACHED_DIR) clean
	-$(MAKE) -C src/annotation-pass clean
	-$(MAKE) -C $(PREENY_DIR) clean
	- rm -f $(BUILD_DIR).*

TARGET_MAX_CHAR_NUM := 20

#HEADER: Other

#BRIEF: Shows this message
help:
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	@echo ''
	@echo 'Usage:'
	@echo '  make <target>'
	@awk '/^[a-zA-Z\-_0-9]+:/ { \
		helpMessage = match(lastLine, /^#BRIEF: (.*)/); \
		if (helpMessage) { \
			helpCommand = substr($$1, 0, index($$1, ":")); \
			helpMessage = substr(lastLine, RSTART + 8, RLENGTH); \
			printf "    %-$(TARGET_MAX_CHAR_NUM)s %s\n", helpCommand, helpMessage; \
		}\
	} \
	{ \
		helpMessage = match(lastLine, /^#HEADER: (.*)/); \
		if (helpMessage) { \
			header = substr(lastLine, RSTART + 9, RLENGTH); \
			printf "\n%s:\n", header; \
		}; \
	lastLine = $$0 }' $(MAKEFILE_LIST)

.PHONY: clean docs clean-all $(BIN_DIR)afl-%
