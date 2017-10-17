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

load ../../common

@test 'unknown property in stream object makes barectf fail' {
  barectf_config_check_fail unknown-prop.yaml
}

@test 'no "packet-context-type" property in stream object makes barectf fail' {
  barectf_config_check_fail pct-no.yaml
}

@test 'wrong "packet-context-type" property type in stream object makes barectf fail' {
  barectf_config_check_fail pct-invalid-type.yaml
}

@test 'invalid "packet-context-type" property field type (not a structure) in stream object makes barectf fail' {
  barectf_config_check_fail pct-not-struct.yaml
}

@test 'invalid "timestamp_begin" field type (not an integer) in packet context type makes barectf fail' {
  barectf_config_check_fail pct-tb-not-int.yaml
}

@test 'invalid "timestamp_begin" field type (signed) in packet context type makes barectf fail' {
  barectf_config_check_fail pct-tb-wrong-signed.yaml
}

@test 'invalid "timestamp_begin" field type (not mapped to a clock) in packet context type makes barectf fail' {
  barectf_config_check_fail pct-tb-wrong-pm.yaml
}

@test 'no "timestamp_begin" field with an existing "timestamp_end" field in packet context type makes barectf fail' {
  barectf_config_check_fail pct-te-yes-tb-no.yaml
}

@test 'invalid "timestamp_end" field type (not an integer) in packet context type makes barectf fail' {
  barectf_config_check_fail pct-te-not-int.yaml
}

@test 'invalid "timestamp_end" field type (signed) in packet context type makes barectf fail' {
  barectf_config_check_fail pct-te-wrong-signed.yaml
}

@test 'invalid "timestamp_end" field type (not mapped to a clock) in packet context type makes barectf fail' {
  barectf_config_check_fail pct-te-wrong-pm.yaml
}

@test 'no "timestamp_end" field with an existing "timestamp_begin" field in packet context type makes barectf fail' {
  barectf_config_check_fail pct-tb-yes-te-no.yaml
}

@test '"timestamp_begin" field and "timestamp_end" field are not mapped to the same clock in packet context type makes barectf fail' {
  barectf_config_check_fail pct-tb-te-different-clocks.yaml
}

@test 'invalid "packet_size" field type (not an integer) in packet context type makes barectf fail' {
  barectf_config_check_fail pct-ps-not-int.yaml
}

@test 'invalid "packet_size" field type (signed) in packet context type makes barectf fail' {
  barectf_config_check_fail pct-ps-wrong-signed.yaml
}

@test 'no "packet_size" field with an existing "content_size" field in packet context type makes barectf fail' {
  barectf_config_check_fail pct-cs-yes-ps-no.yaml
}

@test 'invalid "content_size" field type (not an integer) in packet context type makes barectf fail' {
  barectf_config_check_fail pct-cs-not-int.yaml
}

@test 'invalid "content_size" field type (signed) in packet context type makes barectf fail' {
  barectf_config_check_fail pct-cs-wrong-signed.yaml
}

@test 'no "content_size" field with an existing "packet_size" field in packet context type makes barectf fail' {
  barectf_config_check_fail pct-ps-yes-cs-no.yaml
}

@test '"content_size" field size greater than "packet_size" field size in packet context type makes barectf fail' {
  barectf_config_check_fail pct-cs-gt-ps.yaml
}

@test 'invalid "events_discarded" field type (not an integer) in packet context type makes barectf fail' {
  barectf_config_check_fail pct-ed-not-int.yaml
}

@test 'invalid "events_discarded" field type (signed) in packet context type makes barectf fail' {
  barectf_config_check_fail pct-ed-wrong-signed.yaml
}

@test 'wrong "event-header-type" property type in stream object makes barectf fail' {
  barectf_config_check_fail eht-invalid-type.yaml
}

@test 'invalid "event-header-type" property field type (not a structure) in stream object makes barectf fail' {
  barectf_config_check_fail eht-not-struct.yaml
}

@test 'invalid "timestamp" field type (not an integer) in event header type makes barectf fail' {
  barectf_config_check_fail eht-timestamp-not-int.yaml
}

@test 'invalid "timestamp" field type (signed) in event header type makes barectf fail' {
  barectf_config_check_fail eht-timestamp-wrong-signed.yaml
}

@test 'invalid "timestamp" field type (not mapped to a clock) in event header type makes barectf fail' {
  barectf_config_check_fail eht-timestamp-wrong-pm.yaml
}

@test 'invalid "id" field type (not an integer) in event header type makes barectf fail' {
  barectf_config_check_fail eht-id-not-int.yaml
}

@test 'invalid "id" field type (signed) in event header type makes barectf fail' {
  barectf_config_check_fail eht-id-wrong-signed.yaml
}

@test 'no event header type with multiple events in stream object makes barectf fail' {
  barectf_config_check_fail eht-id-no-multiple-events.yaml
}

@test '"id" field type size too small for the number of stream events in event header type makes barectf fail' {
  barectf_config_check_fail eht-id-too-small.yaml
}

@test 'wrong "event-context-type" property type in stream object makes barectf fail' {
  barectf_config_check_fail ect-invalid-type.yaml
}

@test 'invalid "event-context-type" property field type (not a structure) in stream object makes barectf fail' {
  barectf_config_check_fail ect-not-struct.yaml
}

@test 'no "events" property in stream object makes barectf fail' {
  barectf_config_check_fail events-no.yaml
}

@test 'wrong "events" property type in stream object makes barectf fail' {
  barectf_config_check_fail events-invalid-type.yaml
}

@test 'empty "events" property in stream object makes barectf fail' {
  barectf_config_check_fail events-empty.yaml
}

@test 'invalid "events" key (invalid C identifier) in metadata object makes barectf fail' {
  barectf_config_check_fail events-key-invalid-identifier.yaml
}

@test 'wrong "$default" property type in stream object makes barectf fail' {
  barectf_config_check_fail default-invalid-type.yaml
}
