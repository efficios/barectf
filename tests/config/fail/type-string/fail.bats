#!/usr/bin/env bats

load ../../../common
load ../../common

@test 'unknown property in string type object makes barectf fail' {
  barectf_assert_file_exists unknown-prop.yaml
  barectf_config_check_fail
}
