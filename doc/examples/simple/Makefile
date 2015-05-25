BARECTF ?= barectf
RM = rm -rf

CFLAGS = -O2

TARGET = simple
OBJS = $(TARGET).o barectf.o

.PHONY: all view clean

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) -o $@ $^

barectf.h barectf.c: ctf/metadata
	barectf $<

barectf.o: barectf.c
	$(CC) $(CFLAGS) -Wno-strict-aliasing -Wno-unused-variable -c $<

$(TARGET).o: $(TARGET).c barectf.h
	$(CC) $(CFLAGS) -c $<

clean:
	$(RM) $(TARGET) $(OBJS) ctf/stream*
	$(RM) barectf.h barectf_bitfield.h barectf.c
