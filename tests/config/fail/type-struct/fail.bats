#!/usr/bin/env bats

load ../../../common
load ../../common

@test 'unknown property in struct type object makes barectf fail' {
  barectf_assert_file_exists unknown-prop.yaml
  barectf_config_check_fail
}

@test 'wrong "fields" property type in struct type object makes barectf fail' {
  barectf_assert_file_exists fields-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid field in "fields" property (invalid C identifier) in struct type object makes barectf fail' {
  barectf_assert_file_exists fields-field-invalid-identifier.yaml
  barectf_config_check_fail
}

@test 'wrong "min-align" property type in struct type object makes barectf fail' {
  barectf_assert_file_exists ma-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "min-align" property (0) in struct type object makes barectf fail' {
  barectf_assert_file_exists ma-0.yaml
  barectf_config_check_fail
}

@test 'invalid "min-align" property (3) in struct type object makes barectf fail' {
  barectf_assert_file_exists ma-3.yaml
  barectf_config_check_fail
}
