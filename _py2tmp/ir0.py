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
import itertools
from typing import List, Set, Optional, Iterable, Union, Dict, Hashable, Tuple
from enum import Enum
import re
from _py2tmp import utils

class ExprKind(Enum):
    BOOL = 1
    INT64 = 2
    TYPE = 3
    TEMPLATE = 4
    VARIADIC_TYPE = 5

class TemplateBodyElementOrExpr:
    def get_referenced_identifiers(self) -> Iterable[str]:
        for expr in self.get_transitive_subexpressions():
            for identifier in expr.get_local_referenced_identifiers():
                yield identifier

    # Returns all transitive subexpressions
    def get_transitive_subexpressions(self):
        if isinstance(self, Expr):
            yield self
        for elem in self.get_direct_subelements():
            for subexpr in elem.get_transitive_subexpressions():
                yield subexpr
        for expr in self.get_direct_subexpressions():
            for subexpr in expr.get_transitive_subexpressions():
                yield subexpr

    def get_direct_subelements(self) -> Iterable['TemplateBodyElement']: ...

    def get_direct_subexpressions(self) -> Iterable['Expr']: ...

class ExprType(utils.ValueType):
    def __init__(self, kind: ExprKind):
        self.kind = kind

class BoolType(ExprType):
    def __init__(self):
        super().__init__(kind=ExprKind.BOOL)

class Int64Type(ExprType):
    def __init__(self):
        super().__init__(kind=ExprKind.INT64)

class TypeType(ExprType):
    def __init__(self):
        super().__init__(kind=ExprKind.TYPE)

class TemplateType(ExprType):
    def __init__(self, argtypes: List[ExprType]):
        super().__init__(kind=ExprKind.TEMPLATE)
        self.argtypes = tuple(argtypes)

class VariadicType(ExprType):
    def __init__(self):
        super().__init__(kind=ExprKind.VARIADIC_TYPE)

class Expr(utils.ValueType, TemplateBodyElementOrExpr):
    def __init__(self, type: ExprType):
        self.type = type

    def references_any_of(self, variables: Set[str]):
        return any(isinstance(expr, AtomicTypeLiteral) and expr.cpp_type in variables
                   for expr in self.get_transitive_subexpressions())

    def get_free_vars(self) -> Iterable['AtomicTypeLiteral']:
        for expr in self.get_transitive_subexpressions():
            if isinstance(expr, AtomicTypeLiteral) and expr.is_local:
                yield expr

    def get_local_referenced_identifiers(self) -> Iterable[str]:
        if isinstance(self, AtomicTypeLiteral):
            yield self.cpp_type

    def get_direct_subelements(self):
        return []

    def is_same_expr_excluding_subexpressions(self, other: 'Expr') -> bool: ...

    def copy_with_subexpressions(self, new_subexpressions: List['Expr']): ...

class TemplateBodyElement(TemplateBodyElementOrExpr):
    pass

class StaticAssert(TemplateBodyElement):
    def __init__(self, expr: Expr, message: str):
        assert isinstance(expr.type, BoolType)
        self.expr = expr
        self.message = message

    def get_direct_subelements(self):
        return []

    def get_direct_subexpressions(self):
        yield self.expr

class ConstantDef(TemplateBodyElement):
    def __init__(self, name: str, expr: Expr):
        assert isinstance(expr.type, (BoolType, Int64Type))
        self.name = name
        self.expr = expr

    def get_direct_subelements(self):
        return []

    def get_direct_subexpressions(self):
        yield self.expr

class Typedef(TemplateBodyElement):
    def __init__(self, name: str, expr: Expr):
        assert isinstance(expr.type, (TypeType, TemplateType))
        self.name = name
        self.expr = expr

    def get_direct_subelements(self):
        return []

    def get_direct_subexpressions(self):
        yield self.expr

class TemplateArgDecl:
    def __init__(self, type: ExprType, name: str = ''):
        self.type = type
        self.name = name

_non_identifier_char_pattern = re.compile('[^a-zA-Z0-9_]+')

