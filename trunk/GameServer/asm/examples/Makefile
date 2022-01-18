all: keyboard.bin shell.bin

keyboard.bin: keyboard.o
	ld65 -C ../../src/he-rom.cfg -m keyboard.map -o keyboard.bin keyboard.o

shell.bin: shell.o helib.o
	ld65 -C ../../src/he-rom.cfg -m shell.map -o shell.bin shell.o helib.o

keyboard.o: keyboard.s
	ca65 -l keyboard.lst keyboard.s

shell.o: shell.s
	ca65 -l shell.lst shell.s

helib.o: helib.s
	ca65 -l helib.lst helib.s

clean:
	rm -rf keyboard.bin keyboard.o keyboard.lst keyboard.map shell.bin shell.o helib.o

