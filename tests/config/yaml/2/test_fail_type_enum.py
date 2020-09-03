# The MIT License (MIT)
#
# Copyright (c) 2020 Philippe Proulx <pproulx@efficios.com>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

def test_members_el_invalid_type(request, config_fail_test):
    config_fail_test(request, 'type-enum/members-el-invalid-type')


def test_members_el_member_label_invalid_type(request, config_fail_test):
    config_fail_test(request, 'type-enum/members-el-member-label-invalid-type')


def test_members_el_member_unknown_prop(request, config_fail_test):
    config_fail_test(request, 'type-enum/members-el-member-unknown-prop')


def test_members_el_member_value_invalid_type(request, config_fail_test):
    config_fail_test(request, 'type-enum/members-el-member-value-invalid-type')


def test_members_el_member_value_outside_range_signed(request, config_fail_test):
    config_fail_test(request, 'type-enum/members-el-member-value-outside-range-signed')


def test_members_el_member_value_outside_range_unsigned(request, config_fail_test):
    config_fail_test(request, 'type-enum/members-el-member-value-outside-range-unsigned')


def test_members_empty(request, config_fail_test):
    config_fail_test(request, 'type-enum/members-empty')


def test_members_invalid_type(request, config_fail_test):
    config_fail_test(request, 'type-enum/members-invalid-type')


def test_members_no(request, config_fail_test):
    config_fail_test(request, 'type-enum/members-no')


def test_members_overlap(request, config_fail_test):
    config_fail_test(request, 'type-enum/members-overlap')


def test_unknown_prop(request, config_fail_test):
    config_fail_test(request, 'type-enum/unknown-prop')


def test_vt_invalid_type(request, config_fail_test):
    config_fail_test(request, 'type-enum/vt-invalid-type')


def test_vt_no(request, config_fail_test):
    config_fail_test(request, 'type-enum/vt-no')
