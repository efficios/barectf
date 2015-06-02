# The MIT License (MIT)
#
# Copyright (c) 2015 Philippe Proulx <pproulx@efficios.com>
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


class CodeGenerator:
    def __init__(self, indent_string):
        self._indent_string = indent_string
        self.reset()

    @property
    def code(self):
        return '\n'.join(self._lines)

    def reset(self):
        self._lines = []
        self._indent = 0
        self._glue = False

    def add_line(self, line):
        if self._glue:
            self.append_to_last_line(line)
            self._glue = False
            return

        indent_string = self._get_indent_string()
        self._lines.append(indent_string + str(line))

    def add_lines(self, lines):
        if type(lines) is str:
            lines = lines.split('\n')

        for line in lines:
            self.add_line(line)

    def add_glue(self):
        self._glue = True

    def append_to_last_line(self, s):
        if self._lines:
            self._lines[-1] += str(s)

    def add_empty_line(self):
        self._lines.append('')

    def add_cc_line(self, comment):
        self.add_line('/* {} */'.format(comment))

    def append_cc_to_last_line(self, comment, with_space=True):
        if with_space:
            sp = ' '
        else:
            sp = ''

        self.append_to_last_line('{}/* {} */'.format(sp, comment))

    def indent(self):
        self._indent += 1

    def unindent(self):
        self._indent = max(self._indent - 1, 0)

    def _get_indent_string(self):
        return self._indent_string * self._indent
