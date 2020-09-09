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

import pytest
import os.path


@pytest.fixture
def yaml_cfg_path(request):
    # Use the test's module and function names to automatically find the
    # YAML file.
    #
    # For:
    #
    # Test module name:
    #     `test_fail_hello_there.py`
    #
    # Test function name:
    #     `test_how_are_you`
    #
    # The corresponding YAML file path is
    # `configs/fail/hello-there/how-are-you.yaml'.
    elems = [os.path.dirname(request.fspath), 'configs']
    mod = request.module.__name__
    mod = mod.replace('test_', '')
    mod = mod.replace('_', '-')
    parts = mod.split('-')
    elems.append(parts[0])
    elems.append('-'.join(parts[1:]))
    func = request.function.__name__
    func = func.replace('test_', '')
    func = func.replace('_', '-')
    elems.append(f'{func}.yaml')
    return os.path.join(*elems)