class TemplateSpecialization:
    def __init__(self,
                 args: List[TemplateArgDecl],
                 patterns: 'Optional[List[Expr]]',
                 body: List[TemplateBodyElement]):
        self.args = tuple(args)

        self.patterns = tuple(patterns) if patterns is not None else None
        self.body = tuple(body)

class TemplateDefn(TemplateBodyElement):
    def __init__(self,
                 args: List[TemplateArgDecl],
                 main_definition: Optional[TemplateSpecialization],
                 specializations: List[TemplateSpecialization],
                 name: str,
                 description: str,
                 result_element_names: List[str]):
        assert main_definition or specializations
        assert not main_definition or main_definition.patterns is None
        assert '\n' not in description
        self.name = name
        self.args = tuple(args)
        self.main_definition = main_definition
        self.specializations = tuple(specializations)
        self.description = description
        self.result_element_names = tuple(sorted(result_element_names))

    def get_direct_subelements(self):
        for specialization in itertools.chain((self.main_definition,), self.specializations):
            if specialization:
                for elem in specialization.body:
                    yield elem

    def get_direct_subexpressions(self):
        for specialization in itertools.chain((self.main_definition,), self.specializations):
            if specialization and specialization.patterns:
                for expr in specialization.patterns:
                    yield expr

class Literal(Expr):
    def __init__(self, value: Union[bool, int]):
        if isinstance(value, bool):
            type = BoolType()
        elif isinstance(value, int):
            type = Int64Type()
        else:
            raise NotImplementedError('Unexpected value: ' + repr(value))
        super().__init__(type)
        self.value = value

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, Literal) and self.value == other.value

    def get_direct_subexpressions(self):
        return []

    def copy_with_subexpressions(self, new_subexpressions: List[Expr]):
        assert not new_subexpressions
        return self

class AtomicTypeLiteral(Expr):
    def __init__(self,
                 cpp_type: str,
                 is_local: bool,
                 is_metafunction_that_may_return_error: bool,
                 type: ExprType):
        assert not (is_metafunction_that_may_return_error and not isinstance(type, TemplateType))
        super().__init__(type=type)
        self.cpp_type = cpp_type
        self.is_local = is_local
        self.type = type
        self.is_metafunction_that_may_return_error = is_metafunction_that_may_return_error

    def get_direct_free_vars(self):
        if self.is_local:
            yield self

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, AtomicTypeLiteral) and self.__dict__ == other.__dict__

    def get_direct_subexpressions(self):
        return []

    def copy_with_subexpressions(self, new_subexpressions: List[Expr]):
        assert not new_subexpressions
        return self

    @staticmethod
    def for_local(cpp_type: str,
                  type: ExprType):
        return AtomicTypeLiteral(cpp_type=cpp_type,
                                 is_local=True,
                                 type=type,
                                 is_metafunction_that_may_return_error=(type.kind == ExprKind.TEMPLATE))

    @staticmethod
    def for_nonlocal(cpp_type: str,
                     type: ExprType,
                     is_metafunction_that_may_return_error: bool):
        return AtomicTypeLiteral(cpp_type=cpp_type,
                                 is_local=False,
                                 type=type,
                                 is_metafunction_that_may_return_error=is_metafunction_that_may_return_error)

    @staticmethod
    def for_nonlocal_type(cpp_type: str):
        return AtomicTypeLiteral.for_nonlocal(cpp_type=cpp_type,
                                              type=TypeType(),
                                              is_metafunction_that_may_return_error=False)

    @staticmethod
    def for_nonlocal_template(cpp_type: str,
                              arg_types: List[ExprType],
                              is_metafunction_that_may_return_error: bool):
        return AtomicTypeLiteral.for_nonlocal(cpp_type=cpp_type,
                                              type=TemplateType(arg_types),
                                              is_metafunction_that_may_return_error=is_metafunction_that_may_return_error)

    @staticmethod
    def from_nonlocal_template_defn(template_defn: TemplateDefn,
                                    is_metafunction_that_may_return_error: bool):
        return AtomicTypeLiteral.for_nonlocal_template(cpp_type=template_defn.name,
                                                       arg_types=[arg.type for arg in template_defn.args],
                                                       is_metafunction_that_may_return_error=is_metafunction_that_may_return_error)

