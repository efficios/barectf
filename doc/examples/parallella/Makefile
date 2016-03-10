CROSS_COMPILE ?= e-

BARECTF ?= barectf
RM = rm -rf
MKDIR = mkdir
CC=$(CROSS_COMPILE)gcc
LD=$(CC)
OBJCOPY=$(CROSS_COMPILE)objcopy

ESDK=$(EPIPHANY_HOME)
ELDF=$(ESDK)/bsps/current/fast.ldf
PLATFORM_DIR = ../../../platforms/parallella
CFLAGS = -O2 -Wall -pedantic -std=c99 -I$(PLATFORM_DIR) -I.
LDFLAGS = -T $(ELDF) -le-lib

TARGET = parallella
OBJS = $(TARGET).o barectf.o barectf-platform-parallella.o

.PHONY: all view clean

all: $(TARGET).srec

ctf:
	$(MKDIR) ctf

$(TARGET): $(OBJS)
	$(LD) -o $@ $^ $(LDFLAGS)

$(TARGET).srec: $(TARGET)
	$(OBJCOPY) --srec-forceS3 --output-target srec $< $@

ctf/metadata barectf-bitfield.h barectf.h barectf.c: config.yaml ctf
	barectf $< -m ctf

barectf.o: barectf.c barectf.h barectf-bitfield.h
	$(CC) $(CFLAGS) -c $<

barectf-platform-parallella.o: $(PLATFORM_DIR)/barectf-platform-parallella.c
	$(CC) $(CFLAGS) -c $<

$(TARGET).o: $(TARGET).c barectf.h barectf-bitfield.h
	$(CC) $(CFLAGS) -c $<

clean:
	$(RM) $(TARGET) $(TARGET).srec $(OBJS) ctf
	$(RM) barectf.h barectf-bitfield.h barectf.c
