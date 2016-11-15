# The MIT License (MIT)
#
# Copyright (c) 2015 Philippe Proulx <pproulx@efficios.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

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
CFLAGS = -O2 -Wall -pedantic -I$(PLATFORM_DIR) -I.
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
	$(CC) $(CFLAGS) -ansi -c $<

barectf-platform-parallella.o: $(PLATFORM_DIR)/barectf-platform-parallella.c
	$(CC) $(CFLAGS) -c $<

$(TARGET).o: $(TARGET).c barectf.h barectf-bitfield.h
	$(CC) $(CFLAGS) -c $<

clean:
	$(RM) $(TARGET) $(TARGET).srec $(OBJS) ctf
	$(RM) barectf.h barectf-bitfield.h barectf.c
