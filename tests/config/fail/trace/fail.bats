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

@test 'unknown property in trace object makes barectf fail' {
  barectf_config_check_fail unknown-prop.yaml
}

@test 'wrong "byte-order" property type in trace object makes barectf fail' {
  barectf_config_check_fail bo-invalid-type.yaml
}

@test 'no "byte-order" property in trace object makes barectf fail' {
  barectf_config_check_fail bo-no.yaml
}

@test 'invalid "byte-order" property in trace object makes barectf fail' {
  barectf_config_check_fail bo-invalid.yaml
}

@test 'invalid "packet-header-type" property field type (not a structure) in trace object makes barectf fail' {
  barectf_config_check_fail ph-not-struct.yaml
}

@test 'wrong "uuid" property type in trace object makes barectf fail' {
  barectf_config_check_fail uuid-invalid-type.yaml
}

@test 'invalid "uuid" property (invalid UUID format) in trace object makes barectf fail' {
  barectf_config_check_fail uuid-invalid-uuid.yaml
}

@test 'invalid "magic" field type (not an integer) in packet header type makes barectf fail' {
  barectf_config_check_fail ph-magic-not-int.yaml
}

@test 'invalid "magic" field type (wrong integer size) in packet header type makes barectf fail' {
  barectf_config_check_fail ph-magic-wrong-size.yaml
}

@test 'invalid "magic" field type (signed) in packet header type makes barectf fail' {
  barectf_config_check_fail ph-magic-wrong-signed.yaml
}

@test 'invalid "stream_id" field type (not an integer) in packet header type makes barectf fail' {
  barectf_config_check_fail ph-streamid-not-int.yaml
}

@test 'invalid "stream_id" field type (signed) in packet header type makes barectf fail' {
  barectf_config_check_fail ph-streamid-wrong-signed.yaml
}

@test '"stream_id" field type size too small for the number of trace streams in packet header type makes barectf fail' {
  barectf_config_check_fail ph-streamid-too-small.yaml
}

@test 'invalid "uuid" field type (not an array) in packet header type makes barectf fail' {
  barectf_config_check_fail ph-uuid-not-array.yaml
}

@test 'invalid "uuid" field type (wrong array length) in packet header type makes barectf fail' {
  barectf_config_check_fail ph-uuid-wrong-length.yaml
}

@test 'invalid "uuid" field type (element type is not an integer) in packet header type makes barectf fail' {
  barectf_config_check_fail ph-uuid-et-not-int.yaml
}

@test 'invalid "uuid" field type (wrong element type size) in packet header type makes barectf fail' {
  barectf_config_check_fail ph-uuid-et-wrong-size.yaml
}

@test 'invalid "uuid" field type (element type is signed) in packet header type makes barectf fail' {
  barectf_config_check_fail ph-uuid-et-wrong-signed.yaml
}

@test 'invalid "uuid" field type (wrong element type alignment) in packet header type makes barectf fail' {
  barectf_config_check_fail ph-uuid-et-wrong-align.yaml
}
