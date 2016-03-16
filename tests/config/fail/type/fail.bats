#!/usr/bin/env bats

load ../../../common
load ../../common

@test 'type inheriting an unknown type alias makes barectf fail' {
  barectf_assert_file_exists inherit-unknown.yaml
  barectf_config_check_fail
}

@test 'type inheriting a type alias defined after makes barectf fail' {
  barectf_assert_file_exists inherit-forward.yaml
  barectf_config_check_fail
}

@test 'wrong type property type makes barectf fail' {
  barectf_assert_file_exists invalid-type.yaml
  barectf_config_check_fail
}

@test 'no "class" property in type object makes barectf fail' {
  barectf_assert_file_exists no-class.yaml
  barectf_config_check_fail
}
