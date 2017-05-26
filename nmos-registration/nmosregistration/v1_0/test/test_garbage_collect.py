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

import unittest

from nmosregistration.garbage import GarbageCollect

class MockDataBackend():

    class RegistryUnavailable(Exception):
        pass

    def __init__(self):
        self._data = {}

    def set_data(self, data):
        self._data = data

    def get_healths(self):
        health = self._data.get('/health', {})
        return {'/health': health}

    def get_all(self, rtype):
        return self._data.get(rtype, [])

    def getresources(self, rtype):
        return ["{}/".format(x['id']) for x in self._data.get(rtype, [])]

    def get(self, rtype, rid):
        find = (x for x in self.get_all(rtype) if x['id'] == rid)
        return next(find, None)

    def delete(self, rtype, rid):
        self._data[rtype] = [x for x in self._data.get(rtype, []) if x['id'] != rid]

    def put_obj(self, value):
        exist = self._data.setdefault(value['type'] + 's', [])
        exist.append(value['data'])

class GarbageCollectionTest(unittest.TestCase):

    orphan_resources = [
        {'type': 'node',
         'data': {
             'id': '33279d1d-1be9-43eb-9ac5-7c7a5a80a2c5',
             'version': '1:1',
             'label': 'node-test',
             'href': 'http://127.0.0.1:8020/',
             'caps': {},
             'services': []
         }},
        {'type': 'source',
         'data': {
             'id': 'da80a4c4-6e52-46a0-b204-025538d2b25a',
             'version': '1:1',
             'label': 'source-test',
             'description': 'source...',
             'format': 'urn:x-nmos:format:video',
             'tags': {},
             'device_id': '26303eaf-b302-4f3a-bcf9-51432fdb7e5c',
             'parents': []
         }},
        {'type': 'flow',
         'data': {
             'id': '416f2803-8ac9-47a6-8c67-beff6ee8c76a',
             'version': '1:1',
             'label': 'flow-test',
             'description': 'flow...',
             'format': 'urn:x-nmos:format:video',
             'source_id': '7193bfc4-1b09-4186-8bf0-28036b503e66',
             'parents': []
         }},
        {'type': 'flow',
         'data': {
             'id': '416f2803-8ac9-47a6-8c67-beff6ee8c76a',
             'version': '1:1',
             'label': 'flow-test-with-device',
             'description': 'flow...',
             'format': 'urn:x-nmos:format:video',
             'source_id': '7193bfc4-1b09-4186-8bf0-28036b503e66',
             'device_id': 'f470f024-b625-4b92-bb86-7e0cfc7c7126',
             'parents': []
         }},
        {'type': 'device',
         'data': {
             'id': '42263920-39ff-4300-aea7-27bda12e9543',
             'version': '1:1',
             'label': 'device-test',
             'type': 'urn:x-nmos:device:type',
             'node_id': '58ae56e0-c769-4be2-9ffb-a525068484c5',
             'senders': [],
             'receivers': []
         }},
        {'type': 'sender',
         'data': {
             'id': 'b13e1bab-c841-45d3-b674-6374459810d4',
             'version': '1:1',
             'label': 'sender-test',
             'description': 'sender...',
             'flow_id': 'e656d33c-37d3-4e96-9152-6a0672f66167',
             'transport': 'urn:x-nmos:transport:rtp',
             'device_id': 'c6dc88ad-12a5-48d2-914a-78eb322cedbd',
             'manifest_href': 'http://127.0.0.1:8145/'
         }},
        {'type': 'receiver',
         'data': {
             'id': '76c58953-b7ec-43c7-a2c4-ead95d66edf9',
             'version': '1:1',
             'label': 'receiver-test',
             'description': 'receiver...',
             'format': 'urn:x-nmos:format:video',
             'caps': {},
             'tags': {},
             'device_id': 'de13cbcc-fb9e-4e6a-8532-53daff3ab111',
             'transport': 'urn:x-nmos:transport:rtp',
             'subscription': {}
         }}
    ]

    tree_resources = [
        {'type': 'node',
         'data': {
             'id': '33279d1d-1be9-43eb-9ac5-7c7a5a80a2c5',
             'version': '1:1',
             'label': 'node-test',
             'href': 'http://127.0.0.1:8020/',
             'caps': {},
             'services': []
         }},
        {'type': 'source',
         'data': {
             'id': 'da80a4c4-6e52-46a0-b204-025538d2b25a',
             'version': '1:1',
             'label': 'source-test',
             'description': 'source...',
             'format': 'urn:x-nmos:format:video',
             'tags': {},
             'device_id': '42263920-39ff-4300-aea7-27bda12e9543',
             'parents': []
         }},
        {'type': 'flow',
         'data': {
             'id': '416f2803-8ac9-47a6-8c67-beff6ee8c76a',
             'version': '1:1',
             'label': 'flow-test',
             'description': 'flow...',
             'format': 'urn:x-nmos:format:video',
             'source_id': 'da80a4c4-6e52-46a0-b204-025538d2b25a',
             'device_id': '42263920-39ff-4300-aea7-27bda12e9543',
             'parents': []
         }},
        {'type': 'device',
         'data': {
             'id': '42263920-39ff-4300-aea7-27bda12e9543',
             'version': '1:1',
             'label': 'device-test',
             'type': 'urn:x-nmos:device:type',
             'node_id': '33279d1d-1be9-43eb-9ac5-7c7a5a80a2c5',
             'senders': [],
             'receivers': []
         }},
        {'type': 'sender',
         'data': {
             'id': 'b13e1bab-c841-45d3-b674-6374459810d4',
             'version': '1:1',
             'label': 'sender-test',
             'description': 'sender...',
             'flow_id': 'e656d33c-37d3-4e96-9152-6a0672f66167',
             'transport': 'urn:x-nmos:transport:rtp',
             'device_id': '42263920-39ff-4300-aea7-27bda12e9543',
             'manifest_href': 'http://127.0.0.1:8145/'
         }},
        {'type': 'receiver',
         'data': {
             'id': '76c58953-b7ec-43c7-a2c4-ead95d66edf9',
             'version': '1:1',
             'label': 'receiver-test',
             'description': 'receiver...',
             'format': 'urn:x-nmos:format:video',
             'caps': {},
             'tags': {},
             'device_id': '42263920-39ff-4300-aea7-27bda12e9543',
             'transport': 'urn:x-nmos:transport:rtp',
             'subscription': {}
         }}
    ]

    @classmethod
    def setUpClass(self):
        self._registry = MockDataBackend()
        self._collector = GarbageCollect(identifier='test', registry=self._registry)

    def setUp(self):
        self._registry.set_data({})

    def test_tree_resources(self):
        for r in self.tree_resources:
            self._registry.put_obj(r)
        self._collector._collect()
        for r in self.tree_resources:
            res = self._registry.get(r['type'] + 's', r['data']['id'])
            self.assertIsNone(res)

    def test_tree_alive(self):
        self._registry.set_data({'/health': {'/health/33279d1d-1be9-43eb-9ac5-7c7a5a80a2c5': '0'}})
        for r in self.tree_resources:
            self._registry.put_obj(r)
        self._collector._collect()
        for r in self.tree_resources:
            res = self._registry.get(r['type'] + 's', r['data']['id'])
            self.assertIsNotNone(res)

    def test_tree_resources_no_device(self):
        self._registry.set_data({'/health': {'/health/33279d1d-1be9-43eb-9ac5-7c7a5a80a2c5': '0'}})
        res = [r for r in self.tree_resources if r['type'] != 'device']
        for r in res:
            self._registry.put_obj(r)
        self._collector._collect()
        for r in self.tree_resources:
            res = self._registry.get(r['type'] + 's', r['data']['id'])
            # node should still be alive
            if r['type'] == 'node':
                self.assertIsNotNone(res)
            else:
                self.assertIsNone(res)

    def test_orphan_resources(self):
        for r in self.orphan_resources:
            self._registry.put_obj(r)
        self._collector._collect()
        for r in self.orphan_resources:
            res = self._registry.get(r['type'] + 's', r['data']['id'])
            self.assertIsNone(res)

    def test_orphan_types(self):
        for rtype in ['receiver', 'sender', 'device', 'flow', 'source', 'node']:
            typed = [x for x in self.orphan_resources if x['type'] == rtype]
            for r in typed:
                if r['type'] == rtype:
                    self._registry.put_obj(r)
            self._collector._collect()
            for r in typed:
                res = self._registry.get(r['type'] + 's', r['data']['id'])
                self.assertIsNone(res)


    def _setup_flow_in_tree(self, source_parent, device_parent):
        self._registry.set_data({'/health': {'/health/33279d1d-1be9-43eb-9ac5-7c7a5a80a2c5': '0'}})
        for r in self.tree_resources:
            self._registry.put_obj(r)
        obj = {'type': 'flow',
               'data': {
                   'id': 'e9dbe3eb-5ee1-4e90-99e6-7f480cee99d1',
                   'version': '1:1',
                   'label': 'flow-test-with-device',
                   'description': 'flow...',
                   'format': 'urn:x-nmos:format:video',
                   'source_id': source_parent,
                   'parents': []
               }}
        if device_parent is not None:
            obj['data']['device_id'] = device_parent
        self._registry.put_obj(obj)

    def test_flow_with_missing_device(self):
        # add a flow whose Source parent is "alive", but the Device parent is not present
        # the flow should be collected, as it's parent Device is gone.
        self._setup_flow_in_tree('da80a4c4-6e52-46a0-b204-025538d2b25a', 'd3ba8b6b-79ba-4a48-9552-7b8bbca39b4a')
        self._collector._collect()
        self.assertIsNone(self._registry.get('flows', 'e9dbe3eb-5ee1-4e90-99e6-7f480cee99d1'))

    def test_flow_with_missing_source(self):
        # add a flow whose Source parent is not present, but the Device parent is present
        # the flow should NOT be collected, as it's parent Device still exists.
        self._setup_flow_in_tree('14936c71-f81e-410f-86cd-c4de1104ab78', '42263920-39ff-4300-aea7-27bda12e9543')
        self._collector._collect()
        self.assertIsNotNone(self._registry.get('flows', 'e9dbe3eb-5ee1-4e90-99e6-7f480cee99d1'))

    def test_orphaned_flow_with_device_and_source(self):
        # add a flow whose Source AND Device parents are not present
        # the flow should be collected, as it's Device parent is missing
        self._setup_flow_in_tree('cca041e9-b098-4e5d-b4c3-d99400cbfd64', '05ca684e-1569-4be4-87e8-21946c482880')
        self._collector._collect()
        self.assertIsNone(self._registry.get('flows', 'e9dbe3eb-5ee1-4e90-99e6-7f480cee99d1'))

    def test_flow_with_device_and_source(self):
        # add a flow whose Source AND Device parents are both ALIVE
        # the flow should NOT be collected
        self._setup_flow_in_tree('da80a4c4-6e52-46a0-b204-025538d2b25a', '42263920-39ff-4300-aea7-27bda12e9543')
        self._collector._collect()
        self.assertIsNotNone(self._registry.get('flows', 'e9dbe3eb-5ee1-4e90-99e6-7f480cee99d1'))

    def test_flow_with_no_device_id_and_alive_source(self):
        # add a Flow with only a source_id, pointing at an alive source
        # the flow should NOT be collected
        # Here for backward compatibility of v1.0 spec compliance
        self._setup_flow_in_tree('da80a4c4-6e52-46a0-b204-025538d2b25a', None)
        self._collector._collect()
        self.assertIsNotNone(self._registry.get('flows', 'e9dbe3eb-5ee1-4e90-99e6-7f480cee99d1'))

    def test_flow_with_no_device_id_and_dead_source(self):
        # add a Flow with only a source_id, pointing at a dead source
        # the flow should be collected
        # Here for backward compatibility of v1.0 spec compliance
        self._setup_flow_in_tree('de092973-f230-4e84-b087-80e41f0e2940', None)
        self._collector._collect()
        self.assertIsNone(self._registry.get('flows', 'e9dbe3eb-5ee1-4e90-99e6-7f480cee99d1'))

if __name__ == '__main__':
    unittest.main()
