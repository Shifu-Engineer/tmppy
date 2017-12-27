#  Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from _py2tmp import ir0, transform_ir0
import networkx as nx
from typing import Dict, Iterable

class ExprSimplifyingTransformation(transform_ir0.Transformation):
    def transform_expr(self, expr: ir0.Expr, writer: transform_ir0.Writer, split_nontrivial_exprs=True) -> ir0.Expr:
        if split_nontrivial_exprs and not isinstance(expr, ir0.TypeLiteral):
            expr = super().transform_expr(expr, writer)
            var = writer.new_constant_or_typedef(expr)
            return var
        else:
            return expr

    def transform_constant_def(self, constant_def: ir0.ConstantDef, writer: transform_ir0.Writer):
        writer.write(ir0.ConstantDef(name=constant_def.name,
                                     expr=self.transform_expr(constant_def.expr, writer, split_nontrivial_exprs=False)))

    def transform_typedef(self, typedef: ir0.Typedef, writer: transform_ir0.Writer):
        writer.write(ir0.Typedef(name=typedef.name,
                                 expr=self.transform_expr(typedef.expr, writer, split_nontrivial_exprs=False)))

def normalize_template_defn(template_defn: ir0.TemplateDefn, identifier_generator: Iterable[str]):
    '''Converts template_defn to an equivalent TemplateDefn where all expressions contain 0 or 1 operations.

    Unlike other constants/typedefs, the exprs that initialize "result" and "error" will always have 0 operations.
    '''
    writer = transform_ir0.ToplevelWriter(identifier_generator)
    ExprSimplifyingTransformation().transform_template_defn(template_defn, writer)
    [new_template_defn] = writer.elems

    return new_template_defn

def perform_local_optimizations_on_template_defn(template_defn: ir0.TemplateDefn,
                                                 identifier_generator: Iterable[str],
                                                 inline_template_instantiations_with_multiple_references: bool):
    template_defn = normalize_template_defn(template_defn, identifier_generator)

    return template_defn

def optimize_header(header: ir0.Header, identifier_generator: Iterable[str]):
    template_dependency_graph = nx.DiGraph()

    new_template_defns = {elem.name: elem
                          for elem in header.content
                          if isinstance(elem, ir0.TemplateDefn)} # type: Dict[str, ir0.TemplateDefn]

    for elem in header.content:
        if isinstance(elem, ir0.TemplateDefn):
            template_dependency_graph.add_node(elem.name)

            for identifier in elem.get_referenced_identifiers():
                if identifier in new_template_defns.keys():
                    template_dependency_graph.add_edge(elem.name, identifier)

    condensed_graph = nx.condensation(template_dependency_graph)
    assert isinstance(condensed_graph, nx.DiGraph)

    template_dependency_graph_transitive_closure = nx.transitive_closure(template_dependency_graph)
    assert isinstance(template_dependency_graph_transitive_closure, nx.DiGraph)

    for connected_component_index in nx.topological_sort(condensed_graph, reverse=True):
        connected_component = condensed_graph.node[connected_component_index]['members']
        for node in connected_component:
            template_defn = new_template_defns[node]

            template_defn = perform_local_optimizations_on_template_defn(template_defn,
                                                                         identifier_generator,
                                                                         inline_template_instantiations_with_multiple_references=False)
            new_template_defns[node] = template_defn

    new_elems = []
    for elem in header.content:
        if isinstance(elem, ir0.TemplateDefn):
            new_elems.append(new_template_defns[elem.name])
        else:
            new_elems.append(elem)

    return ir0.Header(new_elems)
