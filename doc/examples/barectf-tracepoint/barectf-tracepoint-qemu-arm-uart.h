#ifndef _BARECTF_TRACEPOINT_QEMU_ARM_UART
#define _BARECTF_TRACEPOINT_QEMU_ARM_UART

#include <barectf-platform-qemu-arm-uart.h>

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

/* init function for this version */
static void init_tracing(void)
{
	/* initialize platform */
	barectf_platform_qemu_arm_uart_init();
	global_barectf_ctx = barectf_platform_qemu_arm_uart_get_barectf_ctx();
}

/* finalization function for this version */
static void fini_tracing(void)
{
	/* finalize platform */
	barectf_platform_qemu_arm_uart_fini();
}

#endif /* _BARECTF_TRACEPOINT_QEMU_ARM_UART */
