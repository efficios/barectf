# The MIT License (MIT)
#
# Copyright (c) 2014-2020 Philippe Proulx <pproulx@efficios.com>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import barectf.config_parse_common as barectf_config_parse_common
import barectf.version as barectf_version
import barectf.config as barectf_config
import barectf.config_file as barectf_config_file
import barectf.codegen as barectf_codegen
import barectf.typing as barectf_typing


# version API
__major_version__ = barectf_version.__major_version__
__minor_version__ = barectf_version.__minor_version__
__patch_version__ = barectf_version.__patch_version__
__pre_version__ = barectf_version.__pre_version__
__version__ = barectf_version.__version__


# common typing API
Index = barectf_typing.Index
Count = barectf_typing.Count
Id = barectf_typing.Id
Alignment = barectf_typing.Alignment
VersionNumber = barectf_typing.VersionNumber


# configuration API
_ArrayFieldType = barectf_config._ArrayFieldType
_BitArrayFieldType = barectf_config._BitArrayFieldType
_ConfigurationParseError = barectf_config_parse_common._ConfigurationParseError
_EnumerationFieldType = barectf_config._EnumerationFieldType
_FieldType = barectf_config._FieldType
_IntegerFieldType = barectf_config._IntegerFieldType
ByteOrder = barectf_config.ByteOrder
ClockType = barectf_config.ClockType
ClockTypeCTypes = barectf_config.ClockTypeCTypes
ClockTypeOffset = barectf_config.ClockTypeOffset
Configuration = barectf_config.Configuration
ConfigurationCodeGenerationHeaderOptions = barectf_config.ConfigurationCodeGenerationHeaderOptions
ConfigurationCodeGenerationOptions = barectf_config.ConfigurationCodeGenerationOptions
ConfigurationOptions = barectf_config.ConfigurationOptions
DEFAULT_FIELD_TYPE = barectf_config.DEFAULT_FIELD_TYPE
DisplayBase = barectf_config.DisplayBase
DynamicArrayFieldType = barectf_config.DynamicArrayFieldType
EnumerationFieldTypeMapping = barectf_config.EnumerationFieldTypeMapping
EnumerationFieldTypeMappingRange = barectf_config.EnumerationFieldTypeMappingRange
EnumerationFieldTypeMappings = barectf_config.EnumerationFieldTypeMappings
EventRecordType = barectf_config.EventRecordType
LogLevel = barectf_config.LogLevel
RealFieldType = barectf_config.RealFieldType
SignedEnumerationFieldType = barectf_config.SignedEnumerationFieldType
SignedIntegerFieldType = barectf_config.SignedIntegerFieldType
StaticArrayFieldType = barectf_config.StaticArrayFieldType
DataStreamType = barectf_config.DataStreamType
DataStreamTypeEventRecordFeatures = barectf_config.DataStreamTypeEventRecordFeatures
DataStreamTypeFeatures = barectf_config.DataStreamTypeFeatures
DataStreamTypePacketFeatures = barectf_config.DataStreamTypePacketFeatures
StringFieldType = barectf_config.StringFieldType
StructureFieldType = barectf_config.StructureFieldType
StructureFieldTypeMember = barectf_config.StructureFieldTypeMember
StructureFieldTypeMembers = barectf_config.StructureFieldTypeMembers
Trace = barectf_config.Trace
TraceEnvironment = barectf_config.TraceEnvironment
TraceType = barectf_config.TraceType
TraceTypeFeatures = barectf_config.TraceTypeFeatures
UnsignedEnumerationFieldType = barectf_config.UnsignedEnumerationFieldType
UnsignedIntegerFieldType = barectf_config.UnsignedIntegerFieldType


# configuration file API
configuration_file_major_version = barectf_config_file.configuration_file_major_version
configuration_from_file = barectf_config_file.configuration_from_file
effective_configuration_file = barectf_config_file.effective_configuration_file


# code generation API
CodeGenerator = barectf_codegen.CodeGenerator


# remove local names
del barectf_config_parse_common
del barectf_version
del barectf_config
del barectf_config_file
del barectf_codegen
del barectf_typing
