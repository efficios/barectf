#!/usr/bin/env bats

load ../../../common
load ../../common

@test 'unknown property in enum type object makes barectf fail' {
  barectf_assert_file_exists unknown-prop.yaml
  barectf_config_check_fail
}

@test 'no "value-type" property in enum type object makes barectf fail' {
  barectf_assert_file_exists vt-no.yaml
  barectf_config_check_fail
}

@test 'wrong "value-type" property type in enum type object makes barectf fail' {
  barectf_assert_file_exists vt-invalid-type.yaml
  barectf_config_check_fail
}

@test 'no "members" property in enum type object makes barectf fail' {
  barectf_assert_file_exists members-no.yaml
  barectf_config_check_fail
}

@test 'wrong "members" property type in enum type object makes barectf fail' {
  barectf_assert_file_exists members-invalid-type.yaml
  barectf_config_check_fail
}

@test 'empty "members" property in enum type object makes barectf fail' {
  barectf_assert_file_exists members-empty.yaml
  barectf_config_check_fail
}

@test 'wrong "members" property element type in enum type object makes barectf fail' {
  barectf_assert_file_exists members-el-invalid-type.yaml
  barectf_config_check_fail
}

@test 'unknown property in enum type member object makes barectf fail' {
  barectf_assert_file_exists members-el-member-unknown-prop.yaml
  barectf_config_check_fail
}

@test 'wrong "label" property type in enum type member object makes barectf fail' {
  barectf_assert_file_exists members-el-member-label-invalid-type.yaml
  barectf_config_check_fail
}

@test 'wrong "value" property type in enum type member object makes barectf fail' {
  barectf_assert_file_exists members-el-member-value-invalid-type.yaml
  barectf_config_check_fail
}

@test '"value" property outside the unsigned value type range in enum type member object makes barectf fail' {
  barectf_assert_file_exists members-el-member-value-outside-range-unsigned.yaml
  barectf_config_check_fail
}

@test '"value" property outside the signed value type range in enum type member object makes barectf fail' {
  barectf_assert_file_exists members-el-member-value-outside-range-signed.yaml
  barectf_config_check_fail
}

@test 'overlapping members in enum type object makes barectf fail' {
  barectf_assert_file_exists members-overlap.yaml
  barectf_config_check_fail
}
