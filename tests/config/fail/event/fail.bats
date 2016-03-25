#!/usr/bin/env bats

load ../../../common
load ../../common

@test 'unknown property in event object makes barectf fail' {
  barectf_assert_file_exists unknown-prop.yaml
  barectf_config_check_fail
}

@test 'wrong "log-level" property type in event object makes barectf fail' {
  barectf_assert_file_exists ll-invalid-type.yaml
  barectf_config_check_fail
}

@test 'non existing log level name as "log-level" property value in event object makes barectf fail' {
  barectf_assert_file_exists ll-non-existing.yaml
  barectf_config_check_fail
}

@test 'wrong "context-type" property type in event object makes barectf fail' {
  barectf_assert_file_exists ct-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "context-type" property field type (not a structure) in event object makes barectf fail' {
  barectf_assert_file_exists ct-not-struct.yaml
  barectf_config_check_fail
}

@test 'wrong "payload-type" property type in event object makes barectf fail' {
  barectf_assert_file_exists pt-invalid-type.yaml
  barectf_config_check_fail
}

@test 'invalid "payload-type" property field type (not a structure) in event object makes barectf fail' {
  barectf_assert_file_exists pt-not-struct.yaml
  barectf_config_check_fail
}

@test 'empty event object makes barectf fail' {
  barectf_assert_file_exists no-fields-at-all.yaml
  barectf_config_check_fail
}