class PointerTypeExpr(Expr):
    def __init__(self, type_expr: Expr):
        super().__init__(type=TypeType())
        assert type_expr.type == TypeType()
        self.type_expr = type_expr

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, PointerTypeExpr)

    def get_direct_subexpressions(self):
        yield self.type_expr

    def copy_with_subexpressions(self, new_subexpressions: List[Expr]):
        [new_type_expr] = new_subexpressions
        return PointerTypeExpr(new_type_expr)

class ReferenceTypeExpr(Expr):
    def __init__(self, type_expr: Expr):
        super().__init__(type=TypeType())
        assert type_expr.type == TypeType()
        self.type_expr = type_expr

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, ReferenceTypeExpr)

    def get_direct_subexpressions(self):
        yield self.type_expr

    def copy_with_subexpressions(self, new_subexpressions: List[Expr]):
        [new_type_expr] = new_subexpressions
        return ReferenceTypeExpr(new_type_expr)

class RvalueReferenceTypeExpr(Expr):
    def __init__(self, type_expr: Expr):
        super().__init__(type=TypeType())
        assert type_expr.type == TypeType()
        self.type_expr = type_expr

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, RvalueReferenceTypeExpr)

    def get_direct_subexpressions(self):
        yield self.type_expr

    def copy_with_subexpressions(self, new_subexpressions: List[Expr]):
        [new_type_expr] = new_subexpressions
        return RvalueReferenceTypeExpr(new_type_expr)

class ConstTypeExpr(Expr):
    def __init__(self, type_expr: Expr):
        super().__init__(type=TypeType())
        assert type_expr.type == TypeType()
        self.type_expr = type_expr

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, ConstTypeExpr)

    def get_direct_subexpressions(self):
        yield self.type_expr
    
    def copy_with_subexpressions(self, new_subexpressions: List[Expr]):
        [new_type_expr] = new_subexpressions
        return ConstTypeExpr(new_type_expr)

class ArrayTypeExpr(Expr):
    def __init__(self, type_expr: Expr):
        super().__init__(type=TypeType())
        assert type_expr.type == TypeType()
        self.type_expr = type_expr

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, ArrayTypeExpr)

    def get_direct_subexpressions(self):
        yield self.type_expr
    
    def copy_with_subexpressions(self, new_subexpressions: List[Expr]):
        [new_type_expr] = new_subexpressions
        return ArrayTypeExpr(new_type_expr)

class FunctionTypeExpr(Expr):
    def __init__(self, return_type_expr: Expr, arg_exprs: List[Expr]):
        assert return_type_expr.type == TypeType(), return_type_expr.type.__class__.__name__

        super().__init__(type=TypeType())
        self.return_type_expr = return_type_expr
        self.arg_exprs = tuple(arg_exprs)

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, FunctionTypeExpr)

    def get_direct_subexpressions(self):
        yield self.return_type_expr
        for expr in self.arg_exprs:
            yield expr

    def copy_with_subexpressions(self, new_subexpressions: List['Expr']):
        [new_return_type_expr, *new_arg_exprs] = new_subexpressions
        return FunctionTypeExpr(new_return_type_expr, new_arg_exprs)

class UnaryExpr(Expr):
    def __init__(self, expr: Expr, result_type: ExprType):
        super().__init__(type=result_type)
        self.expr = expr

    def get_direct_subexpressions(self):
        yield self.expr

class BinaryExpr(Expr):
    def __init__(self, lhs: Expr, rhs: Expr, result_type: ExprType):
        super().__init__(type=result_type)
        self.lhs = lhs
        self.rhs = rhs

    def get_direct_subexpressions(self):
        yield self.lhs
        yield self.rhs

class ComparisonExpr(BinaryExpr):
    def __init__(self, lhs: Expr, rhs: Expr, op: str):
        assert lhs.type == rhs.type
        if isinstance(lhs.type, BoolType):
            assert op == '=='
        elif isinstance(lhs.type, Int64Type):
            assert op in ('==', '!=', '<', '>', '<=', '>=')
        else:
            raise NotImplementedError('Unexpected type: %s' % str(lhs.type))
        super().__init__(lhs, rhs, result_type=BoolType())
        self.op = op

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, ComparisonExpr) and self.op == other.op

    def copy_with_subexpressions(self, new_subexpressions: List['Expr']):
        [lhs, rhs] = new_subexpressions
        return ComparisonExpr(lhs, rhs, self.op)

