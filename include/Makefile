CFLAGS		+= -fPIC -g -Wall -Wextra $(PMFUZZ_CFLAGS)
CFLAG_SH	+= -shared
LDFLAGS		+= -pthread  -lunwind -lunwind-x86_64 -rdynamic
LDFLAGS_SH	+= -shared

TARGET  = libpmtracefuncts.so libpmfuzz.so libfakepmfuzz.so
DEPENDS = rtinfo.o
SOURCES = $(shell echo *.c)
HEADERS = $(shell echo *.h)

all: $(TARGET)

$(DEPENDS): $(DEPENDS:.o=.c)
	$(CC) -c $(FLAGS) $(CFLAGS) $(DEBUGFLAGS) -o $@ $(@:.o=.c) $(LDFLAGS)

$(TARGET): $(TARGET:.so=.c) $(DEPENDS)
	$(CC) $(FLAGS) $(CFLAGS) $(CFLAG_SH) $(DEBUGFLAGS) -o $@ $(@:.so=.c) $(DEPENDS) $(LDFLAGS) $(LDFLAGS_SH)

docs:
	doxygen Doxyfile
	$(MAKE) -C docs/latex
	@echo
	@echo
	@echo "==="
	@echo "Documentation generated in docs/"
	@echo "==="
	@echo
	@echo

clean:
	rm -f *.so *.o
