SOURCES = crt0.s cputc.s puts.s write.s read.s clrscr.s cputcxy.s gotoxy.s cputs.s colour.s dio.s systime.s open.s fileio.s kernel.s netio.s cgetc.s heapi.s

LIBRARY = he.lib

all: $(LIBRARY)

$(LIBRARY): $(SOURCES:.s=.o)
	ar65 a $(LIBRARY) $^

%.o: %.s
	ca65 $<

clean:
	rm -rf $(SOURCES:.s=.o)
