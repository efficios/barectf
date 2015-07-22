/*
 * barectf Parallella platform: consumer application
 *
 * Copyright (c) 2015 EfficiOS Inc. and Linux Foundation
 * Copyright (c) 2015 Philippe Proulx <pproulx@efficios.com>
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in
 * all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

#define _BSD_SOURCE
#include <unistd.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <assert.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <signal.h>
#include <time.h>
#include <errno.h>
#include <e-hal.h>

#include "barectf-platform-parallella-common.h"

#define mb()		__asm__ __volatile__("dmb" : : : "memory")

struct ctx {
	e_mem_t ringbufs_smem;
	int stream_fds[CORES_COUNT];
	const char *trace_dir;
	int verbose;
};

static volatile int quit = 0;

static void sig_handler(int signo)
{
	if (signo == SIGINT) {
		quit = 1;
		fprintf(stderr, "\nGot SIGINT: quitting\n");
	}
}

static int try_consume_core_packet(struct ctx *ctx, unsigned int row,
	unsigned int col)
{
	int stream_fd;
	size_t remaining;
	uint32_t producer_index;
	uint32_t consumer_index;
	uint32_t cons_packet_index;
	volatile uint8_t *packet_src;
	unsigned int index = rowcol2index(row, col);
	volatile struct ringbuf *ringbuf =
		get_ringbuf(ctx->ringbufs_smem.base, row, col);

#ifdef DEBUG
	if (ringbuf->error_buf[0]) {
		printf("[%u, %u] %s\n", row, col, ringbuf->error_buf);
	}
#endif /* DEBUG */

	consumer_index = ringbuf->consumer_index;
	producer_index = ringbuf->producer_index;

	if (producer_index <= consumer_index) {
		return 0;
	}

	/* order producer index reading before packet reading */
	mb();

	/* index of first full packet within ring buffer */
	cons_packet_index = consumer_index & (RINGBUF_SZ - 1);

	/* full packet data */
	packet_src = ringbuf->packets[cons_packet_index];

	/* append packet to stream file */
	remaining = PACKET_SZ;

	if (ctx->verbose) {
		printf("Consuming one packet from ring buffer of core (%u, %u):\n",
			row, col);
		printf("  Producer index:	 %u\n", producer_index);
		printf("  Consumer index:	 %u\n", consumer_index);
		printf("  Consumer packet index: %u\n", cons_packet_index);
	}

	stream_fd = ctx->stream_fds[index];

	for (;;) {
		ssize_t write_ret;

		write_ret = write(stream_fd,
			(uint8_t *) packet_src + (PACKET_SZ - remaining),
			remaining);
		assert(write_ret != 0);

		if (write_ret > 0) {
			remaining -= write_ret;
		} else if (write_ret == -1) {
			if (errno != EINTR) {
				/* other error */
				fprintf(stderr, "Error: failed to write packet of core (%u, %u):\n",
					row, col);
				perror("write");
				return -1;
			}
		}

		if (remaining == 0) {
			break;
		}
	}

	/* order packet reading before consumer index increment */
	mb();

	/* packet is consumed: update consumer index now */
	ringbuf->consumer_index = consumer_index + 1;

	return 0;
}

static int consume(struct ctx *ctx)
{
	int row, col, ret;

	if (ctx->verbose) {
		printf("Starting consumer\n");
	}

	for (;;) {
		if (quit) {
			return 0;
		}

		for (row = 0; row < CORES_ROWS; ++row) {
			for (col = 0; col < CORES_COLS; ++col) {
				if (quit) {
					return 0;
				}

				ret = try_consume_core_packet(ctx, row, col);

				if (ret) {
					return ret;
				}
			}
		}

		/* busy-wait before the next check */
		if (usleep(CONSUMER_POLL_DELAY) == -1) {
			if (errno != EINTR) {
				return -1;
			}
		}
	}
}

static void zero_ringbufs(struct ctx *ctx)
{
	memset(ctx->ringbufs_smem.base, 0, SMEM_SZ);
}

static void close_stream_fds(struct ctx *ctx)
{
	int i;

	for (i = 0; i < CORES_COUNT; ++i) {
		if (ctx->stream_fds[i] >= 0) {
			int fd = ctx->stream_fds[i];

			if (close(fd) == -1) {
				fprintf(stderr,
					"Warning: could not close FD %d:\n",
					fd);
				perror("close");
			}

			ctx->stream_fds[i] = -1;
		}
	}
}

