#!/usr/bin/env bats

load ../../../common
load ../../common

@test 'invalid YAML input makes barectf fail' {
  barectf_assert_file_exists invalid.yaml
  barectf_config_check_fail
}
