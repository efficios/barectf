# The MIT License (MIT)
#
# Copyright (c) 2015-2020 Philippe Proulx <pproulx@efficios.com>
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

from barectf.config_parse_common import _ConfigurationParseError
from barectf.config_parse_common import _append_error_ctx
import barectf.config_parse_common as config_parse_common
import collections
import copy


def _del_prop_if_exists(node, prop_name):
    if prop_name in node:
        del node[prop_name]


def _rename_prop(node, old_prop_name, new_prop_name):
    if old_prop_name in node:
        node[new_prop_name] = node[old_prop_name]
        del node[old_prop_name]


def _copy_prop_if_exists(dst_node, src_node, src_prop_name, dst_prop_name=None):
    if dst_prop_name is None:
        dst_prop_name = src_prop_name

    if src_prop_name in src_node:
        dst_node[dst_prop_name] = copy.deepcopy(src_node[src_prop_name])


# A barectf 2 YAML configuration parser.
#
# The only purpose of such a parser is to transform the passed root
# configuration node so that it's a valid barectf 3 configuration node.
#
# The parser's `config_node` property is the equivalent barectf 3
# configuration node.
#
# See the comments of _parse() for more implementation details about the
# parsing stages and general strategy.
class _Parser(config_parse_common._Parser):
    # Builds a barectf 2 YAML configuration parser and parses the root
    # configuration node `node` (already loaded from `path`).
    def __init__(self, path, node, with_pkg_include_dir, include_dirs, ignore_include_not_found):
        super().__init__(path, node, with_pkg_include_dir, include_dirs, ignore_include_not_found, 2)
        self._ft_cls_name_to_conv_method = {
            'int': self._conv_int_ft_node,
            'integer': self._conv_int_ft_node,
            'enum': self._conv_enum_ft_node,
            'enumeration': self._conv_enum_ft_node,
            'flt': self._conv_real_ft_node,
            'float': self._conv_real_ft_node,
            'floating-point': self._conv_real_ft_node,
            'str': self._conv_string_ft_node,
            'string': self._conv_string_ft_node,
            'array': self._conv_static_array_ft_node,
            'struct': self._conv_struct_ft_node,
            'structure': self._conv_struct_ft_node,
        }
        self._parse()

    # Converts a v2 field type node to a v3 field type node and returns
    # it.
    def _conv_ft_node(self, v2_ft_node):
        assert 'class' in v2_ft_node
        cls = v2_ft_node['class']
        assert cls in self._ft_cls_name_to_conv_method
        return self._ft_cls_name_to_conv_method[cls](v2_ft_node)

    def _conv_ft_node_if_exists(self, v2_parent_node, key):
        if v2_parent_node is None:
            return

        if key not in v2_parent_node:
            return

        return self._conv_ft_node(v2_parent_node[key])

    # Converts a v2 integer field type node to a v3 integer field type
    # node and returns it.
    def _conv_int_ft_node(self, v2_ft_node):
        # copy v2 integer field type node
        v3_ft_node = copy.deepcopy(v2_ft_node)

        # signedness depends on the class, not a property
        cls_name = 'uint'
        prop_name = 'signed'
        is_signed_node = v3_ft_node.get(prop_name)

        if is_signed_node is True:
            cls_name = 'sint'

        v3_ft_node['class'] = cls_name
        _del_prop_if_exists(v3_ft_node, prop_name)

        # rename `align` property to `alignment`
        _rename_prop(v3_ft_node, 'align', 'alignment')

        # rename `base` property to `preferred-display-base`
        _rename_prop(v3_ft_node, 'base', 'preferred-display-base')

        # remove `encoding` property
        _del_prop_if_exists(v3_ft_node, 'encoding')

        # remove `property-mappings` property
        _del_prop_if_exists(v3_ft_node, 'property-mappings')

        return v3_ft_node

    # Converts a v2 enumeration field type node to a v3 enumeration
    # field type node and returns it.
    def _conv_enum_ft_node(self, v2_ft_node):
        # An enumeration field type _is_ an integer field type, so use a
        # copy of the converted v2 value field type node.
        v3_ft_node = copy.deepcopy(self._conv_ft_node(v2_ft_node['value-type']))

        # transform class name accordingly
        prop_name = 'class'
        cls_name = 'uenum'

        if v3_ft_node[prop_name] == 'sint':
            cls_name = 'senum'

        v3_ft_node[prop_name] = cls_name

        # convert members to mappings
        prop_name = 'members'
        members_node = v2_ft_node.get(prop_name)

        if members_node is not None:
            mappings_node = collections.OrderedDict()
            cur = 0

            for member_node in members_node:
                if type(member_node) is str:
                    label = member_node
                    v3_value_node = cur
                    cur += 1
                else:
                    assert type(member_node) is collections.OrderedDict
                    label = member_node['label']
                    v2_value_node = member_node['value']

                    if type(v2_value_node) is int:
                        cur = v2_value_node + 1
                        v3_value_node = v2_value_node
                    else:
                        assert type(v2_value_node) is list
                        assert len(v2_value_node) == 2
                        v3_value_node = list(v2_value_node)
                        cur = v2_value_node[1] + 1

                if label not in mappings_node:
                    mappings_node[label] = []

                mappings_node[label].append(v3_value_node)

            v3_ft_node['mappings'] = mappings_node

        return v3_ft_node

    # Converts a v2 real field type node to a v3 real field type node
    # and returns it.
    def _conv_real_ft_node(self, v2_ft_node):
        # copy v2 real field type node
        v3_ft_node = copy.deepcopy(v2_ft_node)

        # set class to `real`
        v3_ft_node['class'] = 'real'

        # rename `align` property to `alignment`
        _rename_prop(v3_ft_node, 'align', 'alignment')

        # set `size` property to a single integer (total size, in bits)
        prop_name = 'size'
        v3_ft_node[prop_name] = v3_ft_node[prop_name]['exp'] + v3_ft_node[prop_name]['mant']

        return v3_ft_node

    # Converts a v2 string field type node to a v3 string field type
    # node and returns it.
    def _conv_string_ft_node(self, v2_ft_node):
        # copy v2 string field type node
        v3_ft_node = copy.deepcopy(v2_ft_node)

        # remove `encoding` property
        _del_prop_if_exists(v3_ft_node, 'encoding')

        return v3_ft_node

    # Converts a v2 array field type node to a v3 (static) array field
    # type node and returns it.
    def _conv_static_array_ft_node(self, v2_ft_node):
        # class renamed to `static-array`
        v3_ft_node = collections.OrderedDict({'class': 'static-array'})

        # copy `length` property
        _copy_prop_if_exists(v3_ft_node, v2_ft_node, 'length')

        # convert element field type
        v3_ft_node['element-field-type'] = self._conv_ft_node(v2_ft_node['element-type'])

        return v3_ft_node

    # Converts a v2 structure field type node to a v3 structure field
    # type node and returns it.
    def _conv_struct_ft_node(self, v2_ft_node):
        # Create fresh v3 structure field type node, reusing the class
        # of `v2_ft_node`.
        v3_ft_node = collections.OrderedDict({'class': v2_ft_node['class']})

        # rename `min-align` property to `minimum-alignment`
        _copy_prop_if_exists(v3_ft_node, v2_ft_node, 'min-align', 'minimum-alignment')

        # convert fields to members
        prop_name = 'fields'

        if prop_name in v2_ft_node:
            members_node = []

            for member_name, v2_member_ft_node in v2_ft_node[prop_name].items():
                members_node.append(collections.OrderedDict({
                    member_name: collections.OrderedDict({
                        'field-type': self._conv_ft_node(v2_member_ft_node)
                    })
                }))

            v3_ft_node['members'] = members_node

        return v3_ft_node

    # Converts a v2 clock type node to a v3 clock type node and returns
    # it.
    def _conv_clk_type_node(self, v2_clk_type_node):
        # copy v2 clock type node
        v3_clk_type_node = copy.deepcopy(v2_clk_type_node)

        # rename `freq` property to `frequency`
        _rename_prop(v3_clk_type_node, 'freq', 'frequency')

        # rename `error-cycles` property to `precision`
        _rename_prop(v3_clk_type_node, 'error-cycles', 'precision')

        # rename `absolute` property to `origin-is-unix-epoch`
        _rename_prop(v3_clk_type_node, 'absolute', 'origin-is-unix-epoch')

        # rename `$return-ctype`/`return-ctype` property to `$c-type`
        new_prop_name = '$c-type'
        _rename_prop(v3_clk_type_node, 'return-ctype', new_prop_name)
        _rename_prop(v3_clk_type_node, '$return-ctype', new_prop_name)

        return v3_clk_type_node

    # Converts a v2 event type node to a v3 event type node and returns
    # it.
    def _conv_ev_type_node(self, v2_ev_type_node):
        # create empty v3 event type node
        v3_ev_type_node = collections.OrderedDict()

        # copy `log-level` property
        _copy_prop_if_exists(v3_ev_type_node, v2_ev_type_node, 'log-level')

        # convert specific context field type node
        v2_ft_node = v2_ev_type_node.get('context-type')

        if v2_ft_node is not None:
            v3_ev_type_node['specific-context-field-type'] = self._conv_ft_node(v2_ft_node)

        # convert payload field type node
        v2_ft_node = v2_ev_type_node.get('payload-type')

        if v2_ft_node is not None:
            v3_ev_type_node['payload-field-type'] = self._conv_ft_node(v2_ft_node)

        return v3_ev_type_node

    @staticmethod
    def _set_v3_feature_ft_if_exists(v3_features_node, key, node):
        val = node

        if val is None:
            val = False

        v3_features_node[key] = val

    # Converts a v2 stream type node to a v3 stream type node and
    # returns it.
    def _conv_stream_type_node(self, v2_stream_type_node):
        # This function creates a v3 stream type features node from the
        # packet context and event header field type nodes of a
        # v2 stream type node.
        def v3_features_node_from_v2_ft_nodes(v2_pkt_ctx_ft_fields_node,
                                              v2_ev_header_ft_fields_node):
            if v2_ev_header_ft_fields_node is None:
                v2_ev_header_ft_fields_node = collections.OrderedDict()

            v3_pkt_total_size_ft_node = self._conv_ft_node(v2_pkt_ctx_ft_fields_node['packet_size'])
            v3_pkt_content_size_ft_node = self._conv_ft_node(v2_pkt_ctx_ft_fields_node['content_size'])
            v3_pkt_beg_time_ft_node = self._conv_ft_node_if_exists(v2_pkt_ctx_ft_fields_node,
                                                                   'timestamp_begin')
            v3_pkt_end_time_ft_node = self._conv_ft_node_if_exists(v2_pkt_ctx_ft_fields_node,
                                                                   'timestamp_end')
            v3_pkt_disc_ev_counter_ft_node = self._conv_ft_node_if_exists(v2_pkt_ctx_ft_fields_node,
                                                                          'events_discarded')
            v3_ev_type_id_ft_node = self._conv_ft_node_if_exists(v2_ev_header_ft_fields_node, 'id')
            v3_ev_time_ft_node = self._conv_ft_node_if_exists(v2_ev_header_ft_fields_node,
                                                              'timestamp')
            v3_features_node = collections.OrderedDict()
            v3_pkt_node = collections.OrderedDict()
            v3_ev_node = collections.OrderedDict()
            v3_pkt_node['total-size-field-type'] = v3_pkt_total_size_ft_node
            v3_pkt_node['content-size-field-type'] = v3_pkt_content_size_ft_node
            self._set_v3_feature_ft_if_exists(v3_pkt_node, 'beginning-time-field-type',
                                              v3_pkt_beg_time_ft_node)
            self._set_v3_feature_ft_if_exists(v3_pkt_node, 'end-time-field-type',
                                              v3_pkt_end_time_ft_node)
            self._set_v3_feature_ft_if_exists(v3_pkt_node, 'discarded-events-counter-field-type',
                                              v3_pkt_disc_ev_counter_ft_node)
            self._set_v3_feature_ft_if_exists(v3_ev_node, 'type-id-field-type',
                                              v3_ev_type_id_ft_node)
            self._set_v3_feature_ft_if_exists(v3_ev_node, 'time-field-type', v3_ev_time_ft_node)
            v3_features_node['packet'] = v3_pkt_node
            v3_features_node['event'] = v3_ev_node
            return v3_features_node

        def clk_type_name_from_v2_int_ft_node(v2_int_ft_node):
            if v2_int_ft_node is None:
                return

            assert v2_int_ft_node['class'] in ('int', 'integer')
            prop_mappings_node = v2_int_ft_node.get('property-mappings')

            if prop_mappings_node is not None and len(prop_mappings_node) > 0:
                return prop_mappings_node[0]['name']

        # create empty v3 stream type node
        v3_stream_type_node = collections.OrderedDict()

        # rename `$default` property to `$is-default`
        _copy_prop_if_exists(v3_stream_type_node, v2_stream_type_node, '$default', '$is-default')

        # set default clock type node
        pct_prop_name = 'packet-context-type'
        v2_pkt_ctx_ft_fields_node = v2_stream_type_node[pct_prop_name]['fields']
        eht_prop_name = 'event-header-type'
        v2_ev_header_ft_fields_node = None
        v2_ev_header_ft_node = v2_stream_type_node.get(eht_prop_name)

        if v2_ev_header_ft_node is not None:
            v2_ev_header_ft_fields_node = v2_ev_header_ft_node['fields']

        def_clk_type_name = None

        try:
            ts_begin_prop_name = 'timestamp_begin'
            ts_begin_clk_type_name = clk_type_name_from_v2_int_ft_node(v2_pkt_ctx_ft_fields_node.get(ts_begin_prop_name))
            ts_end_prop_name = 'timestamp_end'
            ts_end_clk_type_name = clk_type_name_from_v2_int_ft_node(v2_pkt_ctx_ft_fields_node.get(ts_end_prop_name))

            if ts_begin_clk_type_name is not None and ts_end_clk_type_name is not None:
                if ts_begin_clk_type_name != ts_end_clk_type_name:
                    raise _ConfigurationParseError(f'`{ts_begin_prop_name}`/`{ts_end_prop_name}` properties',
                                                   'Field types are not mapped to the same clock type')
        except _ConfigurationParseError as exc:
            _append_error_ctx(exc, f'`{pct_prop_name}` property')

        try:
            if def_clk_type_name is None and v2_ev_header_ft_fields_node is not None:
                def_clk_type_name = clk_type_name_from_v2_int_ft_node(v2_ev_header_ft_fields_node.get('timestamp'))

            if def_clk_type_name is None and ts_begin_clk_type_name is not None:
                def_clk_type_name = ts_begin_clk_type_name

            if def_clk_type_name is None and ts_end_clk_type_name is not None:
                def_clk_type_name = ts_end_clk_type_name
        except _ConfigurationParseError as exc:
            _append_error_ctx(exc, f'`{eht_prop_name}` property')

        if def_clk_type_name is not None:
            v3_stream_type_node['$default-clock-type-name'] = def_clk_type_name

        # set features node
        v3_stream_type_node['$features'] = v3_features_node_from_v2_ft_nodes(v2_pkt_ctx_ft_fields_node,
                                                                             v2_ev_header_ft_fields_node)

        # set extra packet context field type members node
        pkt_ctx_ft_extra_members = []
        ctf_member_names = [
            'packet_size',
            'content_size',
            'timestamp_begin',
            'timestamp_end',
            'events_discarded',
            'packet_seq_num',
        ]

        for member_name, v2_ft_node in v2_pkt_ctx_ft_fields_node.items():
            if member_name in ctf_member_names:
                continue

            pkt_ctx_ft_extra_members.append(collections.OrderedDict({
                member_name: collections.OrderedDict({
                    'field-type': self._conv_ft_node(v2_ft_node)
                })
            }))

        if len(pkt_ctx_ft_extra_members) > 0:
            v3_stream_type_node['packet-context-field-type-extra-members'] = pkt_ctx_ft_extra_members

        # convert event common context field type node
        v2_ft_node = v2_stream_type_node.get('event-context-type')

        if v2_ft_node is not None:
            v3_stream_type_node['event-common-context-field-type'] = self._conv_ft_node(v2_ft_node)

        # convert event type nodes
        v3_event_types_node = collections.OrderedDict()

        for ev_type_name, v2_ev_type_node in v2_stream_type_node['events'].items():
            try:
                v3_event_types_node[ev_type_name] = self._conv_ev_type_node(v2_ev_type_node)
            except _ConfigurationParseError as exc:
                _append_error_ctx(exc, f'Event type `{ev_type_name}`')

        v3_stream_type_node['event-types'] = v3_event_types_node

        return v3_stream_type_node

    # Converts a v2 metadata node to a v3 trace node and returns it.
    def _conv_meta_node(self, v2_meta_node):
        def v3_features_node_from_v2_ft_node(v2_pkt_header_ft_node):
            def set_if_exists(key, node):
                return self._set_v3_feature_ft_if_exists(v3_features_node, key, node)

            v2_pkt_header_ft_fields_node = collections.OrderedDict()

            if v2_pkt_header_ft_node is not None:
                v2_pkt_header_ft_fields_node = v2_pkt_header_ft_node['fields']

            v3_magic_ft_node = self._conv_ft_node_if_exists(v2_pkt_header_ft_fields_node, 'magic')
            v3_uuid_ft_node = self._conv_ft_node_if_exists(v2_pkt_header_ft_fields_node, 'uuid')
            v3_stream_type_id_ft_node = self._conv_ft_node_if_exists(v2_pkt_header_ft_fields_node,
                                                                     'stream_id')
            v3_features_node = collections.OrderedDict()
            set_if_exists('magic-field-type', v3_magic_ft_node)
            set_if_exists('uuid-field-type', v3_uuid_ft_node)
            set_if_exists('stream-type-id-field-type', v3_stream_type_id_ft_node)
            return v3_features_node

        v3_trace_node = collections.OrderedDict()
        v3_trace_type_node = collections.OrderedDict()
        v2_trace_node = v2_meta_node['trace']

        # rename `byte-order` property to `$default-byte-order`
        _copy_prop_if_exists(v3_trace_type_node, v2_trace_node, 'byte-order', '$default-byte-order')

        # copy `uuid` property
        _copy_prop_if_exists(v3_trace_type_node, v2_trace_node, 'uuid')

        # copy `$log-levels`/`log-levels` property
        new_prop_name = '$log-level-aliases'
        _copy_prop_if_exists(v3_trace_type_node, v2_meta_node, 'log-levels', new_prop_name)
        _copy_prop_if_exists(v3_trace_type_node, v2_meta_node, '$log-levels', new_prop_name)

        # copy `clocks` property, converting clock type nodes
        v2_clk_types_node = v2_meta_node.get('clocks')

        if v2_clk_types_node is not None:
            v3_clk_types_node = collections.OrderedDict()

            for name, v2_clk_type_node in v2_clk_types_node.items():
                v3_clk_types_node[name] = self._conv_clk_type_node(v2_clk_type_node)

            v3_trace_type_node['clock-types'] = v3_clk_types_node

        # set features node
        v2_pkt_header_ft_node = v2_trace_node.get('packet-header-type')
        v3_trace_type_node['$features'] = v3_features_node_from_v2_ft_node(v2_pkt_header_ft_node)

        # convert stream type nodes
        v3_stream_types_node = collections.OrderedDict()

        for stream_type_name, v2_stream_type_node in v2_meta_node['streams'].items():
            try:
                v3_stream_types_node[stream_type_name] = self._conv_stream_type_node(v2_stream_type_node)
            except _ConfigurationParseError as exc:
                _append_error_ctx(exc, f'Stream type `{stream_type_name}`')

        v3_trace_type_node['stream-types'] = v3_stream_types_node

        # If `v2_meta_node` has a `$default-stream` property, find the
        # corresponding v3 stream type node and set its `$is-default`
        # property to `True`.
        prop_name = '$default-stream'
        v2_def_stream_type_node = v2_meta_node.get(prop_name)

        if v2_def_stream_type_node is not None:
            found = False

            for stream_type_name, v3_stream_type_node in v3_stream_types_node.items():
                if stream_type_name == v2_def_stream_type_node:
                    v3_stream_type_node['$is-default'] = True
                    found = True
                    break

            if not found:
                raise _ConfigurationParseError(f'`{prop_name}` property',
                                               f'Stream type `{v2_def_stream_type_node}` does not exist')

        # set environment node
        v2_env_node = v2_meta_node.get('env')

        if v2_env_node is not None:
            v3_trace_node['environment'] = copy.deepcopy(v2_env_node)

        # set v3 trace node's type node
        v3_trace_node['type'] = v3_trace_type_node

        return v3_trace_node

    # Transforms the root configuration node into a valid v3
    # configuration node.
    def _transform_config_node(self):
        # remove the `version` property
        del self._root_node['version']

        # relocate prefix and option nodes
        prefix_prop_name = 'prefix'
        v2_prefix_node = self._root_node.get(prefix_prop_name, 'barectf_')
        _del_prop_if_exists(self._root_node, prefix_prop_name)
        opt_prop_name = 'options'
        v2_options_node = self._root_node.get(opt_prop_name)
        _del_prop_if_exists(self._root_node, opt_prop_name)
        code_gen_node = collections.OrderedDict()
        v3_prefixes = config_parse_common._v3_prefixes_from_v2_prefix(v2_prefix_node)
        v3_prefix_node = collections.OrderedDict([
            ('identifier', v3_prefixes.identifier),
            ('file-name', v3_prefixes.file_name),
        ])
        code_gen_node[prefix_prop_name] = v3_prefix_node

        if v2_options_node is not None:
            header_node = collections.OrderedDict()
            _copy_prop_if_exists(header_node, v2_options_node, 'gen-prefix-def',
                                 'identifier-prefix-definition')
            _copy_prop_if_exists(header_node, v2_options_node, 'gen-default-stream-def',
                                 'default-stream-type-name-definition')
            code_gen_node['header'] = header_node

        self._root_node[opt_prop_name] = collections.OrderedDict({
            'code-generation': code_gen_node,
        })

        # convert the v2 metadata node into a v3 trace node
        try:
            self._root_node['trace'] = self._conv_meta_node(self._root_node['metadata'])
        except _ConfigurationParseError as exc:
            _append_error_ctx(exc, 'Metadata object')

        del self._root_node['metadata']

    # Expands the field type aliases found in the metadata node.
    #
    # This method modifies the metadata node.
    #
    # When this method returns:
    #
    # * Any field type alias is replaced with its full field type node
    #   equivalent.
    #
    # * The `type-aliases` property of metadata node is removed.
    def _expand_ft_aliases(self):
        meta_node = self._root_node['metadata']
        ft_aliases_node = meta_node['type-aliases']

        # Expand field type aliases within trace, stream, and event
        # types now.
        try:
            self._resolve_ft_alias_from(ft_aliases_node, meta_node['trace'], 'packet-header-type')
        except _ConfigurationParseError as exc:
            _append_error_ctx(exc, 'Trace type')

        for stream_type_name, stream_type_node in meta_node['streams'].items():
            try:
                self._resolve_ft_alias_from(ft_aliases_node, stream_type_node,
                                            'packet-context-type')
                self._resolve_ft_alias_from(ft_aliases_node, stream_type_node, 'event-header-type')
                self._resolve_ft_alias_from(ft_aliases_node, stream_type_node,
                                            'event-context-type')

                for ev_type_name, ev_type_node in stream_type_node['events'].items():
                    try:
                        self._resolve_ft_alias_from(ft_aliases_node, ev_type_node, 'context-type')
                        self._resolve_ft_alias_from(ft_aliases_node, ev_type_node, 'payload-type')
                    except _ConfigurationParseError as exc:
                        _append_error_ctx(exc, f'Event type `{ev_type_name}`')
            except _ConfigurationParseError as exc:
                _append_error_ctx(exc, f'Stream type `{stream_type_name}`')

        # remove the (now unneeded) `type-aliases` node
        del meta_node['type-aliases']

    # Applies field type inheritance to all field type nodes found in
    # the metadata node.
    #
    # This method modifies the metadata node.
    #
    # When this method returns, no field type node has an `$inherit` or
    # `inherit` property.
    def _apply_fts_inheritance(self):
        meta_node = self._root_node['metadata']
        self._apply_ft_inheritance(meta_node['trace'], 'packet-header-type')

        for stream_type_node in meta_node['streams'].values():
            self._apply_ft_inheritance(stream_type_node, 'packet-context-type')
            self._apply_ft_inheritance(stream_type_node, 'event-header-type')
            self._apply_ft_inheritance(stream_type_node, 'event-context-type')

            for ev_type_node in stream_type_node['events'].values():
                self._apply_ft_inheritance(ev_type_node, 'context-type')
                self._apply_ft_inheritance(ev_type_node, 'payload-type')

    # Calls _expand_ft_aliases() and _apply_fts_inheritance() if the
    # metadata node has a `type-aliases` property.
    def _expand_fts(self):
        # Make sure that the current configuration node is valid
        # considering field types are not expanded yet.
        self._schema_validator.validate(self._root_node,
                                        '2/config/config-pre-field-type-expansion')

        meta_node = self._root_node['metadata']
        ft_aliases_node = meta_node.get('type-aliases')

        if ft_aliases_node is None:
            # If there's no `type-aliases` node, then there's no field
            # type aliases and therefore no possible inheritance.
            return

        # first, expand field type aliases
        self._expand_ft_aliases()

        # next, apply inheritance to create effective field types
        self._apply_fts_inheritance()

    # Processes the inclusions of the event type node `ev_type_node`,
    # returning the effective node.
    def _process_ev_type_node_include(self, ev_type_node):
        # Make sure the event type node is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(ev_type_node, '2/config/event-type-pre-include')

        # process inclusions
        return self._process_node_include(ev_type_node, self._process_ev_type_node_include)

    # Processes the inclusions of the stream type node
    # `stream_type_node`, returning the effective node.
    def _process_stream_type_node_include(self, stream_type_node):
        def process_children_include(stream_type_node):
            prop_name = 'events'

            if prop_name in stream_type_node:
                ev_types_node = stream_type_node[prop_name]

                for key in list(ev_types_node):
                    ev_types_node[key] = self._process_ev_type_node_include(ev_types_node[key])

        # Make sure the stream type node is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(stream_type_node, '2/config/stream-type-pre-include')

        # process inclusions
        return self._process_node_include(stream_type_node, self._process_stream_type_node_include,
                                          process_children_include)

    # Processes the inclusions of the trace type node `trace_type_node`,
    # returning the effective node.
    def _process_trace_type_node_include(self, trace_type_node):
        # Make sure the trace type node is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(trace_type_node, '2/config/trace-type-pre-include')

        # process inclusions
        return self._process_node_include(trace_type_node, self._process_trace_type_node_include)

    # Processes the inclusions of the clock type node `clk_type_node`,
    # returning the effective node.
    def _process_clk_type_node_include(self, clk_type_node):
        # Make sure the clock type node is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(clk_type_node, '2/config/clock-type-pre-include')

        # process inclusions
        return self._process_node_include(clk_type_node, self._process_clk_type_node_include)

    # Processes the inclusions of the metadata node `meta_node`,
    # returning the effective node.
    def _process_meta_node_include(self, meta_node):
        def process_children_include(meta_node):
            prop_name = 'trace'

            if prop_name in meta_node:
                meta_node[prop_name] = self._process_trace_type_node_include(meta_node[prop_name])

            prop_name = 'clocks'

            if prop_name in meta_node:
                clk_types_node = meta_node[prop_name]

                for key in list(clk_types_node):
                    clk_types_node[key] = self._process_clk_type_node_include(clk_types_node[key])

            prop_name = 'streams'

            if prop_name in meta_node:
                stream_types_node = meta_node[prop_name]

                for key in list(stream_types_node):
                    stream_types_node[key] = self._process_stream_type_node_include(stream_types_node[key])

        # Make sure the metadata node is valid for the inclusion
        # processing stage.
        self._schema_validator.validate(meta_node, '2/config/metadata-pre-include')

        # process inclusions
        return self._process_node_include(meta_node, self._process_meta_node_include,
                                          process_children_include)

    # Processes the inclusions of the configuration node, modifying it
    # during the process.
    def _process_config_includes(self):
        # Process inclusions in this order:
        #
        # 1. Clock type node, event type nodes, and trace type nodes
        #    (the order between those is not important).
        #
        # 2. Stream type nodes.
        #
        # 3. Metadata node.
        #
        # This is because:
        #
        # * A metadata node can include clock type nodes, a trace type
        #   node, stream type nodes, and event type nodes (indirectly).
        #
        # * A stream type node can include event type nodes.
        #
        # First, make sure the configuration node itself is valid for
        # the inclusion processing stage.
        self._schema_validator.validate(self._root_node,
                                        '2/config/config-pre-include')

        # Process metadata node inclusions.
        #
        # self._process_meta_node_include() returns a new (or the same)
        # metadata node without any `$include` property in it,
        # recursively.
        prop_name = 'metadata'
        self._root_node[prop_name] = self._process_meta_node_include(self._root_node[prop_name])

    def _parse(self):
        # Make sure the configuration node is minimally valid, that is,
        # it contains a valid `version` property.
        #
        # This step does not validate the whole configuration node yet
        # because we don't have an effective configuration node; we
        # still need to:
        #
        # * Process inclusions.
        # * Expand field types (aliases and inheritance).
        self._schema_validator.validate(self._root_node, '2/config/config-min')

        # process configuration node inclusions
        self._process_config_includes()

        # Expand field type nodes.
        #
        # This process:
        #
        # 1. Replaces field type aliases with "effective" field type
        #    nodes, recursively.
        #
        #    After this step, the `type-aliases` property of the
        #    metadata node is gone.
        #
        # 2. Applies inheritance, following the `$inherit`/`inherit`
        #    properties.
        #
        #    After this step, field type nodes do not contain `$inherit`
        #    or `inherit` properties.
        #
        # This is done blindly, in that the process _doesn't_ validate
        # field type nodes at this point.
        #
        # The reason we must do this here for a barectf 2 configuration,
        # considering that barectf 3 also supports field type node
        # aliases and inheritance, is that we need to find specific
        # packet header and packet context field type member nodes (for
        # example, `stream_id`, `packet_size`, or `timestamp_end`) to
        # set the `$features` properties of barectf 3 trace type and
        # stream type nodes. Those field type nodes can be aliases,
        # contain aliases, or inherit from other nodes.
        self._expand_fts()

        # Validate the whole, (almost) effective configuration node.
        #
        # It's almost effective because the `log-level` property of
        # event type nodes can be log level aliases. Log level aliases
        # are also a feature of a barectf 3 configuration node,
        # therefore this is compatible.
        self._schema_validator.validate(self._root_node, '2/config/config')

        # Transform the current configuration node into a valid v3
        # configuration node.
        self._transform_config_node()

    @property
    def config_node(self):
        return config_parse_common._ConfigNodeV3(self._root_node)
