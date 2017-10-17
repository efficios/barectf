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

@test 'unknown property in float type object makes barectf fail' {
  barectf_config_check_fail unknown-prop.yaml
}

@test 'no "size" property in float type object makes barectf fail' {
  barectf_config_check_fail size-no.yaml
}

@test 'wrong "size" property type in float type object makes barectf fail' {
  barectf_config_check_fail size-invalid-type.yaml
}

@test 'unknown property in float type object "size" property makes barectf fail' {
  barectf_config_check_fail size-unknown-prop.yaml
}

@test 'no "exp" property in float type object "size" property makes barectf fail' {
  barectf_config_check_fail size-exp-no.yaml
}

@test 'no "mant" property in float type object "size" property makes barectf fail' {
  barectf_config_check_fail size-mant-no.yaml
}

@test 'sum of "mant" and "exp" properties of float type size object not a multiple of 32 property makes barectf fail' {
  barectf_config_check_fail size-exp-mant-wrong-sum.yaml
}

@test 'wrong "align" property type in float type object makes barectf fail' {
  barectf_config_check_fail align-invalid-type.yaml
}

@test 'invalid "align" property (0) in float type object makes barectf fail' {
  barectf_config_check_fail align-0.yaml
}

@test 'invalid "align" property (3) in float type object makes barectf fail' {
  barectf_config_check_fail align-3.yaml
}

@test 'wrong "byte-order" property type in float type object makes barectf fail' {
  barectf_config_check_fail bo-invalid-type.yaml
}

@test 'invalid "byte-order" property in float type object makes barectf fail' {
  barectf_config_check_fail bo-invalid.yaml
}
