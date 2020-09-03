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

def test_default_invalid_type(request, config_fail_test):
    config_fail_test(request, 'stream/default-invalid-type')


def test_ect_invalid_type(request, config_fail_test):
    config_fail_test(request, 'stream/ect-invalid-type')


def test_ect_not_struct(request, config_fail_test):
    config_fail_test(request, 'stream/ect-not-struct')


def test_eht_id_no_multiple_events(request, config_fail_test):
    config_fail_test(request, 'stream/eht-id-no-multiple-events')


def test_eht_id_not_int(request, config_fail_test):
    config_fail_test(request, 'stream/eht-id-not-int')


def test_eht_id_too_small(request, config_fail_test):
    config_fail_test(request, 'stream/eht-id-too-small')


def test_eht_id_wrong_signed(request, config_fail_test):
    config_fail_test(request, 'stream/eht-id-wrong-signed')


def test_eht_invalid_type(request, config_fail_test):
    config_fail_test(request, 'stream/eht-invalid-type')


def test_eht_not_struct(request, config_fail_test):
    config_fail_test(request, 'stream/eht-not-struct')


def test_eht_timestamp_not_int(request, config_fail_test):
    config_fail_test(request, 'stream/eht-timestamp-not-int')


def test_eht_timestamp_wrong_pm(request, config_fail_test):
    config_fail_test(request, 'stream/eht-timestamp-wrong-pm')


def test_eht_timestamp_wrong_signed(request, config_fail_test):
    config_fail_test(request, 'stream/eht-timestamp-wrong-signed')


def test_events_empty(request, config_fail_test):
    config_fail_test(request, 'stream/events-empty')


def test_events_invalid_type(request, config_fail_test):
    config_fail_test(request, 'stream/events-invalid-type')


def test_events_key_invalid_identifier(request, config_fail_test):
    config_fail_test(request, 'stream/events-key-invalid-identifier')


def test_events_no(request, config_fail_test):
    config_fail_test(request, 'stream/events-no')


def test_pct_cs_not_int(request, config_fail_test):
    config_fail_test(request, 'stream/pct-cs-not-int')


def test_pct_cs_wrong_signed(request, config_fail_test):
    config_fail_test(request, 'stream/pct-cs-wrong-signed')


def test_pct_cs_yes_ps_no(request, config_fail_test):
    config_fail_test(request, 'stream/pct-cs-yes-ps-no')


def test_pct_ed_not_int(request, config_fail_test):
    config_fail_test(request, 'stream/pct-ed-not-int')


def test_pct_ed_wrong_signed(request, config_fail_test):
    config_fail_test(request, 'stream/pct-ed-wrong-signed')


def test_pct_invalid_type(request, config_fail_test):
    config_fail_test(request, 'stream/pct-invalid-type')


def test_pct_not_struct(request, config_fail_test):
    config_fail_test(request, 'stream/pct-not-struct')


def test_pct_no(request, config_fail_test):
    config_fail_test(request, 'stream/pct-no')


def test_pct_ps_not_int(request, config_fail_test):
    config_fail_test(request, 'stream/pct-ps-not-int')


def test_pct_ps_wrong_signed(request, config_fail_test):
    config_fail_test(request, 'stream/pct-ps-wrong-signed')


def test_pct_ps_yes_cs_no(request, config_fail_test):
    config_fail_test(request, 'stream/pct-ps-yes-cs-no')


def test_pct_tb_not_int(request, config_fail_test):
    config_fail_test(request, 'stream/pct-tb-not-int')


def test_pct_tb_te_different_clocks(request, config_fail_test):
    config_fail_test(request, 'stream/pct-tb-te-different-clocks')


def test_pct_tb_wrong_pm(request, config_fail_test):
    config_fail_test(request, 'stream/pct-tb-wrong-pm')


def test_pct_tb_wrong_signed(request, config_fail_test):
    config_fail_test(request, 'stream/pct-tb-wrong-signed')


def test_pct_tb_yes_te_no(request, config_fail_test):
    config_fail_test(request, 'stream/pct-tb-yes-te-no')


def test_pct_te_not_int(request, config_fail_test):
    config_fail_test(request, 'stream/pct-te-not-int')


def test_pct_te_wrong_pm(request, config_fail_test):
    config_fail_test(request, 'stream/pct-te-wrong-pm')


def test_pct_te_wrong_signed(request, config_fail_test):
    config_fail_test(request, 'stream/pct-te-wrong-signed')


def test_pct_te_yes_tb_no(request, config_fail_test):
    config_fail_test(request, 'stream/pct-te-yes-tb-no')


def test_unknown_prop(request, config_fail_test):
    config_fail_test(request, 'stream/unknown-prop')
