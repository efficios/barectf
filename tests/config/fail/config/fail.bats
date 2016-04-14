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

@test 'unknown property in config object makes barectf fail' {
  barectf_assert_file_exists unknown-prop.yaml
  barectf_config_check_fail
}

@test 'no "version" property in config object makes barectf fail' {
  barectf_assert_file_exists version-no.yaml
  barectf_config_check_fail
}

@test 'wrong "version" property type in config object makes barectf fail' {
  barectf_assert_file_exists version-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "version" property (1.9) in config object makes barectf fail' {
  barectf_assert_file_exists version-invalid-19.yaml
  barectf_config_check_fail
}

@test 'invalid "version" property (2.3) in config object makes barectf fail' {
  barectf_assert_file_exists version-invalid-23.yaml
  barectf_config_check_fail
}

@test 'wrong "prefix" property type in config object makes barectf fail' {
  barectf_assert_file_exists prefix-invalid-type.yaml
  barectf_config_check_fail
}

@test 'no valid C identifier in "prefix" property type in config object makes barectf fail' {
  barectf_assert_file_exists prefix-invalid-identifier.yaml
  barectf_config_check_fail
}

@test 'no "metadata" property in config object makes barectf fail' {
  barectf_assert_file_exists metadata-no.yaml
  barectf_config_check_fail
}

@test 'wrong "metadata" property type in config object makes barectf fail' {
  barectf_assert_file_exists metadata-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "options" property type in config object makes barectf fail' {
  barectf_assert_file_exists options-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "gen-prefix-def" property type in config options object makes barectf fail' {
  barectf_assert_file_exists options-gen-prefix-def-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "gen-default-stream-def" property type in config options object makes barectf fail' {
  barectf_assert_file_exists options-gen-default-stream-def-invalid-type.yaml
  barectf_config_check_fail
}
