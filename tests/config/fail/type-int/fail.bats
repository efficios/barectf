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

@test 'unknown property in int type object makes barectf fail' {
  barectf_config_check_fail unknown-prop.yaml
}

@test 'no "size" property in int type object makes barectf fail' {
  barectf_config_check_fail size-no.yaml
}

@test 'wrong "size" property type in int type object makes barectf fail' {
  barectf_config_check_fail size-invalid-type.yaml
}

@test 'invalid "size" property (0) in int type object makes barectf fail' {
  barectf_config_check_fail size-0.yaml
}

@test 'invalid "size" property (65) in int type object makes barectf fail' {
  barectf_config_check_fail size-65.yaml
}

@test 'wrong "signed" property type in int type object makes barectf fail' {
  barectf_config_check_fail signed-invalid-type.yaml
}

@test 'wrong "align" property type in int type object makes barectf fail' {
  barectf_config_check_fail align-invalid-type.yaml
}

@test 'invalid "align" property (0) in int type object makes barectf fail' {
  barectf_config_check_fail align-0.yaml
}

@test 'invalid "align" property (3) in int type object makes barectf fail' {
  barectf_config_check_fail align-3.yaml
}

@test 'wrong "base" property type in int type object makes barectf fail' {
  barectf_config_check_fail base-invalid-type.yaml
}

@test 'invalid "base" property in int type object makes barectf fail' {
  barectf_config_check_fail base-invalid.yaml
}

@test 'wrong "byte-order" property type in int type object makes barectf fail' {
  barectf_config_check_fail bo-invalid-type.yaml
}

@test 'invalid "byte-order" property in int type object makes barectf fail' {
  barectf_config_check_fail bo-invalid.yaml
}

@test 'wrong "property-mappings" property type in int type object makes barectf fail' {
  barectf_config_check_fail pm-invalid-type.yaml
}

@test 'invalid "property-mappings" property in int type object makes barectf fail' {
  barectf_config_check_fail pm-unknown-clock.yaml
}

@test 'invalid "property-mappings" property (invalid "type" property) in int type object makes barectf fail' {
  barectf_config_check_fail pm-type-invalid.yaml
}

@test 'invalid "property-mappings" property (invalid "property" property) in int type object makes barectf fail' {
  barectf_config_check_fail pm-property-invalid.yaml
}
