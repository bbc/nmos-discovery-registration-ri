# Copyright 2017 British Broadcasting Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from itertools import chain


class UnparseError(Exception):
    pass


def flatten(xs):
    for x in xs:
        if isinstance(x, list):
            for y in flatten(x):
                yield y
        else:
            yield x


OPERATOR_MAP = {
    'out': 'nin',
    'contains': 'all'
}


TYPE_A = '$eq'.split()  # $eq is not an operator in mongodb. Type A handles implicit.
TYPE_B = '$lte $lt $gt $gte $ne'.split()
TYPE_C = '$in $nin $all'.split()
TYPE_D = '$or $nor'.split()
TYPE_E = '$not'.split()
TYPE_F = '$and'.split()


def handle_type_a(_, field, value):
    return {field: value}


def handle_type_b(operator, field, value):
    return {field: {operator: value}}


def handle_type_c(operator, field, *values):
    return {field: {operator: list(flatten(values))}}


def handle_type_d(operator, *values):
    return {operator: list(values)}


def handle_type_e(operator, query):
    return {key: {operator: value} for key, value in query.items()}


def handle_type_f(operator, *values):
    ''' handles implicit collapsing of some operators:
        eg {$and: [a, b]} -> {a, b}
        {$and: [a]} -> a
        {$and: [a->b,a->c]} -> {$and: [a->b,a->c]}
    '''
    all_values_are_dicts = all(isinstance(val, dict) for val in values)
    if all_values_are_dicts:
        no_duplicate_keys = len(set(chain.from_iterable(d.keys() for d in values))) == len(values)

    if all_values_are_dicts and no_duplicate_keys:
        return dict(chain.from_iterable(d.items() for d in values))
    elif len(values) == 1:
        return values[0]
    else:
        return handle_type_d(operator, *values)


assemblers = dict(
    chain(
        ((operator, handle_type_a) for operator in TYPE_A),
        ((operator, handle_type_b) for operator in TYPE_B),
        ((operator, handle_type_c) for operator in TYPE_C),
        ((operator, handle_type_d) for operator in TYPE_D),
        ((operator, handle_type_e) for operator in TYPE_E),
        ((operator, handle_type_f) for operator in TYPE_F)
    )
)


def translate_name(name):
    return '$' + OPERATOR_MAP.get(name, name)


def unparse(node):
    if not isinstance(node, dict):
        return node

    try:
        name = translate_name(node['name'])
        args = [unparse(a) for a in node['args']]
    except KeyError:
        raise UnparseError('Abstract Sytnax Tree not in expected form: {}'.format(node))

    try:
        assembler = assemblers[name]
    except KeyError:
        raise UnparseError('Unsupported operator: {}'.format(name))

    return assembler(name, *args)
