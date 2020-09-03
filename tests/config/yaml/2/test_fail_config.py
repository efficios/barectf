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

def test_metadata_invalid_type(request, config_fail_test):
    config_fail_test(request, 'config/metadata-invalid-type')


def test_metadata_no(request, config_fail_test):
    config_fail_test(request, 'config/metadata-no')


def test_options_gen_default_stream_def_invalid_type(request, config_fail_test):
    config_fail_test(request, 'config/options-gen-default-stream-def-invalid-type')


def test_options_gen_prefix_def_invalid_type(request, config_fail_test):
    config_fail_test(request, 'config/options-gen-prefix-def-invalid-type')


def test_options_invalid_type(request, config_fail_test):
    config_fail_test(request, 'config/options-invalid-type')


def test_options_unknown_prop(request, config_fail_test):
    config_fail_test(request, 'config/options-unknown-prop')


def test_prefix_invalid_identifier(request, config_fail_test):
    config_fail_test(request, 'config/prefix-invalid-identifier')


def test_prefix_invalid_type(request, config_fail_test):
    config_fail_test(request, 'config/prefix-invalid-type')


def test_unknown_prop(request, config_fail_test):
    config_fail_test(request, 'config/unknown-prop')


def test_version_invalid_19(request, config_fail_test):
    config_fail_test(request, 'config/version-invalid-19')


def test_version_invalid_23(request, config_fail_test):
    config_fail_test(request, 'config/version-invalid-23')


def test_version_invalid_type(request, config_fail_test):
    config_fail_test(request, 'config/version-invalid-type')


def test_version_no(request, config_fail_test):
    config_fail_test(request, 'config/version-no')
