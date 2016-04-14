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

@test 'unknown property in event object makes barectf fail' {
  barectf_assert_file_exists unknown-prop.yaml
  barectf_config_check_fail
}

@test 'wrong "log-level" property type in event object makes barectf fail' {
  barectf_assert_file_exists ll-invalid-type.yaml
  barectf_config_check_fail
}

@test 'non existing log level name as "log-level" property value in event object makes barectf fail' {
  barectf_assert_file_exists ll-non-existing.yaml
  barectf_config_check_fail
}

@test 'wrong "context-type" property type in event object makes barectf fail' {
  barectf_assert_file_exists ct-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "context-type" property field type (not a structure) in event object makes barectf fail' {
  barectf_assert_file_exists ct-not-struct.yaml
  barectf_config_check_fail
}

@test 'wrong "payload-type" property type in event object makes barectf fail' {
  barectf_assert_file_exists pt-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "payload-type" property field type (not a structure) in event object makes barectf fail' {
  barectf_assert_file_exists pt-not-struct.yaml
  barectf_config_check_fail
}

@test 'empty event object makes barectf fail' {
  barectf_assert_file_exists no-fields-at-all.yaml
  barectf_config_check_fail
}
