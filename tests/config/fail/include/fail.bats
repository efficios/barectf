#!/usr/bin/env bats

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
