# The MIT License (MIT)
#
# Copyright (c) 2015-2020 Philippe Proulx <pproulx@efficios.com>
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documeneffective_filetation files (the
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

import pkg_resources
import collections
import jsonschema  # type: ignore
import os.path
import yaml
import copy
import os
from barectf.typing import VersionNumber, _OptStr
from typing import Optional, List, Dict, Any, TextIO, MutableMapping, Union, Set, Iterable, Callable, Tuple
import typing


# The context of a configuration parsing error.
#
# Such a context object has a name and, optionally, a message.
class _ConfigurationParseErrorContext:
    def __init__(self, name: str, message: _OptStr = None):
        self._name = name
        self._msg = message

    @property
    def name(self) -> str:
        return self._name

    @property
    def message(self) -> _OptStr:
        return self._msg


# A configuration parsing error.
#
# Such an error object contains a list of contexts (`context` property).
#
# The first context of this list is the most specific context, while the
# last is the more general.
#
# Use _append_ctx() to append a context to an existing configuration
# parsing error when you catch it before raising it again. You can use
# _append_error_ctx() to do exactly this in a single call.
class _ConfigurationParseError(Exception):
    def __init__(self, init_ctx_obj_name, init_ctx_msg=None):
        super().__init__()
        self._ctx: List[_ConfigurationParseErrorContext] = []
        self._append_ctx(init_ctx_obj_name, init_ctx_msg)

    @property
    def context(self) -> List[_ConfigurationParseErrorContext]:
        return self._ctx

    def _append_ctx(self, name: str, msg: _OptStr = None):
        self._ctx.append(_ConfigurationParseErrorContext(name, msg))

    def __str__(self):
        lines = []

        for ctx in reversed(self._ctx):
            line = f'{ctx.name}:'

            if ctx.message is not None:
                line += f' {ctx.message}'

            lines.append(line)

        return '\n'.join(lines)


# Appends the context having the object name `obj_name` and the
# (optional) message `message` to the `_ConfigurationParseError`
# exception `exc` and then raises `exc` again.
def _append_error_ctx(exc: _ConfigurationParseError, obj_name: str, message: _OptStr = None):
    exc._append_ctx(obj_name, message)
    raise exc


_V3Prefixes = collections.namedtuple('_V3Prefixes', ['identifier', 'file_name'])


# Convers a v2 prefix to v3 prefixes.
def _v3_prefixes_from_v2_prefix(v2_prefix: str) -> _V3Prefixes:
    return _V3Prefixes(v2_prefix, v2_prefix.rstrip('_'))


# This JSON schema reference resolver only serves to detect when it
# needs to resolve a remote URI.
#
# This must never happen in barectf because all our schemas are local;
# it would mean a programming or schema error.
class _RefResolver(jsonschema.RefResolver):
    def resolve_remote(self, uri: str):
        raise RuntimeError(f'Missing local schema with URI `{uri}`')


# Not all static type checkers support type recursion, so let's just use
# `Any` as a map node's value's type.
_MapNode = MutableMapping[str, Any]


# Schema validator which considers all the schemas found in the
# subdirectories `subdirs` (at build time) of the barectf package's
# `schemas` directory.
#
# The only public method is validate() which accepts an instance to
# validate as well as a schema short ID.
class _SchemaValidator:
    def __init__(self, subdirs: Iterable[str]):
        schemas_dir = pkg_resources.resource_filename(__name__, 'schemas')
        self._store: Dict[str, str] = {}

        for subdir in subdirs:
            dir = os.path.join(schemas_dir, subdir)

            for file_name in os.listdir(dir):
                if not file_name.endswith('.yaml'):
                    continue

                with open(os.path.join(dir, file_name)) as f:
                    schema = yaml.load(f, Loader=yaml.SafeLoader)

                assert '$id' in schema
                schema_id = schema['$id']
                assert schema_id not in self._store
                self._store[schema_id] = schema

    @staticmethod
    def _dict_from_ordered_dict(obj):
        if type(obj) is not collections.OrderedDict:
            return obj

        dct = {}

        for k, v in obj.items():
            new_v = v

            if type(v) is collections.OrderedDict:
                new_v = _SchemaValidator._dict_from_ordered_dict(v)
            elif type(v) is list:
                new_v = [_SchemaValidator._dict_from_ordered_dict(elem) for elem in v]

            dct[k] = new_v

        return dct

    def _validate(self, instance: _MapNode, schema_short_id: str):
        # retrieve full schema ID from short ID
        schema_id = f'https://barectf.org/schemas/{schema_short_id}.json'
        assert schema_id in self._store

        # retrieve full schema
        schema = self._store[schema_id]

        # Create a reference resolver for this schema using this
        # validator's schema store.
        resolver = _RefResolver(base_uri=schema_id, referrer=schema,
                                store=self._store)

        # create a JSON schema validator using this reference resolver
        validator = jsonschema.Draft7Validator(schema, resolver=resolver)

        # Validate the instance, converting its
        # `collections.OrderedDict` objects to `dict` objects so as to
        # make any error message easier to read (because
        # validator.validate() below uses str() for error messages, and
        # collections.OrderedDict.__str__() returns a somewhat bulky
        # representation).
        validator.validate(self._dict_from_ordered_dict(instance))

    # Validates `instance` using the schema having the short ID
    # `schema_short_id`.
    #
    # A schema short ID is the part between `schemas/` and `.json` in
    # its URI.
    #
    # Raises a `_ConfigurationParseError` object, hiding any
    # `jsonschema` exception, on validation failure.
    def validate(self, instance: _MapNode, schema_short_id: str):
        try:
            self._validate(instance, schema_short_id)
        except jsonschema.ValidationError as exc:
            # convert to barectf `_ConfigurationParseError` exception
            contexts = ['Configuration object']

            # Each element of the instance's absolute path is either an
            # integer (array element's index) or a string (object
            # property's name).
            for elem in exc.absolute_path:
                if type(elem) is int:
                    ctx = f'Element #{elem + 1}'
                else:
                    ctx = f'`{elem}` property'

                contexts.append(ctx)

            schema_ctx = ''

            if len(exc.context) > 0:
                # According to the documentation of
                # jsonschema.ValidationError.context(), the method
                # returns a
                #
                # > list of errors from the subschemas
                #
                # This contains additional information about the
                # validation failure which can help the user figure out
                # what's wrong exactly.
                #
                # Join each message with `; ` and append this to our
                # configuration parsing error's message.
                msgs = '; '.join([e.message for e in exc.context])
                schema_ctx = f': {msgs}'

            new_exc = _ConfigurationParseError(contexts.pop(),
                                               f'{exc.message}{schema_ctx} (from schema `{schema_short_id}`)')

            for ctx in reversed(contexts):
                new_exc._append_ctx(ctx)

            raise new_exc


# barectf 3 YAML configuration node.
class _ConfigNodeV3:
    def __init__(self, config_node: _MapNode):
        self._config_node = config_node

    @property
    def config_node(self) -> _MapNode:
        return self._config_node


_CONFIG_V3_YAML_TAG = 'tag:barectf.org,2020/3/config'


# Loads the content of the YAML file-like object `file` as a Python
# object and returns it.
#
# If the file's object has the barectf 3 configuration tag, then this
# function returns a `_ConfigNodeV3` object. Otherwise, it returns a
# `collections.OrderedDict` object.
#
# All YAML maps are loaded as `collections.OrderedDict` objects.
def _yaml_load(file: TextIO) -> Union[_ConfigNodeV3, _MapNode]:
    class Loader(yaml.Loader):
        pass

    def config_ctor(loader, node) -> _ConfigNodeV3:
        if not isinstance(node, yaml.MappingNode):
            problem = f'Expecting a map for the tag `{node.tag}`'
            raise yaml.constructor.ConstructorError(problem=problem)

        loader.flatten_mapping(node)
        return _ConfigNodeV3(collections.OrderedDict(loader.construct_pairs(node)))

    def mapping_ctor(loader, node) -> _MapNode:
        loader.flatten_mapping(node)
        return collections.OrderedDict(loader.construct_pairs(node))

    Loader.add_constructor(_CONFIG_V3_YAML_TAG, config_ctor)
    Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping_ctor)

    # YAML -> Python
    try:
        return yaml.load(file, Loader=Loader)
    except (yaml.YAMLError, OSError, IOError) as exc:
        raise _ConfigurationParseError('YAML loader', f'Cannot load file: {exc}')


