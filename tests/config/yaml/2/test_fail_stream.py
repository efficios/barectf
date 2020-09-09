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

def test_default_invalid_type(config_fail_test):
    config_fail_test()


def test_ect_invalid_type(config_fail_test):
    config_fail_test()


def test_ect_not_struct(config_fail_test):
    config_fail_test()


def test_eht_id_no_multiple_events(config_fail_test):
    config_fail_test()


def test_eht_id_not_int(config_fail_test):
    config_fail_test()


def test_eht_id_too_small(config_fail_test):
    config_fail_test()


def test_eht_id_wrong_signed(config_fail_test):
    config_fail_test()


def test_eht_invalid_type(config_fail_test):
    config_fail_test()


def test_eht_not_struct(config_fail_test):
    config_fail_test()


def test_eht_timestamp_not_int(config_fail_test):
    config_fail_test()


def test_eht_timestamp_wrong_pm(config_fail_test):
    config_fail_test()


def test_eht_timestamp_wrong_signed(config_fail_test):
    config_fail_test()


def test_events_empty(config_fail_test):
    config_fail_test()


def test_events_invalid_type(config_fail_test):
    config_fail_test()


def test_events_key_invalid_identifier(config_fail_test):
    config_fail_test()


def test_events_no(config_fail_test):
    config_fail_test()


def test_pct_cs_not_int(config_fail_test):
    config_fail_test()


def test_pct_cs_wrong_signed(config_fail_test):
    config_fail_test()


def test_pct_cs_yes_ps_no(config_fail_test):
    config_fail_test()


def test_pct_ed_not_int(config_fail_test):
    config_fail_test()


def test_pct_ed_wrong_signed(config_fail_test):
    config_fail_test()


def test_pct_invalid_type(config_fail_test):
    config_fail_test()


def test_pct_not_struct(config_fail_test):
    config_fail_test()


def test_pct_no(config_fail_test):
    config_fail_test()


def test_pct_ps_not_int(config_fail_test):
    config_fail_test()


def test_pct_ps_wrong_signed(config_fail_test):
    config_fail_test()


def test_pct_ps_yes_cs_no(config_fail_test):
    config_fail_test()


def test_pct_tb_not_int(config_fail_test):
    config_fail_test()


def test_pct_tb_te_different_clocks(config_fail_test):
    config_fail_test()


def test_pct_tb_wrong_pm(config_fail_test):
    config_fail_test()


def test_pct_tb_wrong_signed(config_fail_test):
    config_fail_test()


def test_pct_tb_yes_te_no(config_fail_test):
    config_fail_test()


def test_pct_te_not_int(config_fail_test):
    config_fail_test()


def test_pct_te_wrong_pm(config_fail_test):
    config_fail_test()


def test_pct_te_wrong_signed(config_fail_test):
    config_fail_test()


def test_pct_te_yes_tb_no(config_fail_test):
    config_fail_test()


def test_unknown_prop(config_fail_test):
    config_fail_test()
