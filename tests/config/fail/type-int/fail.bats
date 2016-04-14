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

@test 'unknown property in int type object makes barectf fail' {
  barectf_assert_file_exists unknown-prop.yaml
  barectf_config_check_fail
}

@test 'no "size" property in int type object makes barectf fail' {
  barectf_assert_file_exists size-no.yaml
  barectf_config_check_fail
}

@test 'wrong "size" property type in int type object makes barectf fail' {
  barectf_assert_file_exists size-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "size" property (0) in int type object makes barectf fail' {
  barectf_assert_file_exists size-0.yaml
  barectf_config_check_fail
}

@test 'invalid "size" property (65) in int type object makes barectf fail' {
  barectf_assert_file_exists size-65.yaml
  barectf_config_check_fail
}

@test 'wrong "signed" property type in int type object makes barectf fail' {
  barectf_assert_file_exists signed-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "align" property type in int type object makes barectf fail' {
  barectf_assert_file_exists align-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "align" property (0) in int type object makes barectf fail' {
  barectf_assert_file_exists align-0.yaml
  barectf_config_check_fail
}

@test 'invalid "align" property (3) in int type object makes barectf fail' {
  barectf_assert_file_exists align-3.yaml
  barectf_config_check_fail
}

@test 'wrong "base" property type in int type object makes barectf fail' {
  barectf_assert_file_exists base-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "base" property in int type object makes barectf fail' {
  barectf_assert_file_exists base-invalid.yaml
  barectf_config_check_fail
}

@test 'wrong "byte-order" property type in int type object makes barectf fail' {
  barectf_assert_file_exists bo-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "byte-order" property in int type object makes barectf fail' {
  barectf_assert_file_exists bo-invalid.yaml
  barectf_config_check_fail
}

@test 'wrong "property-mappings" property type in int type object makes barectf fail' {
  barectf_assert_file_exists pm-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "property-mappings" property in int type object makes barectf fail' {
  barectf_assert_file_exists pm-unknown-clock.yaml
  barectf_config_check_fail
}

@test 'invalid "property-mappings" property (invalid "type" property) in int type object makes barectf fail' {
  barectf_assert_file_exists pm-type-invalid.yaml
  barectf_config_check_fail
}

@test 'invalid "property-mappings" property (invalid "property" property) in int type object makes barectf fail' {
  barectf_assert_file_exists pm-property-invalid.yaml
  barectf_config_check_fail
}
