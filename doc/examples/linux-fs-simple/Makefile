BARECTF ?= barectf
RM = rm -rf
MKDIR = mkdir

PLATFORM_DIR = ../../../platforms/linux-fs
CFLAGS = -O2 -Wall -pedantic -std=gnu99 -I$(PLATFORM_DIR) -I.

TARGET = linux-fs-simple
OBJS = $(TARGET).o barectf.o barectf-platform-linux-fs.o

.PHONY: all view

all: $(TARGET)

ctf:
	$(MKDIR) ctf

$(TARGET): $(OBJS)
	$(CC) -o $@ $^

ctf/metadata barectf-bitfield.h barectf.h barectf.c: config.yaml ctf
	$(BARECTF) $< -m ctf

barectf.o: barectf.c
	$(CC) $(CFLAGS) -c $<

barectf-platform-linux-fs.o: $(PLATFORM_DIR)/barectf-platform-linux-fs.c
	$(CC) $(CFLAGS) -c $<

$(TARGET).o: $(TARGET).c barectf.h barectf-bitfield.h
	$(CC) $(CFLAGS) -c $<

clean:
	$(RM) $(TARGET) $(OBJS) ctf
	$(RM) barectf.h barectf-bitfield.h barectf.c
