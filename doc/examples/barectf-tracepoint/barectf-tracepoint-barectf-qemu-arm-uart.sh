#!/usr/bin/env bash

qemu-system-arm -M versatilepb -m 128M -nographic -monitor none \
	-kernel barectf-tracepoint-barectf-qemu-arm-uart \
	-serial stdio -serial file:ctf-qemu-arm-uart/stream |
{
	while read line; do
		echo "$line"

		if [ x"$line" = x"tracing: done" ]; then
			pkill -nf file:ctf-qemu-arm-uart
		fi
	done
}
