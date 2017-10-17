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

@test 'unknown property in metadata object makes barectf fail' {
  barectf_config_check_fail unknown-prop.yaml
}

@test 'wrong "env" property type in metadata object makes barectf fail' {
  barectf_config_check_fail env-invalid-type.yaml
}

@test 'invalid "env" key (invalid C identifier) in metadata object makes barectf fail' {
  barectf_config_check_fail env-key-invalid-identifier.yaml
}

@test 'invalid "env" value (not an int/string) in metadata object makes barectf fail' {
  barectf_config_check_fail env-value-invalid-type.yaml
}

@test 'wrong "clocks" property type in metadata object makes barectf fail' {
  barectf_config_check_fail clocks-invalid-type.yaml
}

@test 'invalid "clocks" key (invalid C identifier) in metadata object makes barectf fail' {
  barectf_config_check_fail clocks-key-invalid-identifier.yaml
}

@test 'wrong "$log-levels" property type in metadata object makes barectf fail' {
  barectf_config_check_fail ll-invalid-type.yaml
}

@test 'wrong "$log-levels" property value type in metadata object makes barectf fail' {
  barectf_config_check_fail ll-value-invalid-type.yaml
}

@test 'wrong "type-aliases" property type in metadata object makes barectf fail' {
  barectf_config_check_fail ta-invalid-type.yaml
}

@test 'no "trace" property in metadata object makes barectf fail' {
  barectf_config_check_fail trace-no.yaml
}

@test 'wrong "trace" property type in metadata object makes barectf fail' {
  barectf_config_check_fail trace-invalid-type.yaml
}

@test 'empty "trace" property in metadata object makes barectf fail' {
  barectf_config_check_fail trace-empty.yaml
}

@test 'no "streams" property in metadata object makes barectf fail' {
  barectf_config_check_fail streams-no.yaml
}

@test 'wrong "streams" property type in metadata object makes barectf fail' {
  barectf_config_check_fail streams-invalid-type.yaml
}

@test 'empty "streams" property in metadata object makes barectf fail' {
  barectf_config_check_fail streams-empty.yaml
}

@test 'invalid "streams" key (invalid C identifier) in metadata object makes barectf fail' {
  barectf_config_check_fail streams-key-invalid-identifier.yaml
}

@test 'multiple streams in metadata object with missing "stream_id" packet header type field makes barectf fail' {
  barectf_config_check_fail multiple-streams-trace-ph-no-stream-id.yaml
}

@test 'wrong "$default-stream" property type in metadata object makes barectf fail' {
  barectf_config_check_fail default-stream-invalid-type.yaml
}

@test 'non-existing stream name in "$default-stream" property makes barectf fail' {
  barectf_config_check_fail default-stream-unknown-stream.yaml
}

@test 'coexisting "$default-stream" property (metadata) and "$default: true" property (stream) with different names make barectf fail' {
  barectf_config_check_fail default-stream-stream-default-duplicate.yaml
}
