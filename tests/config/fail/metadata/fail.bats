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

@test 'unknown property in metadata object makes barectf fail' {
  barectf_assert_file_exists unknown-prop.yaml
  barectf_config_check_fail
}

@test 'wrong "env" property type in metadata object makes barectf fail' {
  barectf_assert_file_exists env-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "env" key (invalid C identifier) in metadata object makes barectf fail' {
  barectf_assert_file_exists env-key-invalid-identifier.yaml
  barectf_config_check_fail
}

@test 'invalid "env" value (not an int/string) in metadata object makes barectf fail' {
  barectf_assert_file_exists env-value-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "clocks" property type in metadata object makes barectf fail' {
  barectf_assert_file_exists clocks-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "clocks" key (invalid C identifier) in metadata object makes barectf fail' {
  barectf_assert_file_exists clocks-key-invalid-identifier.yaml
  barectf_config_check_fail
}

@test 'wrong "$log-levels" property type in metadata object makes barectf fail' {
  barectf_assert_file_exists ll-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "$log-levels" property value type in metadata object makes barectf fail' {
  barectf_assert_file_exists ll-value-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "type-aliases" property type in metadata object makes barectf fail' {
  barectf_assert_file_exists ta-invalid-type.yaml
  barectf_config_check_fail
}

@test 'no "trace" property in metadata object makes barectf fail' {
  barectf_assert_file_exists trace-no.yaml
  barectf_config_check_fail
}

@test 'wrong "trace" property type in metadata object makes barectf fail' {
  barectf_assert_file_exists trace-invalid-type.yaml
  barectf_config_check_fail
}

@test 'empty "trace" property in metadata object makes barectf fail' {
  barectf_assert_file_exists trace-empty.yaml
  barectf_config_check_fail
}

@test 'no "streams" property in metadata object makes barectf fail' {
  barectf_assert_file_exists streams-no.yaml
  barectf_config_check_fail
}

@test 'wrong "streams" property type in metadata object makes barectf fail' {
  barectf_assert_file_exists streams-invalid-type.yaml
  barectf_config_check_fail
}

@test 'empty "streams" property in metadata object makes barectf fail' {
  barectf_assert_file_exists streams-empty.yaml
  barectf_config_check_fail
}

@test 'invalid "streams" key (invalid C identifier) in metadata object makes barectf fail' {
  barectf_assert_file_exists streams-key-invalid-identifier.yaml
  barectf_config_check_fail
}

@test 'multiple streams in metadata object with missing "stream_id" packet header type field makes barectf fail' {
  barectf_assert_file_exists multiple-streams-trace-ph-no-stream-id.yaml
  barectf_config_check_fail
}

@test 'wrong "$default-stream" property type in metadata object makes barectf fail' {
  barectf_assert_file_exists default-stream-invalid-type.yaml
  barectf_config_check_fail
}

@test 'non-existing stream name in "$default-stream" property makes barectf fail' {
  barectf_assert_file_exists default-stream-unknown-stream.yaml
  barectf_config_check_fail
}

@test 'coexisting "$default-stream" property (metadata) and "$default: true" property (stream) with different names make barectf fail' {
  barectf_assert_file_exists default-stream-stream-default-duplicate.yaml
  barectf_config_check_fail
}