def _yaml_load_path(path: str) -> Union[_ConfigNodeV3, _MapNode]:
    with open(path) as f:
        return _yaml_load(f)


# Dumps the content of the Python object `obj`
# (`collections.OrderedDict` or `_ConfigNodeV3`) as a YAML string and
# returns it.
def _yaml_dump(node: _MapNode, **kwds) -> str:
    class Dumper(yaml.Dumper):
        pass

    def config_repr(dumper, node):
        return dumper.represent_mapping(_CONFIG_V3_YAML_TAG, node.config_node.items())

    def mapping_repr(dumper, node):
        return dumper.represent_mapping(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                                        node.items())

    Dumper.add_representer(_ConfigNodeV3, config_repr)
    Dumper.add_representer(collections.OrderedDict, mapping_repr)

    # Python -> YAML
    return yaml.dump(node, Dumper=Dumper, version=(1, 2), **kwds)


# A common barectf YAML configuration parser.
#
# This is the base class of any barectf YAML configuration parser. It
# mostly contains helpers.
class _Parser:
    # Builds a base barectf YAML configuration parser to process the
    # configuration node `node` (already loaded from the file-like
    # object `file`).
    #
    # For its _process_node_include() method, the parser considers the
    # package inclusion directory as well as `include_dirs`, and ignores
    # nonexistent inclusion files if `ignore_include_not_found` is
    # `True`.
    def __init__(self, root_file: TextIO, node: Union[_MapNode, _ConfigNodeV3],
                 with_pkg_include_dir: bool, include_dirs: Optional[List[str]],
                 ignore_include_not_found: bool, major_version: VersionNumber):
        self._root_file = root_file
        self._root_node = node
        self._ft_prop_names = [
            # barectf 2.1+
            '$inherit',

            # barectf 2
            'inherit',
            'value-type',
            'element-type',

            # barectf 3
            'element-field-type',
        ]

        if include_dirs is None:
            include_dirs = []

        self._include_dirs = copy.copy(include_dirs)

        if with_pkg_include_dir:
            self._include_dirs.append(pkg_resources.resource_filename(__name__, f'include/{major_version}'))

        self._ignore_include_not_found = ignore_include_not_found
        self._include_stack: List[str] = []
        self._resolved_ft_aliases: Set[str] = set()
        self._schema_validator = _SchemaValidator({'config/common', f'config/{major_version}'})
        self._major_version = major_version

    @property
    def root_node(self):
        return self._root_node

    @property
    def _struct_ft_node_members_prop_name(self) -> str:
        if self._major_version == 2:
            return 'fields'
        else:
            return 'members'

    # Returns the last included file name from the parser's inclusion
    # file name stack, or `N/A` if the root file does not have an
    # associated path under the `name` property.
    def _get_last_include_file(self) -> str:
        if self._include_stack:
            return self._include_stack[-1]

        if hasattr(self._root_file, 'name'):
            return typing.cast(str, self._root_file.name)

        return 'N/A'

    # Loads the inclusion file having the path `yaml_path` and returns
    # its content as a `collections.OrderedDict` object.
    def _load_include(self, yaml_path) -> Optional[_MapNode]:
        for inc_dir in self._include_dirs:
            # Current inclusion dir + file name path.
            #
            # Note: os.path.join() only takes the last argument if it's
            # absolute.
            inc_path = os.path.join(inc_dir, yaml_path)

            # real path (symbolic links resolved)
            real_path = os.path.realpath(inc_path)

            # normalized path (weird stuff removed!)
            norm_path = os.path.normpath(real_path)

            if not os.path.isfile(norm_path):
                # file doesn't exist: skip
                continue

            if norm_path in self._include_stack:
                base_path = self._get_last_include_file()
                raise _ConfigurationParseError(f'File `{base_path}`',
                                               f'Cannot recursively include file `{norm_path}`')

            self._include_stack.append(norm_path)

            # load raw content
            return typing.cast(_MapNode, _yaml_load_path(norm_path))

        if not self._ignore_include_not_found:
            base_path = self._get_last_include_file()
            raise _ConfigurationParseError(f'File `{base_path}`',
                                           f'Cannot include file `{yaml_path}`: file not found in inclusion directories')

        return None

    # Returns a list of all the inclusion file paths as found in the
    # inclusion node `include_node`.
    def _get_include_paths(self, include_node: _MapNode) -> List[str]:
        if include_node is None:
            # none
            return []

        if type(include_node) is str:
            # wrap as array
            return [typing.cast(str, include_node)]

        # already an array
        assert type(include_node) is list
        return typing.cast(List[str], include_node)

    # Updates the node `base_node` with an overlay node `overlay_node`.
    #
    # Both the inclusion and field type node inheritance features use
    # this update mechanism.
    def _update_node(self, base_node: _MapNode, overlay_node: _MapNode):
        # see the comment about the `members` property below
        def update_members_node(base_value: List[Any], olay_value: List[Any]):
            for olay_item in olay_value:
                # assume we append `olay_item` to `base_value` initially
                append_olay_item = True

                if type(olay_item) is collections.OrderedDict:
                    # overlay item is an object
                    if len(olay_item) == 1:
                        # overlay object item contains a single property
                        olay_name = list(olay_item)[0]

                        # find corresponding base item
                        for base_item in base_value:
                            if type(base_item) is collections.OrderedDict:
                                if len(olay_item) == 1:
                                    base_name = list(base_item)[0]

                                    if olay_name == base_name:
                                        # Names match: update with usual
                                        # strategy.
                                        self._update_node(base_item, olay_item)

                                        # Do _not_ append `olay_item` to
                                        # `base_value`: we just updated
                                        # `base_item`.
                                        append_olay_item = False
                                        break

                if append_olay_item:
                    base_value.append(copy.deepcopy(olay_item))

        for olay_key, olay_value in overlay_node.items():
            if olay_key in base_node:
                base_value = base_node[olay_key]

                if type(olay_value) is collections.OrderedDict and type(base_value) is collections.OrderedDict:
                    # merge both objects
                    self._update_node(base_value, olay_value)
                elif type(olay_value) is list and type(base_value) is list:
                    if olay_key == 'members' and self._major_version == 3:
                        # This is a "temporary" hack.
                        #
                        # In barectf 2, a structure field type node
                        # looks like this:
                        #
                        #     class: struct
                        #     fields:
                        #       hello: uint8
                        #       world: string
                        #
                        # Having an overlay such as
                        #
                        #     fields:
                        #       hello: float
                        #
                        # will result in
                        #
                        #     class: struct
                        #     fields:
                        #       hello: float
                        #       world: string
                        #
                        # because the `fields` property is a map.
                        #
                        # In barectf 3, this is fixed (a YAML map is not
                        # ordered), so that the same initial structure
                        # field type node looks like this:
                        #
                        #     class: struct
                        #     members:
                        #       - hello: uint8
                        #       - world:
                        #           field-type:
                        #             class: str
                        #
                        # Although the `members` property is
                        # syntaxically an array, it's semantically an
                        # ordered map, where an entry's key is the array
                        # item's map's first key (like YAML's `!!omap`).
                        #
                        # Having an overlay such as
                        #
                        #     members:
                        #       - hello: float
                        #
                        # would result in
                        #
                        #     class: struct
                        #     members:
                        #       - hello: uint8
                        #       - world:
                        #           field-type:
                        #             class: str
                        #       - hello: float
                        #
                        # with the naive strategy, while what we really
                        # want is:
                        #
                        #     class: struct
                        #     members:
                        #       - hello: float
                        #       - world:
                        #           field-type:
                        #             class: str
                        #
                        # As of this version of barectf, the _only_
                        # property with a list value which acts as an
                        # ordered map is named `members`. This is why we
                        # can only check the value of `olay_key`,
                        # whatever our context.
                        #
                        # update_members_node() attempts to perform
                        # this below. For a given item of `olay_value`,
                        # if
                        #
                        # * It's not an object.
                        #
                        # * It contains more than one property.
                        #
                        # * Its single property's name does not match
                        #   the name of the single property of any
                        #   object item of `base_value`.
                        #
                        # then we append the item to `base_value` as
                        # usual.
                        update_members_node(base_value, olay_value)
                    else:
                        # append extension array items to base items
                        base_value += copy.deepcopy(olay_value)
                else:
                    # fall back to replacing base property
                    base_node[olay_key] = copy.deepcopy(olay_value)
            else:
                # set base property from overlay property
                base_node[olay_key] = copy.deepcopy(olay_value)

    # Processes inclusions using `last_overlay_node` as the last overlay
    # node to use to "patch" the node.
    #
    # If `last_overlay_node` contains an `$include` property, then this
    # method patches the current base node (initially empty) in order
    # using the content of the inclusion files (recursively).
    #
    # At the end, this method removes the `$include` property of
    # `last_overlay_node` and then patches the current base node with
    # its other properties before returning the result (always a deep
    # copy).
    def _process_node_include(self, last_overlay_node: _MapNode,
                              process_base_include_cb: Callable[[_MapNode], _MapNode],
                              process_children_include_cb: Optional[Callable[[_MapNode], None]] = None) -> _MapNode:
        # process children inclusions first
        if process_children_include_cb is not None:
            process_children_include_cb(last_overlay_node)

        incl_prop_name = '$include'

        if incl_prop_name in last_overlay_node:
            include_node = last_overlay_node[incl_prop_name]
        else:
            # no inclusions!
            return last_overlay_node

        include_paths = self._get_include_paths(include_node)
        cur_base_path = self._get_last_include_file()
        base_node = None

        # keep the inclusion paths and remove the `$include` property
        include_paths = copy.deepcopy(include_paths)
        del last_overlay_node[incl_prop_name]

        for include_path in include_paths:
            # load raw YAML from included file
            overlay_node = self._load_include(include_path)

            if overlay_node is None:
                # Cannot find inclusion file, but we're ignoring those
                # errors, otherwise _load_include() itself raises a
                # config error.
                continue

            # recursively process inclusions
            try:
                overlay_node = process_base_include_cb(overlay_node)
            except _ConfigurationParseError as exc:
                _append_error_ctx(exc, f'File `{cur_base_path}`')

            # pop inclusion stack now that we're done including
            del self._include_stack[-1]

            # At this point, `base_node` is fully resolved (does not
            # contain any `$include` property).
            if base_node is None:
                base_node = overlay_node
            else:
                self._update_node(base_node, overlay_node)

        # Finally, update the latest base node with our last overlay
        # node.
        if base_node is None:
            # Nothing was included, which is possible when we're
            # ignoring inclusion errors.
            return last_overlay_node

        self._update_node(base_node, last_overlay_node)
        return base_node

    # Generates pairs of member node and field type node property name
    # (in the member node) for the structure field type node's members
    # node `node`.
    def _struct_ft_member_fts_iter(self,
                                   node: Union[List[_MapNode], _MapNode]) -> Iterable[Tuple[_MapNode, str]]:
        if type(node) is list:
            # barectf 3
            assert self._major_version == 3
            node = typing.cast(List[_MapNode], node)

            for member_node in node:
                assert type(member_node) is collections.OrderedDict
                member_node = typing.cast(_MapNode, member_node)
                name, val = list(member_node.items())[0]

                if type(val) is collections.OrderedDict:
                    member_node = val
                    name = 'field-type'

                yield member_node, name
        else:
            # barectf 2
            assert self._major_version == 2
            assert type(node) is collections.OrderedDict
            node = typing.cast(_MapNode, node)

            for name in node:
                yield node, name

    # Resolves the field type alias `key` in the node `parent_node`, as
    # well as any nested field type aliases, using the aliases of the
    # `ft_aliases_node` node.
    #
    # If `key` is not in `parent_node`, this method returns.
    #
    # This method can modify `ft_aliases_node` and `parent_node[key]`.
    #
    # `ctx_obj_name` is the context's object name when this method
    # raises a `_ConfigurationParseError` exception.
    def _resolve_ft_alias(self, ft_aliases_node: _MapNode, parent_node: _MapNode, key: str,
                          ctx_obj_name: str, alias_set: Optional[Set[str]] = None):
        if key not in parent_node:
            return

        node = parent_node[key]

        if node is None:
            # some nodes can be null to use their default value
            return

        # This set holds all the field type aliases to be expanded,
        # recursively. This is used to detect cycles.
        if alias_set is None:
            alias_set = set()

        if type(node) is str:
            alias = node

            # Make sure this alias names an existing field type node, at
            # least.
            if alias not in ft_aliases_node:
                raise _ConfigurationParseError(ctx_obj_name,
                                               f'Field type alias `{alias}` does not exist')

            if alias not in self._resolved_ft_aliases:
                # Only check for a field type alias cycle when we didn't
                # resolve the alias yet, as a given node can refer to
                # the same field type alias more than once.
                if alias in alias_set:
                    msg = f'Cycle detected during the `{alias}` field type alias resolution'
                    raise _ConfigurationParseError(ctx_obj_name, msg)

                # Resolve it.
                #
                # Add `alias` to the set of encountered field type
                # aliases before calling self._resolve_ft_alias() to
                # detect cycles.
                alias_set.add(alias)
                self._resolve_ft_alias(ft_aliases_node, ft_aliases_node, alias, ctx_obj_name,
                                       alias_set)
                self._resolved_ft_aliases.add(alias)

            # replace alias with field type node copy
            parent_node[key] = copy.deepcopy(ft_aliases_node[alias])
            return

        # resolve nested field type aliases
        for pkey in self._ft_prop_names:
            self._resolve_ft_alias(ft_aliases_node, node, pkey, ctx_obj_name, alias_set)

        # Resolve field type aliases of structure field type node member
        # nodes.
        pkey = self._struct_ft_node_members_prop_name

        if pkey in node:
            for member_node, ft_prop_name in self._struct_ft_member_fts_iter(node[pkey]):
                self._resolve_ft_alias(ft_aliases_node, member_node, ft_prop_name,
                                       ctx_obj_name, alias_set)

    # Like _resolve_ft_alias(), but builds a context object name for any
    # `ctx_obj_name` exception.
    def _resolve_ft_alias_from(self, ft_aliases_node: _MapNode, parent_node: _MapNode, key: str):
        self._resolve_ft_alias(ft_aliases_node, parent_node, key, f'`{key}` property')

    # Applies field type node inheritance to the property `key` of
    # `parent_node`.
    #
    # `parent_node[key]`, if it exists, must not contain any field type
    # alias (all field type objects are complete).
    #
    # This method can modify `parent[key]`.
    #
    # When this method returns, no field type node has an `$inherit` or
    # `inherit` property.
    def _apply_ft_inheritance(self, parent_node: _MapNode, key: str):
        if key not in parent_node:
            return

        node = parent_node[key]

        if node is None:
            return

        # process children first
        for pkey in self._ft_prop_names:
            self._apply_ft_inheritance(node, pkey)

        # Process the field types of structure field type node member
        # nodes.
        pkey = self._struct_ft_node_members_prop_name

        if pkey in node:
            for member_node, ft_prop_name in self._struct_ft_member_fts_iter(node[pkey]):
                self._apply_ft_inheritance(member_node, ft_prop_name)

        # apply inheritance for this node
        if 'inherit' in node:
            # barectf 2.1: `inherit` property was renamed to `$inherit`
            assert '$inherit' not in node
            node['$inherit'] = node['inherit']
            del node['inherit']

        inherit_key = '$inherit'

        if inherit_key in node:
            assert type(node[inherit_key]) is collections.OrderedDict

            # apply inheritance below
            self._apply_ft_inheritance(node, inherit_key)

            # `node` is an overlay on the `$inherit` node
            base_node = node[inherit_key]
            del node[inherit_key]
            self._update_node(base_node, node)

            # set updated base node as this node
            parent_node[key] = base_node
