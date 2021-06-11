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
## Preeny configuration
##
PREENY_DIR	= $(DIR)vendor/preeny/

##
## Docs
##
DOCS_DIR		:= $(DIR)docs/

export AFL_PATH		= $(AFL_DIR)

#HEADER: Targets
#BRIEF: Builds everything
all:
	$(MAKE) builddir
	$(MAKE) basic

basic: afl preeny trace-functs
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	@echo $(DIR)

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
	wget -nv -P $(BUILD_DIR) \
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

	cp $(DIR)docs/manpages/*.1 /usr/local/share/man/man1/
	cp $(DIR)docs/manpages/*.7 /usr/local/share/man/man7/
	ln -fs /usr/local/share/man/man7/libpmfuzz.7 /usr/local/share/man/man7/libfakepmfuzz.7

	cp $(LIBS_DIR)libpmfuzz.so /usr/local/lib/libpmfuzz.so.1.0.0
	ln -fs /usr/local/lib/libpmfuzz.so.1.0.0 /usr/local/lib/libpmfuzz.so.1.0 
	ln -fs /usr/local/lib/libpmfuzz.so.1.0.0 /usr/local/lib/libpmfuzz.so.1   
	ln -fs /usr/local/lib/libpmfuzz.so.1.0.0 /usr/local/lib/libpmfuzz.so     

	cp $(LIBS_DIR)libfakepmfuzz.so /usr/local/lib/libfakepmfuzz.so.1.0.0
	ln -fs /usr/local/lib/libfakepmfuzz.so.1.0.0 /usr/local/lib/libfakepmfuzz.so.1.0 
	ln -fs /usr/local/lib/libfakepmfuzz.so.1.0.0 /usr/local/lib/libfakepmfuzz.so.1   
	ln -fs /usr/local/lib/libfakepmfuzz.so.1.0.0 /usr/local/lib/libfakepmfuzz.so     

	cp $(LIBS_DIR)pmfuzz_annot_pass.so /usr/local/lib/pmfuzz_annot_pass.so.1.0.0

	mkdir -p /usr/local/pmfuzz
	cp -r docs/ include/ scripts/ src/ vendor/ VERSION LICENSE \
		/usr/local/pmfuzz/
	ln -fs /usr/local/pmfuzz/src/pmfuzz/pmfuzz-fuzz.py /usr/local/bin/pmfuzz-fuzz

	ldconfig /usr/local/lib

	mkdir -p /usr/local/include/pmfuzz

	cp include/*.h /usr/local/include/pmfuzz


#BRIEF: Uninstalls PMFuzz to system path
uninstall:
	@printf '  %b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	rm -f /usr/local/share/man/man1/pmfuzz-fuzz.1 \
		/usr/local/share/man/man7/libpmfuzz.7 \
		/usr/local/share/man/man7/libfakepmfuzz.7

	rm -f /usr/local/lib/libpmfuzz.so.1.0.0
	rm -f /usr/local/lib/libpmfuzz.so.1.0
	rm -f /usr/local/lib/libpmfuzz.so.1
	rm -f /usr/local/lib/libpmfuzz.so

	rm -f /usr/local/lib/libfakepmfuzz.so.1.0.0
	rm -f /usr/local/lib/libfakepmfuzz.so.1.0
	rm -f /usr/local/lib/libfakepmfuzz.so.1
	rm -f /usr/local/lib/libfakepmfuzz.so

	rm -f /usr/local/lib/pmfuzz_annot_pass.so

	rm -rf /usr/local/pmfuzz
	rm -f /usr/local/pmfuzz-fuzz

	rm -rf /usr/local/include/pmfuzz


#HEADER: Cleanup
#BRIEF: Remove all generated files, including build directory
clean-all: clean
	-rm -rf $(BUILD_DIR)

#BRIEF: Remove all generated files, excluding build directory
clean:
	@printf '%b %b\n' $(MAKECOLOR)MAKE$(ENDCOLOR) $(BINCOLOR)$@$(ENDCOLOR)
	-$(MAKE) -C $(AFL_DIR) clean
	-$(MAKE) -C $(DIR)include/ clean
	-$(MAKE) -C $(PASS_DIR) clean
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
