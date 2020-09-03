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

import jinja2
import barectf.config as barectf_config
import barectf.version as barectf_version
from barectf.typing import Count
from typing import Callable, Optional, Any, Mapping


def _filt_indent_tab(text: str, count: Count = Count(1), indent_first: bool = False) -> str:
    in_lines = text.split('\n')
    out_lines = []
    tab = '\t'

    for index, in_line in enumerate(in_lines):
        in_line = in_line.rstrip()

        if len(in_line) == 0 or (index == 0 and not indent_first):
            out_lines.append(in_line)
            continue

        out_lines.append(f'{tab * count}{in_line}')

    return '\n'.join(out_lines)


def _filt_escape_dq(text: str) -> str:
    return text.replace('\\', '\\\\').replace('"', '\\"')


_Filter = Callable[..., Any]
_Filters = Mapping[str, _Filter]
_Test = Callable[..., bool]
_Tests = Mapping[str, _Test]


class _Template:
    def __init__(self, name: str, is_file_template: bool = False,
                 cfg: Optional[barectf_config.Configuration] = None,
                 filters: Optional[_Filters] = None, tests: Optional[_Tests] = None):
        env = jinja2.Environment(trim_blocks=True, lstrip_blocks=True,
                                 loader=jinja2.PackageLoader('barectf', 'templates'))
        env.globals.update({
            'cfg': cfg,
            'barectf_config': barectf_config,
            'barectf_version': barectf_version,
        })

        env.filters['indent_tab'] = _filt_indent_tab
        env.filters['escape_dq'] = _filt_escape_dq

        if filters is not None:
            env.filters.update(filters)

        if tests is not None:
            env.tests.update(tests)

        self._templ = env.get_template(name)
        self._is_file_template = is_file_template

    def render(self, **kwargs) -> str:
        text = self._templ.render(**kwargs)

        if self._is_file_template:
            text = text.strip() + '\n'

        return text
