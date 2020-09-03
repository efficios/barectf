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

def test_clocks_invalid_type(request, config_fail_test):
    config_fail_test(request, 'metadata/clocks-invalid-type')


def test_clocks_key_invalid_identifier(request, config_fail_test):
    config_fail_test(request, 'metadata/clocks-key-invalid-identifier')


def test_default_stream_invalid_type(request, config_fail_test):
    config_fail_test(request, 'metadata/default-stream-invalid-type')


def test_default_stream_stream_default_duplicate(request, config_fail_test):
    config_fail_test(request, 'metadata/default-stream-stream-default-duplicate')


def test_default_stream_unknown_stream(request, config_fail_test):
    config_fail_test(request, 'metadata/default-stream-unknown-stream')


def test_env_invalid_type(request, config_fail_test):
    config_fail_test(request, 'metadata/env-invalid-type')


def test_env_key_invalid_identifier(request, config_fail_test):
    config_fail_test(request, 'metadata/env-key-invalid-identifier')


def test_env_value_invalid_type(request, config_fail_test):
    config_fail_test(request, 'metadata/env-value-invalid-type')


def test_ll_invalid_type(request, config_fail_test):
    config_fail_test(request, 'metadata/ll-invalid-type')


def test_ll_value_invalid_type(request, config_fail_test):
    config_fail_test(request, 'metadata/ll-value-invalid-type')


def test_multiple_streams_trace_ph_no_stream_id(request, config_fail_test):
    config_fail_test(request, 'metadata/multiple-streams-trace-ph-no-stream-id')


def test_streams_empty(request, config_fail_test):
    config_fail_test(request, 'metadata/streams-empty')


def test_streams_invalid_type(request, config_fail_test):
    config_fail_test(request, 'metadata/streams-invalid-type')


def test_streams_key_invalid_identifier(request, config_fail_test):
    config_fail_test(request, 'metadata/streams-key-invalid-identifier')


def test_streams_no(request, config_fail_test):
    config_fail_test(request, 'metadata/streams-no')


def test_ta_invalid_type(request, config_fail_test):
    config_fail_test(request, 'metadata/ta-invalid-type')


def test_trace_empty(request, config_fail_test):
    config_fail_test(request, 'metadata/trace-empty')


def test_trace_invalid_type(request, config_fail_test):
    config_fail_test(request, 'metadata/trace-invalid-type')


def test_trace_no(request, config_fail_test):
    config_fail_test(request, 'metadata/trace-no')


def test_unknown_prop(request, config_fail_test):
    config_fail_test(request, 'metadata/unknown-prop')
