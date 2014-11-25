#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <time.h>

#include "barectf.h"

static uint64_t get_clock(void* data)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);

	return ts.tv_sec * 1000000000UL + ts.tv_nsec;
}

enum state_t {
	NEW,
	TERMINATED,
	READY,
	RUNNING,
	WAITING,
};

static void simple(uint8_t* buf, size_t sz)
{
	/* initialize barectf context */
	struct barectf_ctx ctx;
	struct barectf_ctx* pctx = &ctx;

	barectf_init(pctx, buf, sz, get_clock, NULL);

	/* open packet */
	barectf_open_packet(pctx);

	/* record events */
	barectf_trace_simple_uint32(pctx, 20150101);
	barectf_trace_simple_int16(pctx, -2999);
	barectf_trace_simple_float(pctx, 23.57);
	barectf_trace_simple_string(pctx, "Hello, World!");
	barectf_trace_simple_enum(pctx, RUNNING);
	barectf_trace_a_few_fields(pctx, -1, 301, -3.14159, "Hello again!", NEW);
	barectf_trace_bit_packed_integers(pctx, 1, -1, 3, -2, 2, 7, 23, -55, 232);

	/* close packet */
	barectf_close_packet(pctx);
}

static void write_packet(const char* filename, const uint8_t* buf, size_t sz)
{
	FILE* fh = fopen(filename, "wb");

	if (!fh) {
		return;
	}

	fwrite(buf, 1, sz, fh);
	fclose(fh);
}

int main(void)
{
	puts("simple barectf example!");

	const size_t buf_sz = 8192;

	uint8_t* buf = malloc(buf_sz);

	if (!buf) {
		return 1;
	}

	simple(buf, buf_sz);
	write_packet("ctf/stream_0", buf, buf_sz);
	free(buf);

	return 0;
}
