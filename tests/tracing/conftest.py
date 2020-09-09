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
import os
import os.path
import barectf
import shutil
import subprocess


@pytest.fixture
def tracing_succeed_test(yaml_cfg_path, request, tmpdir):
    def func():
        test_dir = os.path.dirname(request.fspath)

        # Use the test's module and function names to automatically find
        # the test-specific expectation files.
        #
        # For:
        #
        # Test module name:
        #     `test_succeed_hello_there.py`
        #
        # Test function name:
        #     `test_how_are_you`
        #
        # The corresponding base expectation file path is
        # `expect/succeed/hello-there/how-are-you'.
        elems = [test_dir, 'expect']
        mod = request.module.__name__
        mod = mod.replace('test_', '')
        mod = mod.replace('_', '-')
        parts = mod.split('-')
        elems.append(parts[0])
        elems.append('-'.join(parts[1:]))
        func = request.function.__name__
        func = func.replace('test_', '')
        func = func.replace('_', '-')
        elems.append(func)
        expect_base_path = os.path.join(*elems)

        # Use the test's module and function names to automatically find
        # the test-specific C source file.
        #
        # For:
        #
        # Test module name:
        #     `test_succeed_hello_there.py`
        #
        # Test function name:
        #     `test_how_are_you`
        #
        # The corresponding expectation file path is
        # `src/succeed/hello-there/how-are-you.c'.
        elems = [test_dir, 'src']
        mod = request.module.__name__
        mod = mod.replace('test_', '')
        mod = mod.replace('_', '-')
        parts = mod.split('-')
        elems.append(parts[0])
        elems.append('-'.join(parts[1:]))
        func = request.function.__name__
        func = func.replace('test_', '')
        func = func.replace('_', '-')
        elems.append(f'{func}.c')
        src_path = os.path.join(*elems)

        # create barectf configuration
        with open(yaml_cfg_path) as f:
            cfg = barectf.configuration_from_file(f)

        # generate and write C code files
        cg = barectf.CodeGenerator(cfg)
        files = cg.generate_c_headers()
        files += cg.generate_c_sources()

        for file in files:
            with open(os.path.join(tmpdir, file.name), 'w') as f:
                f.write(file.contents)

        # generate metadata stream, stripping the version and date
        file = cg.generate_metadata_stream()
        lines = file.contents.split('\n')
        new_lines = []
        discard_patterns = [
            'Copyright (c)',
            'The following code was generated',
            '* on ',
            'barectf_gen_date =',
            'tracer_major =',
            'tracer_minor =',
            'tracer_patch =',
        ]

        for line in lines:
            skip = False

            for pattern in discard_patterns:
                if pattern in line:
                    skip = True

            if skip:
                continue

            new_lines.append(line)

        actual_metadata = '\n'.join(new_lines)

        # copy Makefile to build directory
        support_dir = os.path.join(test_dir, 'support')
        shutil.copy(os.path.join(support_dir, 'Makefile'), tmpdir)

        # copy platform files to build directory
        shutil.copy(os.path.join(support_dir, 'test-platform.c'), tmpdir)
        shutil.copy(os.path.join(support_dir, 'test-platform.h'), tmpdir)

        # copy specific source code file to build directory
        shutil.copy(src_path, os.path.join(tmpdir, 'test.c'))

        # build the test
        subprocess.check_output(['make'], cwd=tmpdir)

        # run the test (produce the data stream)
        subprocess.check_output(['./test'], cwd=tmpdir)

        # read actual stream
        with open(os.path.join(tmpdir, 'stream'), 'rb') as f:
            actual_stream = f.read()

        # read data stream expectation file
        with open(f'{expect_base_path}.data.expect', 'rb') as f:
            expected_stream = f.read()

        # read metadata stream expectation file
        with open(f'{expect_base_path}.metadata.expect', 'r') as f:
            expected_metadata = f.read()

        # validate streams
        assert actual_metadata == expected_metadata
        assert actual_stream == expected_stream

    return func
