#ifndef _BARECTF_PLATFORM_PARALLELLA_CONFIG_H
#define _BARECTF_PLATFORM_PARALLELLA_CONFIG_H

/* barectf Parallella platform parameters */

/* cores/row (4 for the Parallella) */
#define CORES_ROWS		4

/* cores/row (4 for the Parallella) */
#define CORES_COLS		4

/* packet size (must be a power of two) */
#ifndef PACKET_SZ
#define PACKET_SZ		256
#endif

/* ring buffer size (at least 2) */
#ifndef RINGBUF_SZ
#define RINGBUF_SZ		4
#endif

/* shared memory region name */
#ifndef SMEM_NAME
#define SMEM_NAME		"barectf-tracing"
#endif

/* backend check timeout (cycles) */
#ifndef BACKEND_CHECK_TIMEOUT
#define BACKEND_CHECK_TIMEOUT	(10000000ULL)
#endif

/* consumer poll delay (µs) */
#ifndef CONSUMER_POLL_DELAY
#define CONSUMER_POLL_DELAY	(5000)
#endif

#endif /* _BARECTF_PLATFORM_PARALLELLA_CONFIG_H */
