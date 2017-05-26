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

from ..parser import parse
from .fixtures import query_pairs


def test_generator():
    for test_cases in query_pairs.values():
        for q, expected in test_cases.items():

            print 'next query {} -> {}'.format(q, expected)

            actual = parse(q)

            # some of the tests are not in their final form..
            if isinstance(expected, str):
                expected = parse(expected)
            if expected.get('cache'):
                del expected['cache']

            yield check_params, actual, expected


def check_params(a, b):
    print 'found actual {}, expected {}. Result: {}'.format(a, b, a == b)

    if isinstance(b, dict):
        # poor mans deep comparison
        assert set(a) == set(b)
        assert str(a) == str(b)
    else:
        assert a == b
