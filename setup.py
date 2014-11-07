#!/usr/bin/env python3
#
# The MIT License (MIT)
#
# Copyright (c) 2014 Philippe Proulx <philippe.proulx@efficios.com>
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
import os
import sys
import subprocess
from setuptools import setup


# make sure we run Python 3+ here
v = sys.version_info
if v.major < 3:
    sys.stderr.write('Sorry, barectf needs Python 3\n')
    sys.exit(1)


# pyPEG2 needs to be installed manually (for pytsdl) until their PyPI
# tarball is fixed for setuptools.
try:
    import pypeg2
except ImportError:
    sys.stderr.write('Please install pyPEG2 manually:\n\n')
    sys.stderr.write('    sudo pip3 install pyPEG2\n')
    sys.exit(1)


install_requires = [
  'termcolor',
  'pytsdl',
]


packages = [
    'barectf',
]


entry_points = {
    'console_scripts': [
        'barectf = barectf.cli:run'
    ],
}


setup(name='barectf',
      version=0.1,
      description='Generator of ANSI C code that can write native CTF',
      author='Philippe Proulx',
      author_email='eeppeliteloop@gmail.com',
      license='MIT',
      keywords='tsdl ctf metadata',
      url='https://github.com/eepp/barectf',
      packages=packages,
      install_requires=install_requires,
      entry_points=entry_points)
