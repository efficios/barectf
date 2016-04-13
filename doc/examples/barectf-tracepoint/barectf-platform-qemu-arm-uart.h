#ifndef _BARECTF_PLATFORM_QEMU_ARM_UART
#define _BARECTF_PLATFORM_QEMU_ARM_UART

#include <barectf.h>

void barectf_platform_qemu_arm_uart_init(void);
void barectf_platform_qemu_arm_uart_fini(void);
struct barectf_default_ctx *barectf_platform_qemu_arm_uart_get_barectf_ctx(void);

#endif /* _BARECTF_PLATFORM_QEMU_ARM_UART */
