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

def test_bo_invalid_type(request, config_fail_test):
    config_fail_test(request, 'trace/bo-invalid-type')


def test_bo_invalid(request, config_fail_test):
    config_fail_test(request, 'trace/bo-invalid')


def test_bo_no(request, config_fail_test):
    config_fail_test(request, 'trace/bo-no')


def test_ph_magic_not_int(request, config_fail_test):
    config_fail_test(request, 'trace/ph-magic-not-int')


def test_ph_magic_wrong_signed(request, config_fail_test):
    config_fail_test(request, 'trace/ph-magic-wrong-signed')


def test_ph_magic_wrong_size(request, config_fail_test):
    config_fail_test(request, 'trace/ph-magic-wrong-size')


def test_ph_not_struct(request, config_fail_test):
    config_fail_test(request, 'trace/ph-not-struct')


def test_ph_streamid_not_int(request, config_fail_test):
    config_fail_test(request, 'trace/ph-streamid-not-int')


def test_ph_streamid_too_small(request, config_fail_test):
    config_fail_test(request, 'trace/ph-streamid-too-small')


def test_ph_streamid_wrong_signed(request, config_fail_test):
    config_fail_test(request, 'trace/ph-streamid-wrong-signed')


def test_ph_uuid_et_not_int(request, config_fail_test):
    config_fail_test(request, 'trace/ph-uuid-et-not-int')


def test_ph_uuid_et_wrong_align(request, config_fail_test):
    config_fail_test(request, 'trace/ph-uuid-et-wrong-align')


def test_ph_uuid_et_wrong_signed(request, config_fail_test):
    config_fail_test(request, 'trace/ph-uuid-et-wrong-signed')


def test_ph_uuid_et_wrong_size(request, config_fail_test):
    config_fail_test(request, 'trace/ph-uuid-et-wrong-size')


def test_ph_uuid_not_array(request, config_fail_test):
    config_fail_test(request, 'trace/ph-uuid-not-array')


def test_ph_uuid_wrong_length(request, config_fail_test):
    config_fail_test(request, 'trace/ph-uuid-wrong-length')


def test_unknown_prop(request, config_fail_test):
    config_fail_test(request, 'trace/unknown-prop')


def test_uuid_invalid_type(request, config_fail_test):
    config_fail_test(request, 'trace/uuid-invalid-type')


def test_uuid_invalid_uuid(request, config_fail_test):
    config_fail_test(request, 'trace/uuid-invalid-uuid')
