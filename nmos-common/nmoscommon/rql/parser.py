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

import re
import logging
from functools import reduce
from .converters import CONVERTERS, convert_from_fiql


JSON_QUERY_COMPATIBLE = True
JSON_QUERY_SUBSTITUTIONS = {
    r'/%3C=/g': '=le=',
    r'/%3E=/g': '=ge=',
    r'/%3C/g': '=lt=',
    r'/%3E/g': '=gt='
}


PARSING_REGEX = r'(\))|([&\|,])?([\+\*\$\-:\w%\._]*)(\(?)'
BUBBLE_TO_TOP_OPERATORS = ['sort', 'select', 'values', 'limit']
PRIMARY_KEY_NUMBER = 'id'
DEFAULT_NODE_NAME = 'and'


class URIError(Exception):
    pass


class ParserError(Exception):
    pass


def str_to_val(string):
    converter = CONVERTERS['auto']

    if ':' in string:
        convert_name, rest = string.split(":", 1)
        try:
            logging.info('attempting to convert {} with {} converter'.format(string, convert_name))
            converter = CONVERTERS[convert_name]
        except KeyError as e:
            raise ParserError('Unknown converter ' + convert_name, e)
        string = ':'.join([rest])

    return converter(string)


class Query(object):
    def __init__(self, name='', args=None, parent=None):
        self.name = name
        self.args = args
        self.cache = {}
        self.parent = parent

        if self.args is None:
            self.args = []

    def add_argument(self, arg):
        self.args.append(arg)
        return self

    def set_conjuction(self, operator):
        if not self.name:
            self.name = operator
        elif self.name != operator:
            raise ParserError(
                'Can not mix conjunctions within a group, use paranthesis around each set of same conjuctions (& and |)'
            )
        return self

    def dict(self):
        return {'name': self.name, 'args': [x.dict() if isinstance(x, Query) else x for x in self.args]}

    def __repr__(self):
        return str(self.dict())


def parse(query):

    top_term = term = Query()

    if isinstance(query, Query):
        return query
    elif isinstance(query, dict):
        for key, value in query.items():
            term.add_argument(Query('eq', [key, value]))

    if query[0] == '?':
        # raise URIError('Query mustnot start with ?')
        query = query[1:]

    if '/' in query:
        query = re.sub(
            r'[\+\*\$\-:\w%\._]*\/[\+\*\$\-:\w%\._\/]*',
            lambda s: '({})'.format(s.group().replace('/', ',')),
            query
        )

    if JSON_QUERY_COMPATIBLE:
        query = reduce(
            lambda q, args: re.sub(args[0], args[1], q),
            JSON_QUERY_SUBSTITUTIONS.items(),
            query
        )

    query = convert_from_fiql(query)

    current_term = term
    for closed_paran, delim, property_or_value, open_paran in re.findall(PARSING_REGEX, query):
        if delim:
            if delim == '&':
                current_term.set_conjuction('and')
            elif delim == '|':
                current_term.set_conjuction('or')

        if open_paran:
            new_term = Query(property_or_value, parent=current_term)
            current_term.add_argument(new_term)
            if current_term.name in BUBBLE_TO_TOP_OPERATORS:
                top_term.cache[term.name] = term.args
            current_term = new_term
        elif closed_paran:
            if current_term.parent is None:
                raise ParserError('Closing paranthesis without an opening paranthesis')

            # TODO: this isn't clear
            conjunction = current_term.name
            current_term = current_term.parent

            if not conjunction:
                unrequired_query_object = current_term.args.pop()
                current_term.add_argument(unrequired_query_object.args)

        elif (property_or_value or ',' in delim):
            val = str_to_val(property_or_value)
            if val is not '':
                current_term.add_argument(val)

            # cache operators we want to bubble to top term
            if term.name in BUBBLE_TO_TOP_OPERATORS:
                top_term.cache[term.name] = term.args

            if term.name == 'eq' and term.args[0] == PRIMARY_KEY_NUMBER:
                top_term.cache[PRIMARY_KEY_NUMBER] = term.args[1]

    if current_term.parent is not None:
        raise ParserError('Opening paranthesis without an closing paranthesis')

    left_over_characters = re.sub(PARSING_REGEX, '', query)
    if left_over_characters:
        # raise URIError('Query must not start with ?')
        pass

    if not top_term.name:
        top_term.name = DEFAULT_NODE_NAME

    return top_term.dict()
