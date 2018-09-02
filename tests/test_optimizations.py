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

from py2tmp.testing import *

@assert_code_optimizes_to(r'''
#include <tmppy/tmppy.h>
#include <type_traits>
template <typename> struct CheckIfError { using type = void; };
template <int64_t TmppyInternal_5> struct inc {
  static constexpr int64_t value = (TmppyInternal_5) + (1LL);
  using error = void;
};
''')
def test_optimization_one_function():
    def inc(n: int):
        return n + 1

@assert_code_optimizes_to(r'''
#include <tmppy/tmppy.h>
#include <type_traits>
template <typename> struct CheckIfError { using type = void; };
static_assert(((1LL) + (1LL)) == (2LL),
              "TMPPy assertion failed: \n<unknown>:1: assert 1 + 1 == 2");
''')
def test_optimization_toplevel_code():
    assert 1 + 1 == 2

@assert_code_optimizes_to(r'''
#include <tmppy/tmppy.h>
#include <type_traits>
template <typename> struct CheckIfError { using type = void; };
template <int64_t TmppyInternal_5> struct f {
  static constexpr int64_t TmppyInternal_10 =
      (2LL) * ((TmppyInternal_5) + (1LL));
  using TmppyInternal_18 = int *;
  static constexpr bool value =
      ((TmppyInternal_10) == (TmppyInternal_10)) ==
      (std::is_same<
          typename Select1stTypeInt64<TmppyInternal_18, TmppyInternal_5>::value,
          TmppyInternal_18>::value);
  using error = void;
};
''')
def test_common_subexpression_elimination():
    from tmppy import Type
    def f(n: int):
        x1 = 2*(n + 1)
        x2 = 2*(n + 1)
        t1 = Type.pointer(Type('int'))
        t2 = Type.pointer(Type('int'))
        return (x1 == x2) == (t1 == t2)

@assert_code_optimizes_to(r'''
#include <tmppy/tmppy.h>
#include <type_traits>
template <typename> struct CheckIfError { using type = void; };
static constexpr int64_t TmppyInternal_9 = (2LL) * ((3LL) + (1LL));
using TmppyInternal_17 = int *;
static_assert(
    ((TmppyInternal_9) == (TmppyInternal_9)) ==
        (std::is_same<TmppyInternal_17, TmppyInternal_17>::value),
    "TMPPy assertion failed: \n<unknown>:2: assert (2*(3+1) == 2*(3+1)) == "
    "(Type.pointer(Type('int')) == Type.pointer(Type('int')))");
''')
def test_common_subexpression_elimination_toplevel():
    from tmppy import Type
    assert (2*(3+1) == 2*(3+1)) == (Type.pointer(Type('int')) == Type.pointer(Type('int')))

@assert_code_optimizes_to(r'''
#include <tmppy/tmppy.h>
#include <type_traits>
template <typename> struct CheckIfError { using type = void; };
static constexpr int64_t TmppyInternal_9 = (2LL) * ((3LL) + (1LL));
using TmppyInternal_17 = int *;
static_assert(
    ((TmppyInternal_9) == (TmppyInternal_9)) ==
        (std::is_same<TmppyInternal_17, TmppyInternal_17>::value),
    "TMPPy assertion failed: \n<unknown>:2: assert (2*(3 + 1) == 2*(3 + 1)) == "
    "(Type.pointer(Type('int')) == Type.pointer(Type('int')))");
''')
def test_common_subexpression_elimination_at_toplevel():
    from tmppy import Type
    assert (2*(3 + 1) == 2*(3 + 1)) == (Type.pointer(Type('int')) == Type.pointer(Type('int')))

@assert_code_optimizes_to(r'''
#include <tmppy/tmppy.h>
#include <type_traits>
template <typename> struct CheckIfError { using type = void; };
template <int64_t TmppyInternal_5> struct inc {
  using error = void;
  static constexpr int64_t value = (TmppyInternal_5) + (1LL);
};
''')
def test_optimization_two_functions_with_call():
    def _plus(n: int, m: int):
        return n + m
    def inc(n: int):
        return _plus(n, 1)

