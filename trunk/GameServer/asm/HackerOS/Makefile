%.bin: %.o he-bin.o
	ld65 -C cfg/he-bin.cfg -m he-bin.map -o $@ $^
	cp $@ /tmp/debugfs

BOOT.SYS: boot.o
	ld65 -C cfg/he-boot.cfg -m boot.map -o BOOT.SYS boot.o
	cp BOOT.SYS /tmp/debugfs

KERNEL.SYS: kernel.o filedrv.o netdrv.o shell.o
	ld65 -C cfg/he-kernel.cfg -m kernel.map -o KERNEL.SYS $^
	cp KERNEL.SYS /tmp/debugfs
	cp FILEIO.SYS /tmp/debugfs
	cp NETDRV.SYS /tmp/debugfs
	cp SHELL.SYS /tmp/debugfs

bootrom: bootrom.o
	ld65 -C cfg/he-rom.cfg -m bootrom.map -o bootrom.bin bootrom.o
	python tohex.py 200 bootrom.bin

%.s: %.c
	cc65 $<

%.o: %.s
	ca65 -l code.lst $<
	#cp $< /home/kveroneau/Projects/hedevkit/HackerOS/

%.bin: %.c
	cc65 $<
	ca65 $(basename $<).s
	ld65 -C cfg/he-bin.cfg -m $(basename $^).map -o $@ $(basename $^).o clib/he.lib
	cp $@ /tmp/debugfs
	rm $(basename $<).s $(basename $<).o

clean:
	rm -rf *.SYS output.hex *.bin
	rm -rf *.o 
	rm -rf *.map *.lst

docs:
	cp readme.txt /tmp/debugfs
	cp docs/* /tmp/debugfs

os: BOOT.SYS KERNEL.SYS halt.bin reboot.bin ls.bin mkfs.bin rm.bin clear.bin 

tools: echo.bin cat.bin hemon.bin basic.bin ipconfig.bin help.bin

examples: showcase.bin
