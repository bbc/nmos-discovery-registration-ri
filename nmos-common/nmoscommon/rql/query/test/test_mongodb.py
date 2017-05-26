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
Tests ported from https://github.com/alonho/pql
'''

from unittest import TestCase, skip
from .. import mongodb
from datetime import datetime


class BaseMongoTestCase(TestCase):

    def compare(self, ast, expected):
        print ast, '->', expected
        self.assertEqual(mongodb.unparse(ast), expected)


class SchemaLessTestCase(BaseMongoTestCase):

    @skip('should check if the recursion is correct for more than 3 levels')
    def test_deeply_nested(self):
        self.compare({}, {})
        self.assertTrue(False)

    def test_multiple_arguments_raise_for_wrong_operator(self):
        self.assertTrue(True)

    def test_and_multiple_arguments_does_not_collapse(self):
        self.compare({
            'args': [
                {'args': ['a', 'b'], 'name': 'eq'}, {'args': ['a', 't'], 'name': 'eq'}, {'args': ['a', 'f'], 'name': 'eq'}
            ],
            'name': 'and'
            }, {'$and': [{'a': 'b'}, {'a': 't'}, {'a': 'f'}]}
        )

    def test_contains(self):
        self.compare({'args': ['tags', 'foo', 'bar'], 'name': 'contains'}, {'tags': {'$all': ['foo', 'bar']}})
        self.compare({'args': ['tags', 'foo'], 'name': 'contains'}, {'tags': {'$all': ['foo']}})

    def test_collapse_and_with_single_arg(self):
        self.compare({'name': 'and', 'args': [{'name': 'eq', 'args': ['foo', 'bar']}]}, {'foo': 'bar'})
        self.compare({'name': 'eq', 'args': ['foo', 'bar']}, {'foo': 'bar'})

    def test_hyphenated(self):
        self.compare({'name': 'eq', 'args': ['foo-bar', 'spam']}, {'foo-bar': 'spam'})

    def test_equal_int(self):
        self.compare({'name': 'eq', 'args': ['a', 1]}, {'a': 1})

    def test_not_equal_string(self):
        self.compare({'name': 'ne', 'args': ['a', 'foo']}, {'a': {'$ne': 'foo'}})

    def test_nested(self):
        self.compare({'name': 'eq', 'args': ['a.b', 1]}, {'a.b': 1})

    def test_and(self):
        self.compare({'name': 'and', 'args': [
            {'name': 'eq', 'args': ['a', 1]},
            {'name': 'eq', 'args': ['b', 2]}
        ]}, {'a': 1, 'b': 2})

    def test_or(self):
        self.compare({'name': 'or', 'args': [
            {'name': 'eq', 'args': ['a', 1]},
            {'name': 'eq', 'args': ['b', 2]}
        ]}, {'$or': [{'a': 1}, {'b': 2}]})

    def test_not(self):
        self.compare({'name': 'not', 'args': [
            {'name': 'gt', 'args': ['a', 1]}
        ]}, {'a': {'$not': {'$gt': 1}}})

    def test_algebra(self):
        for string, expected in [({'name': 'gt', 'args': ['a', 1]}, {'a': {'$gt': 1}}),
                                 ({'name': 'gte', 'args': ['a', 1]}, {'a': {'$gte': 1}}),
                                 ({'name': 'lt', 'args': ['a', 1]}, {'a': {'$lt': 1}}),
                                 ({'name': 'lte', 'args': ['a', 1]}, {'a': {'$lte': 1}})]:
            self.compare(string, expected)

    def test_bool(self):
        self.compare({'name': 'eq', 'args': ['a', True]}, {'a': True})
        self.compare({'name': 'eq', 'args': ['a', False]}, {'a': False})

    def test_none(self):
        self.compare({'name': 'eq', 'args': ['a', None]}, {'a': None})

    def test_list(self):
        self.compare({'name': 'eq', 'args': ['a', [1, 2, 3]]}, {'a': [1, 2, 3]})

    def test_in(self):
        self.compare({'name': 'in', 'args': ['a', {'name': 'and', 'args': [[1, 2, 3]]}]}, {'a': {'$in': [1, 2, 3]}})

    # @skip('out is not an official RQL operator')
    def test_not_in(self):
        # self.compare({'name': 'out', 'args': ['a', [1, 2, 3]]}, {'a': {'$nin': [1, 2, 3]}})
        self.compare({'name': 'out', 'args': ['a', {'name': 'and', 'args': [[1, 2, 3]]}]}, {'a': {'$nin': [1, 2, 3]}})

    def test_unknown_operator(self):
        with self.assertRaises(mongodb.UnparseError) as context:
            mongodb.unparse({'name': 'foo', 'args': ['a', [1, 2, 3]]})
        self.assertIn('Unsupported operator', str(context.exception))

    @skip('Currently unsupported')
    def test_exists(self):
        self.compare('a == exists(True)', {'a': {'$exists': True}})

    @skip('Currently unsupported')
    def test_type(self):
        self.compare('a == type(3)', {'a': {'$type': 3}})

    @skip('Currently unsupported')
    def test_regex(self):
        self.compare('a == regex("foo")', {'a': {'$regex': 'foo'}})
        self.compare('a == regex("foo", "i")', {'a': {'$regex': 'foo', '$options': 'i'}})

    def test_date(self):
        self.compare({'name': 'eq', 'args': ['a', datetime(2012, 3, 4)]}, {'a': datetime(2012, 3, 4)})