@assert_code_optimizes_to(r'''
#include <tmppy/tmppy.h>
#include <type_traits>
template <typename> struct CheckIfError { using type = void; };
static_assert(((3LL) + (1LL)) == (4LL),
              "TMPPy assertion failed: \n<unknown>:3: assert _plus(3, 1) == 4");
''')
def test_optimization_function_call_at_toplevel():
    def _plus(n: int, m: int):
        return n + m
    assert _plus(3, 1) == 4

@assert_code_optimizes_to(r'''
#include <tmppy/tmppy.h>
#include <type_traits>
template <typename> struct CheckIfError { using type = void; };
template <bool TmppyInternal_5, bool> struct TmppyInternal_10;
template <bool TmppyInternal_5> struct f;
template <bool TmppyInternal_5> struct g;
// (meta)function generated for an if-else statement
template <bool TmppyInternal_5> struct TmppyInternal_10<TmppyInternal_5, true> {
  static constexpr int64_t value = 3LL;
  using error = void;
};
// (meta)function generated for an if-else statement
template <bool TmppyInternal_5>
struct TmppyInternal_10<TmppyInternal_5, false> {
  static constexpr int64_t value = g<true>::value;
  using error = void;
};
template <bool TmppyInternal_5> struct f {
  static constexpr int64_t value =
      TmppyInternal_10<TmppyInternal_5, TmppyInternal_5>::value;
  using error =
      typename TmppyInternal_10<TmppyInternal_5, TmppyInternal_5>::error;
};
template <bool TmppyInternal_5> struct g {
  static constexpr int64_t value = f<TmppyInternal_5>::value;
  using error = void;
};
''')
def test_optimization_of_mutually_recursive_functions():
    def f(b: bool) -> int:
        if b:
            return 3
        else:
            return g(True)
    def g(b: bool) -> int:
        return f(b)

@assert_code_optimizes_to(r'''
#include <tmppy/tmppy.h>
#include <type_traits>
template <typename> struct CheckIfError { using type = void; };
template <typename TmppyInternal_22, typename> struct TmppyInternal_24;
// (meta)function wrapping a match expression
template <typename TmppyInternal_22, typename... TmppyInternal_23>
struct TmppyInternal_24<TmppyInternal_22, std::tuple<TmppyInternal_23...>> {
  using type = List<TmppyInternal_23...>;
  using error = void;
};
template <typename TmppyInternal_9, typename TmppyInternal_8, bool>
struct TmppyInternal_26;
// (meta)function generated for an if-else statement
template <typename TmppyInternal_9, typename TmppyInternal_8>
struct TmppyInternal_26<TmppyInternal_9, TmppyInternal_8, true> {
  using type = void;
  using error = TmppyInternal_9;
};
// (meta)function generated for an if-else statement
template <typename TmppyInternal_9, typename TmppyInternal_8>
struct TmppyInternal_26<TmppyInternal_9, TmppyInternal_8, false> {
  using error = void;
  using type = TmppyInternal_8;
};
template <typename> struct TmppyInternal_28;
// (meta)function to expand the list of args for a template instantiation
template <typename... TmppyInternal_27>
struct TmppyInternal_28<List<TmppyInternal_27...>> {
  using type = std::tuple<TmppyInternal_27...>;
};
using TmppyInternal_45 =
    typename TmppyInternal_28<List<int, float, double>>::type;
using TmppyInternal_47 =
    typename TmppyInternal_24<void, TmppyInternal_45>::error;
static_assert(
    std::is_same<typename TmppyInternal_26<
                     TmppyInternal_47,
                     typename TmppyInternal_24<void, TmppyInternal_45>::type,
                     !(std::is_same<TmppyInternal_47, void>::value)>::type,
                 List<int, float, double>>::value,
    "TMPPy assertion failed: \n<unknown>:7: assert "
    "_unpack_tuple(Type.template_instantiation('std::tuple', [Type('int'), "
    "Type('float'), Type('double')])) \\");
''')
def test_match_expr_extract_list_optimization():
    from tmppy import Type, match
    def _unpack_tuple(t: Type):
        return match(t)(lambda Ts: {
            Type.template_instantiation('std::tuple', [*Ts]):
                Ts
        })
    assert _unpack_tuple(Type.template_instantiation('std::tuple', [Type('int'), Type('float'), Type('double')])) \
        == [Type('int'), Type('float'), Type('double')]
