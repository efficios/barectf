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
import tempfile


def pytest_collect_file(parent, path):
    yaml_ext = '.yaml'

    if path.ext != yaml_ext:
        # not a YAML file: cancel
        return

    # If `path` is
    # `/home/jo/barectf/tests/tracing/configs/basic/static-array/of-str.yaml`,
    # for example, then:
    #
    # `cat`:
    #     `basic`
    #
    # `subcat`:
    #     `static-array`
    #
    # `file_name`:
    #     `of-str.yaml`
    path_str = str(path)
    file_name = os.path.basename(path_str)
    subcat_dir = os.path.dirname(path_str)
    subcat = os.path.basename(subcat_dir)
    cat_dir = os.path.dirname(subcat_dir)
    cat = os.path.basename(cat_dir)
    configs_dir = os.path.dirname(cat_dir)
    valid_cats = {
        'basic',
        'counter-clock',
        'basic-extra-pc-ft-members',
    }

    if cat not in valid_cats or os.path.basename(configs_dir) != 'configs':
        # not a YAML configuration test
        return

    # create C source, expectation file, and support directory paths
    base_dir = os.path.dirname(configs_dir)
    base_name = file_name.replace(yaml_ext, '')
    subcat_rel_dir = os.path.join(cat, subcat)
    src_path = os.path.join(base_dir, 'src', subcat_rel_dir, f'{base_name}.c')
    data_expect_path = os.path.join(base_dir, 'expect', subcat_rel_dir, f'{base_name}.data.expect')
    metadata_expect_path = os.path.join(base_dir, 'expect', subcat_rel_dir,
                                        f'{base_name}.metadata.expect')
    support_dir_path = os.path.join(base_dir, 'support', cat)

    # create the file node
    return _YamlFile.from_parent(parent, fspath=path, src_path=src_path,
                                 data_expect_path=data_expect_path,
                                 metadata_expect_path=metadata_expect_path,
                                 support_dir_path=support_dir_path,
                                 name=f'test-{cat}-{subcat}-{base_name}')


class _YamlFile(pytest.File):
    def __init__(self, parent, fspath, src_path, data_expect_path, metadata_expect_path,
                 support_dir_path, name):
        super().__init__(parent=parent, fspath=fspath)
        self._name = name
        self._src_path = src_path
        self._data_expect_path = data_expect_path
        self._metadata_expect_path = metadata_expect_path
        self._support_dir_path = support_dir_path

    def collect(self):
        # yield a single item
        yield _YamlItem.from_parent(self, name=self._name, src_path=self._src_path,
                                    data_expect_path=self._data_expect_path,
                                    metadata_expect_path=self._metadata_expect_path,
                                    support_dir_path=self._support_dir_path)


class _YamlItem(pytest.Item):
    def __init__(self, parent, name, src_path, data_expect_path, metadata_expect_path,
                 support_dir_path):
        super().__init__(parent=parent, name=name)
        self._src_path = src_path
        self._data_expect_path = data_expect_path
        self._metadata_expect_path = metadata_expect_path
        self._support_dir_path = support_dir_path

    def runtest(self):
        # create a temporary directory
        tmpdir = tempfile.TemporaryDirectory(prefix='pytest-barectf')

        # create barectf configuration
        with open(self.fspath) as f:
            cfg = barectf.configuration_from_file(f, inclusion_directories=[self._support_dir_path])

        # generate and write C code files
        cg = barectf.CodeGenerator(cfg)
        files = cg.generate_c_headers()
        files += cg.generate_c_sources()

        for file in files:
            with open(os.path.join(tmpdir.name, file.name), 'w') as f:
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
            'tracer_pre =',
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
        shutil.copy(os.path.join(self._support_dir_path, 'Makefile'), tmpdir.name)

        # copy platform files to build directory
        shutil.copy(os.path.join(self._support_dir_path, 'test-platform.c'), tmpdir.name)
        shutil.copy(os.path.join(self._support_dir_path, 'test-platform.h'), tmpdir.name)

        # copy specific source code file to build directory
        shutil.copy(self._src_path, os.path.join(tmpdir.name, 'test.c'))

        # build the test
        subprocess.check_output(['make'], cwd=tmpdir.name)

        # run the test (produce the data stream)
        subprocess.check_output(['./test'], cwd=tmpdir.name)

        # read actual stream
        with open(os.path.join(tmpdir.name, 'stream'), 'rb') as f:
            actual_stream = f.read()

        # read data stream expectation file
        with open(self._data_expect_path, 'rb') as f:
            expected_stream = f.read()

        # read metadata stream expectation file
        with open(self._metadata_expect_path, 'r') as f:
            expected_metadata = f.read()

        # validate streams
        assert actual_metadata == expected_metadata
        assert actual_stream == expected_stream

        # delete temporary directory
        tmpdir.cleanup()

    def repr_failure(self, excinfo, style=None):
        return f'`{self.fspath}` failed: {excinfo}.'

    def reportinfo(self):
        return self.fspath, None, self.name
