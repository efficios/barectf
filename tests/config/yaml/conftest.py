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
import barectf


def pytest_collect_file(parent, path):
    yaml_ext = '.yaml'

    if path.ext != yaml_ext:
        # not a YAML file: cancel
        return

    if path.fnmatch('*.inc.yaml'):
        # not a top-level test file (partial inclusion YAML file)
        return

    # At the end of this loop, if `path` is
    # `/home/jo/barectf/tests/config/yaml/2/configs/fail/stream/pct-no.yaml`,
    # for example, then `elems` is:
    #
    # * `pct-no.yaml`
    # * `stream`
    # * `fail`
    path_str = str(path)
    elems = []

    while True:
        elem = os.path.basename(path_str)

        if elem == 'configs':
            break

        elems.append(elem)
        path_str = os.path.dirname(path_str)

    # create a unique test name
    name = f'test-{"-".join(reversed(elems))}'.replace(yaml_ext, '')

    # create the file node
    if 'fail' in elems:
        return _YamlFileFail.from_parent(parent, fspath=path, name=name)
    elif 'pass' in elems:
        return _YamlFilePass.from_parent(parent, fspath=path, name=name)
    else:
        # YAML file is not a test case
        return


class _YamlItem(pytest.Item):
    def runtest(self):
        yaml_dir = self.fspath.dirname

        with open(str(self.fspath)) as f:
            self._runtest(f, yaml_dir)

    def reportinfo(self):
        return self.fspath, None, self.name


class _YamlItemFail(_YamlItem):
    def _runtest(self, f, yaml_dir):
        with pytest.raises(barectf._ConfigurationParseError):
            barectf.configuration_from_file(f, inclusion_directories=[yaml_dir])

    def repr_failure(self, excinfo, style=None):
        return f'`{self.fspath}` did not make barectf.configuration_from_file() raise `barectf._ConfigurationParseError`: {excinfo}.'


class _YamlItemPass(_YamlItem):
    def _runtest(self, f, yaml_dir):
        barectf.configuration_from_file(f, inclusion_directories=[yaml_dir])

    def repr_failure(self, excinfo, style=None):
        return f'`{self.fspath}` barectf.configuration_from_file() raised an exception.: {excinfo}.'


class _YamlFile(pytest.File):
    def __init__(self, parent, fspath, name):
        super().__init__(parent=parent, fspath=fspath)
        self._name = name

    def collect(self):
        # yield a single item
        yield self._item_cls.from_parent(self, name=self._name)


class _YamlFileFail(_YamlFile):
    _item_cls = _YamlItemFail


class _YamlFilePass(_YamlFile):
    _item_cls = _YamlItemPass
