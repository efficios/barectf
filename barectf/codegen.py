# The MIT License (MIT)
#
# Copyright (c) 2014-2020 Philippe Proulx <pproulx@efficios.com>
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

import barectf.tsdl182gen as barectf_tsdl182gen
import barectf.template as barectf_template
import barectf.config as barectf_config
import barectf.cgen as barectf_cgen


# A file generated by a `CodeGenerator` object.
#
# A generated file has a name (influenced by the configuration's
# file name prefix option) and contents.
class _GeneratedFile:
    def __init__(self, name, contents):
        self._name = name
        self._contents = contents

    @property
    def name(self):
        return self._name

    @property
    def contents(self):
        return self._contents


# A barectf code generator.
#
# Build a code generator with a barectf configuration.
#
# A code generator can generate the TSDL `metadata` file and C source
# and header files.
class CodeGenerator:
    def __init__(self, configuration):
        self._config = configuration
        self._file_name_prefix = configuration.options.code_generation_options.file_name_prefix
        self._c_code_gen = barectf_cgen._CodeGen(configuration)
        self._c_headers = None
        self._c_sources = None
        self._metadata_stream = None

    @property
    def _barectf_header_name(self):
        return f'{self._file_name_prefix}.h'

    @property
    def _bitfield_header_name(self):
        return f'{self._file_name_prefix}-bitfield.h'

    def generate_c_headers(self):
        if self._c_headers is None:
            self._c_headers = [
                _GeneratedFile(self._barectf_header_name, self._c_code_gen.gen_header()),
                _GeneratedFile(self._bitfield_header_name, self._c_code_gen.gen_bitfield_header()),
            ]

        return self._c_headers

    def generate_c_sources(self):
        if self._c_sources is None:
            self._c_sources = [
                _GeneratedFile(f'{self._file_name_prefix}.c',
                               self._c_code_gen.gen_src(self._barectf_header_name,
                                                        self._bitfield_header_name))
            ]

        return self._c_sources

    def generate_metadata_stream(self):
        if self._metadata_stream is None:
            self._metadata_stream = _GeneratedFile('metadata',
                                                   barectf_tsdl182gen._from_config(self._config))

        return self._metadata_stream