static int open_stream_fd(struct ctx *ctx, unsigned int row, unsigned int col)
{
	char filename[128];
	unsigned int index = rowcol2index(row, col);

	sprintf(filename, "%s/stream-%u-%u", ctx->trace_dir,
		row, col);
	ctx->stream_fds[index] =
		open(filename, O_CREAT | O_WRONLY, 0644);

	if (ctx->stream_fds[index] == -1) {
		fprintf(stderr, "Error: could not open \"%s\" for writing\n",
			filename);
		close_stream_fds(ctx);
		return -1;
	}

	return 0;
}

static int open_stream_fds(struct ctx *ctx)
{
	unsigned int row, col;

	for (row = 0; row < CORES_ROWS; ++row) {
		for (col = 0; col < CORES_COLS; ++col) {
			int ret = open_stream_fd(ctx, row, col);

			if (ret) {
				return ret;
			}
		}
	}

	return 0;
}

static void init_stream_fds(struct ctx *ctx)
{
	unsigned int row, col;

	for (row = 0; row < CORES_ROWS; ++row) {
		for (col = 0; col < CORES_COLS; ++col) {
			ctx->stream_fds[rowcol2index(row, col)] = -1;
		}
	}
}

static int init(struct ctx *ctx)
{
	int ret = 0;

	e_set_host_verbosity(H_D0);

	if (ctx->verbose) {
		printf("Initializing HAL\n");
	}

	if (e_init(NULL) != E_OK) {
		fprintf(stderr, "Error: Epiphany HAL initialization failed\n");
		ret = -1;
		goto error;
	}

	if (ctx->verbose) {
		printf("HAL initialized\n");
		printf("Allocating %u bytes of shared memory in region \"%s\"\n",
			SMEM_SZ, SMEM_NAME);
	}

	ret = e_shm_alloc(&ctx->ringbufs_smem, SMEM_NAME, SMEM_SZ) != E_OK;

	if (ret != E_OK) {
		if (ctx->verbose) {
			printf("Allocation failed; attaching to shared memory region \"%s\"\n",
				SMEM_NAME);
		}

		ret = e_shm_attach(&ctx->ringbufs_smem, SMEM_NAME);
	}

	if (ret != E_OK) {
		fprintf(stderr, "Error: failed to attach to shared memory: %s\n",
			strerror(errno));
		ret = -1;
		goto error_finalize;
	}

	zero_ringbufs(ctx);

	if (ctx->verbose) {
		printf("Creating CTF stream files in \"%s\"\n", ctx->trace_dir);
	}

	init_stream_fds(ctx);

	if (open_stream_fds(ctx)) {
		fprintf(stderr, "Error: failed to create CTF stream files\n");
		ret = -1;
		goto error_finalize;
	}

	return 0;

error_finalize:
	if (ctx->ringbufs_smem.base) {
		e_shm_release(SMEM_NAME);
	}

	e_finalize();

error:
	return ret;
}

static void fini(struct ctx *ctx)
{
	if (ctx->verbose) {
		printf("Closing CTF stream files\n");
	}

	close_stream_fds(ctx);

	if (ctx->verbose) {
		printf("Releasing shared memory region \"%s\"\n", SMEM_NAME);
	}

	e_shm_release(SMEM_NAME);

	if (ctx->verbose) {
		printf("Finalizing HAL\n");
	}

	e_finalize();
}

static int parse_arguments(int argc, char *argv[], struct ctx *ctx)
{
	int i;

	if (argc > 3) {
		fprintf(stderr,
			"Error: the only accepted arguments are -v and a trace directory path\n");
		return -1;
	}

	for (i = 1; i < argc; ++i) {
		const char *arg = argv[i];

		if (strcmp(arg, "-v") == 0) {
			ctx->verbose = 1;
		} else {
			ctx->trace_dir = arg;
		}
	}

	if (!ctx->trace_dir) {
		ctx->trace_dir = "ctf";
	}

	return 0;
}

int main(int argc, char *argv[])
{
	int ret = 0;
	struct ctx ctx;

	if (signal(SIGINT, sig_handler) == SIG_ERR) {
		fprintf(stderr, "Error: failed to register SIGINT handler\n");
		ret = 1;
		goto end;
	}

	memset(&ctx, 0, sizeof(ctx));

	if (parse_arguments(argc, argv, &ctx)) {
		ret = 1;
		goto end;
	}

	if (init(&ctx)) {
		ret = 1;
		goto end;
	}

	if (consume(&ctx)) {
		ret = 1;
		goto end_fini;
	}

end_fini:
	fini(&ctx);

end:
	return ret;
}
