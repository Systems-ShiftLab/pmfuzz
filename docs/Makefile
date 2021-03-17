all: manpages

manpages:
	pandoc pmfuzz-fuzz.1.md -s -t man > manpages/pmfuzz-fuzz.1
	pandoc libpmfuzz.7.md -s -t man > manpages/libpmfuzz.7

clean:
	-rm programming_manual
	-rm programming_manual.pdf


.PHONY: manpages
