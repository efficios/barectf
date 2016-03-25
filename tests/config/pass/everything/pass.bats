#!/usr/bin/env bats

load ../../../common
load ../../common

@test 'config file using all features makes barectf pass' {
  barectf_assert_file_exists config.yaml
  [ $status -eq 0 ]
  [ -f metadata ]
  [ -f bctf.c ]
  [ -f bctf.h ]
  [ -f bctf-bitfield.h ]

  # test should be more extensive than that, but it's a start
  $CC -c bctf.c
  nm bctf.o | grep bctf_init
  nm bctf.o | grep bctf_my_other_stream_close_packet
  nm bctf.o | grep bctf_my_other_stream_open_packet
  nm bctf.o | grep bctf_my_other_stream_trace_context_no_payload
  nm bctf.o | grep bctf_my_other_stream_trace_evev
  nm bctf.o | grep bctf_my_other_stream_trace_my_event
  nm bctf.o | grep bctf_my_other_stream_trace_no_context_no_payload
  nm bctf.o | grep bctf_my_other_stream_trace_oh_henry_event
  nm bctf.o | grep bctf_my_other_stream_trace_this_event
  nm bctf.o | grep bctf_my_stream_close_packet
  nm bctf.o | grep bctf_my_stream_open_packet
  nm bctf.o | grep bctf_my_stream_trace_my_event
  nm bctf.o | grep bctf_packet_buf
  nm bctf.o | grep bctf_packet_buf_size
  nm bctf.o | grep bctf_packet_events_discarded
  nm bctf.o | grep bctf_packet_is_empty
  nm bctf.o | grep bctf_packet_is_full
  nm bctf.o | grep bctf_packet_is_open
  nm bctf.o | grep bctf_packet_set_buf
  nm bctf.o | grep bctf_packet_size
}
