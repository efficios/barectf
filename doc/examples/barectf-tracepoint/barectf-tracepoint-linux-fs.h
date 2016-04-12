#ifndef _BARECTF_TRACEPOINT_LINUX_FS
#define _BARECTF_TRACEPOINT_LINUX_FS

#include <barectf-platform-linux-fs.h>

/*
 * Include generated barectf header file: this contains the prefix and
 * default stream name to be used by the tracepoint() macro.
 */
#include "barectf.h"

/* define how the context is to be found by tracepoint() calls */
#define BARECTF_TRACEPOINT_CTX	(global_barectf_ctx)

/* then include this: */
#include <barectf-tracepoint.h>

/* global barectf context (default stream) */
static struct barectf_default_ctx *global_barectf_ctx;

/* global barectf platform context */
static struct barectf_platform_linux_fs_ctx *global_barectf_platform_ctx;

/* init function for this version */
static void init_tracing(void)
{
	/* initialize platform */
	global_barectf_platform_ctx =
		barectf_platform_linux_fs_init(512, "ctf-linux-fs", 1, 2, 7);

	if (!global_barectf_platform_ctx) {
		fprintf(stderr, "Error: could not initialize platform\n");
		exit(1);
	}

	global_barectf_ctx = barectf_platform_linux_fs_get_barectf_ctx(
		global_barectf_platform_ctx);
}

/* finalization function for this version */
static void fini_tracing(void)
{
	/* finalize platform */
	barectf_platform_linux_fs_fini(global_barectf_platform_ctx);
}

#endif /* _BARECTF_TRACEPOINT_LINUX_FS */
