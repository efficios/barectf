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

@test 'unknown property in clock object makes barectf fail' {
  barectf_assert_file_exists unknown-prop.yaml
  barectf_config_check_fail
}

@test 'wrong "freq" property type in clock object makes barectf fail' {
  barectf_assert_file_exists freq-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "freq" property (0) in clock object makes barectf fail' {
  barectf_assert_file_exists freq-0.yaml
  barectf_config_check_fail
}

@test 'invalid "freq" property (negative) in clock object makes barectf fail' {
  barectf_assert_file_exists freq-neg.yaml
  barectf_config_check_fail
}

@test 'wrong "description" property type in clock object makes barectf fail' {
  barectf_assert_file_exists description-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "uuid" property type in clock object makes barectf fail' {
  barectf_assert_file_exists uuid-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "uuid" property in clock object makes barectf fail' {
  barectf_assert_file_exists uuid-invalid.yaml
  barectf_config_check_fail
}

@test 'wrong "error-cycles" property type in clock object makes barectf fail' {
  barectf_assert_file_exists ec-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "error-cycles" property in clock object makes barectf fail' {
  barectf_assert_file_exists ec-invalid.yaml
  barectf_config_check_fail
}

@test 'wrong "offset" property type in clock object makes barectf fail' {
  barectf_assert_file_exists offset-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "absolute" property type in clock object makes barectf fail' {
  barectf_assert_file_exists absolute-invalid-type.yaml
  barectf_config_check_fail
}

@test 'unknown property in clock offset object makes barectf fail' {
  barectf_assert_file_exists offset-unknown-prop.yaml
  barectf_config_check_fail
}

@test 'wrong "seconds" property type in clock offset object makes barectf fail' {
  barectf_assert_file_exists offset-seconds-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "seconds" property in clock offset object makes barectf fail' {
  barectf_assert_file_exists offset-seconds-neg.yaml
  barectf_config_check_fail
}

@test 'wrong "cycles" property type in clock offset object makes barectf fail' {
  barectf_assert_file_exists offset-cycles-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "cycles" property in clock offset object makes barectf fail' {
  barectf_assert_file_exists offset-cycles-neg.yaml
  barectf_config_check_fail
}

@test 'wrong "$return-ctype" property type in clock object makes barectf fail' {
  barectf_assert_file_exists rct-invalid-type.yaml
  barectf_config_check_fail
}
