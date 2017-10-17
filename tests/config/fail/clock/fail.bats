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

@test 'unknown property in clock object makes barectf fail' {
  barectf_config_check_fail unknown-prop.yaml
}

@test 'wrong "freq" property type in clock object makes barectf fail' {
  barectf_config_check_fail freq-invalid-type.yaml
}

@test 'invalid "freq" property (0) in clock object makes barectf fail' {
  barectf_config_check_fail freq-0.yaml
}

@test 'invalid "freq" property (negative) in clock object makes barectf fail' {
  barectf_config_check_fail freq-neg.yaml
}

@test 'wrong "description" property type in clock object makes barectf fail' {
  barectf_config_check_fail description-invalid-type.yaml
}

@test 'wrong "uuid" property type in clock object makes barectf fail' {
  barectf_config_check_fail uuid-invalid-type.yaml
}

@test 'invalid "uuid" property in clock object makes barectf fail' {
  barectf_config_check_fail uuid-invalid.yaml
}

@test 'wrong "error-cycles" property type in clock object makes barectf fail' {
  barectf_config_check_fail ec-invalid-type.yaml
}

@test 'invalid "error-cycles" property in clock object makes barectf fail' {
  barectf_config_check_fail ec-invalid.yaml
}

@test 'wrong "offset" property type in clock object makes barectf fail' {
  barectf_config_check_fail offset-invalid-type.yaml
}

@test 'wrong "absolute" property type in clock object makes barectf fail' {
  barectf_config_check_fail absolute-invalid-type.yaml
}

@test 'unknown property in clock offset object makes barectf fail' {
  barectf_config_check_fail offset-unknown-prop.yaml
}

@test 'wrong "seconds" property type in clock offset object makes barectf fail' {
  barectf_config_check_fail offset-seconds-invalid-type.yaml
}

@test 'invalid "seconds" property in clock offset object makes barectf fail' {
  barectf_config_check_fail offset-seconds-neg.yaml
}

@test 'wrong "cycles" property type in clock offset object makes barectf fail' {
  barectf_config_check_fail offset-cycles-invalid-type.yaml
}

@test 'invalid "cycles" property in clock offset object makes barectf fail' {
  barectf_config_check_fail offset-cycles-neg.yaml
}

@test 'wrong "$return-ctype" property type in clock object makes barectf fail' {
  barectf_config_check_fail rct-invalid-type.yaml
}
