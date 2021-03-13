DEPENDS :=
CXXFLAGS :=
LIBS :=-lfakepmfuzz

%.o: %.cc $(DEPENDS)
	$(CXX) $(INCLUDE) -c $(CXXFLAGS) $< -o $@

example: example.o
	$(CXX) -o $@ $< $(LIBS)

clean:
	rm -f example *.o
