# The MIT License (MIT)
#
# Copyright (c) 2015-2016 Philippe Proulx <pproulx@efficios.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

from barectf import config_parse


ConfigParseError = config_parse.ConfigParseError


class Config:
    def __init__(self, metadata, prefix=None, options=None):
        self._metadata = metadata

        if prefix is None:
            self._prefix = 'barectf_'
        else:
            self._prefix = prefix

        if options is None:
            self._options = ConfigOptions()
        else:
            self._options = options

    @property
    def metadata(self):
        return self._metadata

    @property
    def prefix(self):
        return self._prefix

    @property
    def options(self):
        return self._options


class ConfigOptions:
    def __init__(self, gen_prefix_def=False, gen_default_stream_def=False):
        self._gen_prefix_def = False
        self._gen_default_stream_def = False

    @property
    def gen_prefix_def(self):
        return self._gen_prefix_def

    @property
    def gen_default_stream_def(self):
        return self._gen_default_stream_def


def from_file(path, include_dirs, ignore_include_not_found, dump_config):
    return config_parse._from_file(path, include_dirs, ignore_include_not_found,
                                   dump_config)


# deprecated
from_yaml_file = from_file
