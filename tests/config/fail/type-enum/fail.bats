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

@test 'unknown property in enum type object makes barectf fail' {
  barectf_config_check_fail unknown-prop.yaml
}

@test 'no "value-type" property in enum type object makes barectf fail' {
  barectf_config_check_fail vt-no.yaml
}

@test 'wrong "value-type" property type in enum type object makes barectf fail' {
  barectf_config_check_fail vt-invalid-type.yaml
}

@test 'no "members" property in enum type object makes barectf fail' {
  barectf_config_check_fail members-no.yaml
}

@test 'wrong "members" property type in enum type object makes barectf fail' {
  barectf_config_check_fail members-invalid-type.yaml
}

@test 'empty "members" property in enum type object makes barectf fail' {
  barectf_config_check_fail members-empty.yaml
}

@test 'wrong "members" property element type in enum type object makes barectf fail' {
  barectf_config_check_fail members-el-invalid-type.yaml
}

@test 'unknown property in enum type member object makes barectf fail' {
  barectf_config_check_fail members-el-member-unknown-prop.yaml
}

@test 'wrong "label" property type in enum type member object makes barectf fail' {
  barectf_config_check_fail members-el-member-label-invalid-type.yaml
}

@test 'wrong "value" property type in enum type member object makes barectf fail' {
  barectf_config_check_fail members-el-member-value-invalid-type.yaml
}

@test '"value" property outside the unsigned value type range in enum type member object makes barectf fail' {
  barectf_config_check_fail members-el-member-value-outside-range-unsigned.yaml
}

@test '"value" property outside the signed value type range in enum type member object makes barectf fail' {
  barectf_config_check_fail members-el-member-value-outside-range-signed.yaml
}

@test 'overlapping members in enum type object makes barectf fail' {
  barectf_config_check_fail members-overlap.yaml
}
