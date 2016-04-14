#!/usr/bin/env bats

# The MIT License (MIT)
#
# Copyright (c) 2016 Philippe Proulx <pproulx@efficios.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

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