class Int64BinaryOpExpr(BinaryExpr):
    def __init__(self, lhs: Expr, rhs: Expr, op: str):
        super().__init__(lhs, rhs, result_type=Int64Type())
        assert isinstance(lhs.type, Int64Type)
        assert isinstance(rhs.type, Int64Type)
        assert op in ('+', '-', '*', '/', '%')
        self.op = op

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, Int64BinaryOpExpr) and self.op == other.op

    def copy_with_subexpressions(self, new_subexpressions: List[Expr]):
        [lhs, rhs] = new_subexpressions
        return Int64BinaryOpExpr(lhs, rhs, self.op)

class TemplateInstantiation(Expr):
    def __init__(self,
                 template_expr: Expr,
                 args: List[Expr],
                 instantiation_might_trigger_static_asserts: bool):
        assert isinstance(template_expr.type, TemplateType), str(template_expr.type)

        if any(type.kind == ExprKind.VARIADIC_TYPE
               for types in (template_expr.type.argtypes, (arg.type for arg in args))
               for type in types):
            # In this case it's fine if the two lists "don't match up"
            pass
        else:
            assert len(template_expr.type.argtypes) == len(args), 'template_expr.type.argtypes: %s, args: %s' % (template_expr.type.argtypes, args)
            for arg_type, arg_expr in zip(template_expr.type.argtypes, args):
                assert arg_expr.type == arg_type, '%s vs %s' % (str(arg_expr.type), str(arg_type))

        super().__init__(type=TypeType())
        self.template_expr = template_expr
        self.args = tuple(args)
        self.instantiation_might_trigger_static_asserts = instantiation_might_trigger_static_asserts

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, TemplateInstantiation) and self.instantiation_might_trigger_static_asserts == other.instantiation_might_trigger_static_asserts

    def get_direct_subexpressions(self):
        yield self.template_expr
        for expr in self.args:
            yield expr

    def copy_with_subexpressions(self, new_subexpressions: List[Expr]):
        [template_expr, *args] = new_subexpressions
        return TemplateInstantiation(template_expr, args, self.instantiation_might_trigger_static_asserts)

class ClassMemberAccess(UnaryExpr):
    def __init__(self, class_type_expr: Expr, member_name: str, member_type: ExprType):
        super().__init__(class_type_expr, result_type=member_type)
        self.member_name = member_name

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, ClassMemberAccess) and self.member_name == other.member_name

    def copy_with_subexpressions(self, new_subexpressions: List[Expr]):
        assert not new_subexpressions
        return self

class NotExpr(UnaryExpr):
    def __init__(self, expr: Expr):
        super().__init__(expr, result_type=BoolType())

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, NotExpr)

    def copy_with_subexpressions(self, new_subexpressions: List[Expr]):
        [expr] = new_subexpressions
        return NotExpr(expr)

class UnaryMinusExpr(UnaryExpr):
    def __init__(self, expr: Expr):
        super().__init__(expr, result_type=Int64Type())

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, UnaryMinusExpr)

    def copy_with_subexpressions(self, new_subexpressions: List[Expr]):
        [expr] = new_subexpressions
        return UnaryMinusExpr(expr)

class VariadicTypeExpansion(UnaryExpr):
    def __init__(self, expr: Expr):
        super().__init__(expr, result_type=TypeType())

    def is_same_expr_excluding_subexpressions(self, other: Expr):
        return isinstance(other, VariadicTypeExpansion)

    def copy_with_subexpressions(self, new_subexpressions: List[Expr]):
        [expr] = new_subexpressions
        return VariadicTypeExpansion(expr)

class Header:
    def __init__(self,
                 template_defns: List[TemplateDefn],
                 toplevel_content: List[Union[StaticAssert, ConstantDef, Typedef]],
                 public_names: Set[str]):
        self.template_defns = template_defns
        self.toplevel_content = tuple(toplevel_content)
        self.public_names = public_names
