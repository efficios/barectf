#!/usr/bin/env bats

# The MIT License (MIT)
#
# Copyright (c) 2016 Philippe Proulx <pproulx@efficios.com>
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

load ../../../common
load ../../common

@test 'wrong "$include" property type makes barectf fail' {
  barectf_assert_file_exists invalid-type.yaml
  barectf_config_check_fail
}

@test 'non-existing file in "$include" property (string) makes barectf fail' {
  barectf_assert_file_exists file-not-found.yaml
  barectf_config_check_fail
}

@test 'non-existing absolute file in "$include" property (string) makes barectf fail' {
  barectf_assert_file_exists file-not-found-abs.yaml
  barectf_config_check_fail
}

@test 'non-existing file in "$include" property (array) makes barectf fail' {
  barectf_assert_file_exists file-not-found-in-array.yaml
  barectf_config_check_fail
}

@test 'non-existing file in "$include" property (recursive) makes barectf fail' {
  barectf_assert_file_exists file-not-found-recursive.yaml
  barectf_config_check_fail
}

@test 'cycle in include graph makes barectf fail' {
  barectf_assert_file_exists cycle.yaml
  barectf_config_check_fail
}

@test 'cycle in include graph (with a symbolic link) makes barectf fail' {
  local symlink="$BATS_TEST_DIRNAME/inc-recursive-sym3.yaml"
  ln -fs inc-recursive-sym1.yaml "$symlink"
  barectf_assert_file_exists cycle-sym.yaml
  barectf_config_check_fail
  rm -f "$symlink"
}
