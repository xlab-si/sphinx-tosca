# Copyright (C) 2016 XLAB d.o.o.
#
# This file is part of sphinx-tosca.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, * WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. * See the
# License for the specific language governing permissions and * limitations
# under the License.

import collections

from docutils import nodes
from docutils.parsers.rst import Directive

from sphinx import addnodes
from sphinx.domains import Domain, ObjType
from sphinx.roles import XRefRole
from sphinx.util.nodes import make_refnode


SECTION_MAPPING = collections.OrderedDict((
    ("parents", "Parents"),
    ("property", "Properties"),
    ("attribute", "Attributes"),
    ("relationship", "Relationships"),
))

ToscaObject = collections.namedtuple("ToscaObject", ("doc", "typ"))


def _split_content(node):
    content = addnodes.desc_content()
    fields = []

    for child in node:
        if isinstance(child, nodes.field_list):
            fields.extend([f for f in child])
        else:
            content.append(child)
    return content, fields


def _group_fields(fields):
    content = collections.defaultdict(nodes.field_list)
    for name, body in fields:
        field_parts = name.astext().split()
        if len(field_parts) > 1:
            content[field_parts[0]].append(
                nodes.field("", nodes.field_name(text=field_parts[1]), body)
            )
        else:
            content[field_parts[0]] = body

    result = nodes.field_list()
    for section_id, section_label in SECTION_MAPPING.items():
        items = content[section_id]
        if len(items) > 0:
            if isinstance(items, nodes.field_body):
                body = items
            else:
                body = nodes.field_body("", items)
            result.append(
                nodes.field("", nodes.field_name(text=section_label), body)
            )

    return result


class ToscaNodeType(Directive):

    has_content = True
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = False

    def run(self):
        name = self.arguments[0]
        dname = addnodes.desc_name(name, name)

        dcontent = addnodes.desc_content()
        self.state.nested_parse(self.content, self.content_offset, dcontent)

        dcontent, fields = _split_content(dcontent)
        dcontent.append(_group_fields(fields))

        signature = addnodes.desc_signature(name, "")
        signature.append(dname)
        signature.append(dcontent)

        if ":" in self.name:
            domain, objtype = self.name.split(":", 1)
        else:
            domain, objtype = "", self.name

        description = addnodes.desc()
        description["domain"] = domain
        description["objtype"] = objtype
        description.append(signature)

        if name not in self.state.document.ids:
            signature["names"].append(name)
            signature["ids"].append(name)
            signature["first"] = True
            self.state.document.note_explicit_target(signature)

            env = self.state.document.settings.env
            objects = env.domaindata["tosca"]["objects"]
            if name in objects:
                msg = "duplicate TOSCA type {}, other in {}"
                self.state_machine.reporter.warning(msg.format(
                    name, env.doc2path(objects[name].doc)
                ), line=self.lineno)
            objects[name] = ToscaObject(env.docname, objtype)

        indexnode = addnodes.index(entries=[("single", name, name, "", None)])

        return [indexnode, description]


class ToscaXRefRole(XRefRole):
    """ Cross-link TOSCA role. """

    def __init__(self, object_type, **kwargs):
        super(ToscaXRefRole, self).__init__(self, **kwargs)
        self.object_type = object_type

    def process_link(self, env, refnode, has_explicit_title, title, target):
        return target, target


class ToscaDomain(Domain):
    """ TOSCA domain. """

    name = "tosca"
    label = "TOSCA"

    object_types = {
        "node_type": ObjType("node_type", "node_type"),
    }

    directives = {
        "node_type": ToscaNodeType,
    }

    roles = {
        "node_type": ToscaXRefRole("type"),
    }

    initial_data = {
        "objects": {},
    }

    def clear_doc(self, docname):
        self.data["objects"] = {
            k: v for k, v in self.data["objects"].items() if v.doc != docname
        }

    def merge_domaindata(self, docnames, otherdata):
        for name, obj in otherdata["objects"].items():
            if obj.doc in docnames:
                self.data['objects'][name] = obj

    def resolve_xref(self, env, fromdoc, builder, typ, target, node, cont):
        obj = self.data["objects"].get(target)
        if obj is None:
            return None
        return make_refnode(builder, fromdoc, obj.doc, target, cont, target)

    def resolve_any_xref(self, env, fromdoc, builder, target, node, cont):
        obj = self.data["objects"].get(target)
        if obj is None:
            return None
        return [(
            self.name + ':' + self.role_for_objtype(obj.typ),
            make_refnode(builder, fromdoc, obj.doc, target, cont, target)
        )]

    def get_objects(self):
        for name, (doc, typ) in self.data['objects'].items():
            yield (name, name, typ, doc, name, 1)
