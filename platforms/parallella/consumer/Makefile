RM = rm -f
CC = $(CROSS_COMPILE)gcc
LD = $(CC)

ESDK=$(EPIPHANY_HOME)

CFLAGS = -O2 -std=c99 -I.. -I"$(ESDK)/tools/host/include"
LDFLAGS = -L"$(ESDK)/tools/host/lib" -le-hal

TARGET = consumer
OBJS = $(TARGET).o

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(OBJS)
	$(LD) -o $@ $^ $(LDFLAGS)

$(TARGET).o: $(TARGET).c
	$(CC) $(CFLAGS) -c $<

clean:
	$(RM) $(TARGET) $(OBJS)
