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


def etcd_unpack(obj):
    """Take a JSON response object (as a dict) from etcd, and transform
    into a dict without the associated etcd cruft.

    >>> etcd_unpack({})
    {}
    >>> etcd_unpack({'node': { 'key': 'a', 'value': 'AA'}})
    {'a': 'AA'}
    >>> etcd_unpack({'node': {'nodes': [{'value': 'a', 'key': 'A'}, {'value': 'B', 'key': 'b'}], 'dir': True, 'key': 'pa'}})
    {'pa': {'A': 'a', 'b': 'B'}}
    >>> etcd_unpack({'node': {'nodes': [{'nodes': [{'value': 'a', 'key': 'A'}], 'dir': True, 'key': 'pa'}], 'dir': True, 'key': 'paa'}})
    {'paa': {'pa': {'A': 'a'}}}
    >>> etcd_unpack({'node': {'dir': True, 'key': '/resource/flow'}})
    {'/resource/flow': {}}
    """
    def _unpack_lst(n):
        rv = {}
        for v in n:
            if not 'dir' in v:
                rv[v['key']] = v['value']
            elif 'nodes' in v:
                rv[v['key']] = _unpack_lst(v['nodes'])
            else:
                rv[v['key']] = {}
        return rv

    if not 'node' in obj:
        return {}

    n = obj['node']
    if not 'dir' in n:
        return {n['key']: n['value']}
    elif 'nodes' in n:
        return {n['key']: _unpack_lst(n['nodes'])}
    else:
        return {n['key']: {}}


if __name__ == '__main__':
    import doctest
    doctest.testmod()
