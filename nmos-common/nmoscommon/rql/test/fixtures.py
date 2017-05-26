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

'''
    Test cases ported directly from https://github.com/persvr/rql/blob/master/test/query.js
'''
import datetime

query_pairs = {
    'arrays': {
        'a': {'name': 'and', 'args': ['a']},
        '(a)': {'name': 'and', 'args': [['a']]},
        'a,b,c': {'name': 'and', 'args': ['a', 'b', 'c']},
        '(a,b,c)': {'name': 'and', 'args': [['a', 'b', 'c']]},
        'a(b)': {'name': 'and', 'args': [{'name': 'a', 'args': ['b']}]},
        'a(b,c)': {'name': 'and', 'args': [{'name': 'a', 'args': ['b', 'c']}]},
        'a((b),c)': {'name': 'and', 'args': [{'name': 'a', 'args': [['b'], 'c']}]},
        'a((b,c),d)': {'name': 'and', 'args': [{'name': 'a', 'args': [['b', 'c'], 'd']}]},
        'a(b/c,d)': {'name': 'and', 'args': [{'name': 'a', 'args': [['b', 'c'], 'd']}]},
        'a(b)&c(d(e))': {'name': 'and', 'args': [
            {'name': 'a', 'args': ['b']},
            {'name': 'c', 'args': [{'name': 'd', 'args': ['e']}]}
        ]}
    },
    'dot-comparison': {
        'foo.bar=3': {'name': 'and', 'args': [{'name': 'eq', 'args': ['foo.bar', 3]}]},
        'select(sub.name)': {
            'name': 'and',
            'args': [{'name': 'select', 'args': ['sub.name']}],
            'cache': {'select': ['sub.name']}
        }
    },
    'equality': {
        'eq(a,b)': {'name': 'and', 'args': [{'name': 'eq', 'args': ['a', 'b']}]},
        'a=eq=b': 'eq(a,b)',
        'a=b': 'eq(a,b)'
    },
    'inequality': {
        'ne(a,b)': {'name': 'and', 'args': [{'name': 'ne', 'args': ['a', 'b']}]},
        'a=ne=b': 'ne(a,b)',
        'a!=b': 'ne(a,b)'
    },
    'less-than': {
        'lt(a,b)': {'name': 'and', 'args': [{'name': 'lt', 'args': ['a', 'b']}]},
        'a=lt=b': 'lt(a,b)',
        'a<b': 'lt(a,b)'
    },
    'less-than-equals': {
        'le(a,b)': {'name': 'and', 'args': [{'name': 'le', 'args': ['a', 'b']}]},
        'a=le=b': 'le(a,b)',
        'a<=b': 'le(a,b)'
    },
    'greater-than': {
        'gt(a,b)': {'name': 'and', 'args': [{'name': 'gt', 'args': ['a', 'b']}]},
        'a=gt=b': 'gt(a,b)',
        'a>b': 'gt(a,b)'
    },
    'greater-than-equals': {
        'ge(a,b)': {'name': 'and', 'args': [{'name': 'ge', 'args': ['a', 'b']}]},
        'a=ge=b': 'ge(a,b)',
        'a>=b': 'ge(a,b)'
    },
    'nested comparisons': {
        'a(b(le(c,d)))': {'name': 'and', 'args': [
            {'name': 'a', 'args': [
                {'name': 'b', 'args': [{'name': 'le', 'args': ['c', 'd']}]}]}
        ]},
        'a(b(c=le=d))': 'a(b(le(c,d)))',
        'a(b(c<=d))': 'a(b(le(c,d)))'
    },
    'arbitrary FIQL desugaring': {
        'a=b=c': {'name': 'and', 'args': [{'name': 'b', 'args': ['a', 'c']}]},
        'a(b=cd=e)': {'name': 'and', 'args': [{'name': 'a', 'args': [{'name': 'cd', 'args': ['b', 'e']}]}]}
    },
    'and grouping': {
        'a&b&c': {'name': 'and', 'args': ['a', 'b', 'c']},
        'a(b)&c': {'name': 'and', 'args': [{'name': 'a', 'args': ['b']}, 'c']},
        'a&(b&c)': {'name': 'and', 'args': ['a', {'name': 'and', 'args': ['b', 'c']}]}
    },
    'or grouping': {
        '(a|b|c)': {'name': 'and', 'args': [{'name': 'or', 'args': ['a', 'b', 'c']}]},
        '(a(b)|c)': {'name': 'and', 'args': [{'name': 'or', 'args': [{'name': 'a', 'args': ['b']}, 'c']}]}
    },
    'complex grouping': {
        'a&(b|c)': {'name': 'and', 'args': ['a', {'name': 'or', 'args': ['b', 'c']}]},
        'a|(b&c)': {'name': 'or', 'args': ['a', {'name': 'and', 'args': ['b', 'c']}]},
        'a(b(c<d,e(f=g)))': {
            'name': 'and',
            'args': [
                {
                    'name': 'a',
                    'args': [{'name': 'b', 'args': [
                            {'name': 'lt', 'args': ['c', 'd']},
                            {'name': 'e', 'args': [{'name': 'eq', 'args': ['f', 'g']}]}
                    ]}]
                }
            ]
        }
    },
    'complex comparisons': {

    },
    'string coercion': {
        'a(string)': {'name': 'and', 'args': [{'name': 'a', 'args': ['string']}]},
        'a(string:b)': {'name': 'and', 'args': [{'name': 'a', 'args': ['b']}]},
        'a(string:1)': {'name': 'and', 'args': [{'name': 'a', 'args': ['1']}]}
    },
    'number coercion': {
        'a(number)': {'name': 'and', 'args': [{'name': 'a', 'args': ['number']}]},
        'a(number:1)': {'name': 'and', 'args': [{'name': 'a', 'args': [1]}]}
    },
    'date coercion': {
        'a(date)': {'name': 'and', 'args': [{'name': 'a', 'args': ['date']}]},
        'a(date:2009)': {'name': 'and', 'args': [{'name': 'a', 'args': [datetime.datetime(2009, 1, 1)]}]},
        'a(date:1989-11-21)': {'name': 'and', 'args': [{'name': 'a', 'args': [(datetime.datetime(1989, 11, 21))]}]},
        'a(date:1989-11-21T00:21:00.21Z)': {'name': 'and', 'args': [{'name': 'a', 'args': [(datetime.datetime(1989, 11, 21, 0, 21, 0, 210000))]}]},
        'a(date:1989-11-21T00:21:00)': {'name': 'and', 'args': [{'name': 'a', 'args': [(datetime.datetime(1989, 11, 21, 0, 21, 0))]}]}
    },
    'boolean coercion': {
        'a(True)': {'name': 'and', 'args': [{'name': 'a', 'args': [True]}]},
        'a(False)': {'name': 'and', 'args': [{'name': 'a', 'args': [False]}]},
        'a(boolean:True)': {'name': 'and', 'args': [{'name': 'a', 'args': [True]}]}
    },
    'None coercion': {
        'a(None)': {'name': 'and', 'args': [{'name': 'a', 'args': [None]}]},
        'a(auto:None)': {'name': 'and', 'args': [{'name': 'a', 'args': [None]}]},
        'a(string:None)': {'name': 'and', 'args': [{'name': 'a', 'args': ['None']}]}
    },
    'complex coercion': {
        '(a=b|c=d)&(e=f|g=1)': {'name': 'and', 'args': [
            {'name': 'or', 'args': [{'name': 'eq', 'args': ['a', 'b']}, {
                'name': 'eq', 'args': ['c', 'd']}]},
            {'name': 'or', 'args': [{'name': 'eq', 'args': [
                'e', 'f']}, {'name': 'eq', 'args': ['g', 1]}]}
        ]}
    },
    'epoch': {
        'a(epoch:1970-1-1)': {'name': 'and', 'args': [{'name': 'a', 'args': [0]}]},
        'a(epoch:2009-11-1T01:04:05.3)': {'name': 'and', 'args': [{'name': 'a', 'args': [1257037445300]}]}
    },
    'real-word': {
        'eq(label,testing)': {'name': 'and', 'args':[{'name': 'eq', 'args': ['label', 'testing']}]},
    },
    'uri-encoding': {
        'eq(label,value%20with%20space)': {'name': 'and', 'args':[{'name': 'eq', 'args': ['label', 'value with space']}]}
    }
}
