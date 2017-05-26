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

from urllib import unquote
from .dateutil import strptime_partial
from datetime import datetime
import json
import re
import logging

JSON_QUERY_COMPATIBLE = True


CONVERT_TYPES = {
    'true': True,
    'false': False,
    'none': None,
    'null': None,
    'undefined': None,
    'infinity': float('inf'),
    '-infinity': -float('inf')
}


class ConversionError(Exception):
    pass


def converter_auto(string):
    if string.lower() in CONVERT_TYPES:
        known_conversion = CONVERT_TYPES[string.lower()]
        logging.info('auto conversition for {} -> {}'.format(string, known_conversion))
        ret = known_conversion
    elif string.isdigit():
        logging.info('auto converting {} to integer'.format(string))
        ret = int(string)
    else:
        ret = unquote(string)
        if ret and JSON_QUERY_COMPATIBLE:
            if "'" == ret[0] == ret[-1]:
                ret = json.loads('"{}"'.format(ret[1: -1]))
    if ret == string:
        logging.info('auto converting made no change to {}'.format(string))
    return ret


def converter_number(n):
    return int(n)


def converter_epoch(x):
    delta = (strptime_partial(x) - datetime(1970, 1, 1))
    return int(1000 * delta.total_seconds())


def converter_isodate(x):
    return strptime_partial(x)


def converter_date(x):
    return strptime_partial(x)


def converter_boolean(x):
    x = x.lower()
    if x == 'true':
        return True
    elif x == 'false':
        return False
    else:
        raise ConversionError('Do not recognise boolean: {}'.format(x))
    return x == 'true'


def converter_string(x):
    return unquote(x)


def converter_re(x):    # TODO: no test coverage
    return re.compile(converter_string(x), flags=re.IGNORECASE)


def converter_RE(x):    # TODO: no test coverage
    return re.compile(converter_string(x))


def converter_glob(x):
    raise NotImplementedError('cannot convert blob {}'.format(x))


CONVERTERS = {
    'auto': converter_auto,
    'number': converter_number,
    'epoch': converter_epoch,
    'isodate': converter_isodate,
    'date': converter_date,
    'boolean': converter_boolean,
    'string': converter_string,
    're': converter_re,
    'RE': converter_RE,
    'glob': converter_glob
}

FIQL_REGEX = r'(\([\+\*\$\-:\w%\._,]+\)|[\+\*\$\-:\w%\._]*|)([<>!]?=(?:[\w]*=)?|>|<)(\([\+\*\$\-:\w%\._,]+\)|[\+\*\$\-:\w%\._]*|)'

OPERATOR_MAP = {
    '=': 'eq',
    '==': 'eq',
    '>': 'gt',
    '>=': 'ge',
    '<': 'lt',
    '<=': 'le',
    '!=': 'ne'
}


def convert_from_fiql(query):

    def substitutor(match):
        prop, operator, value = match.groups()
        if len(operator) < 3:
            try:
                operator = OPERATOR_MAP[operator]
            except KeyError:
                raise ConversionError("Illegal operator {}".format(operator))
        else:
            operator = operator[1:-1]
        return operator + '(' + prop + ',' + value + ')'

    return re.sub(FIQL_REGEX, substitutor, query)
