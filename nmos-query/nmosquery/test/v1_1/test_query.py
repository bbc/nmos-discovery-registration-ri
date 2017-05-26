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

from nmosquery.v1_1 import query

# The following is an example response from `etcd'
NODES_RESPONSE = {u'action': u'get',
 u'node': {u'createdIndex': 6068,
           u'dir': True,
           u'key': u'/resource',
           u'modifiedIndex': 6068,
           u'nodes': [{u'createdIndex': 6068,
                       u'dir': True,
                       u'key': u'/resource/nodes',
                       u'modifiedIndex': 6068,
                       u'nodes': [{u'createdIndex': 6074,
                                   u'key': u'/resource/nodes/efee1ab5-85f1-4ae3-b5d5-3ccc79ae76af',
                                   u'modifiedIndex': 6074,
                                   u'value': u'{"@_apiversion": "v1.1", "href": "http://127.0.0.1:1234/path", "id": "efee1ab5-85f1-4ae3-b5d5-3ccc79ae76af", "label": "test_node", "services": []}'},
                                  {u'createdIndex': 6076,
                                   u'key': u'/resource/nodes/90461aaa-a45a-48f0-ba2e-de51b45ce4ce',
                                   u'modifiedIndex': 6076,
                                   u'value': u'{"@_apiversion": "v1.1", "href": "http://127.0.0.1:1234/path",  "id": "90461aaa-a45a-48f0-ba2e-de51b45ce4ce", "label": "test_node", "services": [{"type": "urn:x-nmos-opensourceprivatenamespace:service:mdnsbridge/v1.0"}]}'},
                                  {u'createdIndex': 6077,
                                   u'key': u'/resource/nodes/007ff4e5-fe72-4c4b-b858-4c5f37dff946',
                                   u'modifiedIndex': 6077,
                                   u'value': u'{"@_apiversion": "v1.1", "href": "http://172.29.176.88:12345/", "id": "007ff4e5-fe72-4c4b-b858-4c5f37dff946", "label": "ap-ch-z420-2.rd.bbc.co.uk", "services": [{"type": "urn:x-nmos-opensourceprivatenamespace:service:pipelinemanager/v1.0"}]}'}]}]}}


class TestQuery(unittest.TestCase):

    def setUp(self):
        self.query = query.Query()

    def test_parse_services_dict_all(self):
        expected = [
            {u"href": "http://127.0.0.1:1234/path",
             u"id": u"efee1ab5-85f1-4ae3-b5d5-3ccc79ae76af", u"label": u"test_node", "services": []},
            {u"href": "http://172.29.176.88:12345/",
             u"id": u"007ff4e5-fe72-4c4b-b858-4c5f37dff946", u"label": u"ap-ch-z420-2.rd.bbc.co.uk", "services": [{"type": "urn:x-nmos-opensourceprivatenamespace:service:pipelinemanager/v1.0"}]},
            {u"href": u"http://127.0.0.1:1234/path",
             u"id": u"90461aaa-a45a-48f0-ba2e-de51b45ce4ce", u"label": u"test_node", "services": [{"type": "urn:x-nmos-opensourceprivatenamespace:service:mdnsbridge/v1.0"}]}
        ]
        actual = self.query.parse_services_dict(NODES_RESPONSE, "nodes/", {}, verbose=True)
        self.assertItemsEqual(expected, actual)

    def test_parse_services_dict_condensed(self):
        """ When not in verbose mode, return just node IDs """
        expected = [u"efee1ab5-85f1-4ae3-b5d5-3ccc79ae76af",
                    u"007ff4e5-fe72-4c4b-b858-4c5f37dff946",
                    u"90461aaa-a45a-48f0-ba2e-de51b45ce4ce"]
        actual = self.query.parse_services_dict(NODES_RESPONSE, "nodes/", {}, verbose=False)
        self.assertItemsEqual(expected, actual)

    def test_parse_services_dict_single(self):
        expected = [{u'href': u'http://127.0.0.1:1234/path',
                     u'id': u'90461aaa-a45a-48f0-ba2e-de51b45ce4ce', u'label': u'test_node', "services": [{"type": "urn:x-nmos-opensourceprivatenamespace:service:mdnsbridge/v1.0"}]}]
        actual = self.query.parse_services_dict(NODES_RESPONSE, "nodes/90461aaa-a45a-48f0-ba2e-de51b45ce4ce", {}, verbose=True)
        self.assertItemsEqual(expected, actual)

    def test_parse_services_dict_with_args_no_result(self):
        args = {'label': 'nonsense'}
        expected = []
        actual = self.query.parse_services_dict(NODES_RESPONSE, "nodes/90461aaa-a45a-48f0-ba2e-de51b45ce4ce", args, verbose=True)
        self.assertItemsEqual(expected, actual)

    def test_parse_services_dict_with_args_one_result(self):
        args = {'label': 'ap-ch-z420-2.rd.bbc.co.uk'}
        expected = [{u"href": "http://172.29.176.88:12345/",
                     u"id": u"007ff4e5-fe72-4c4b-b858-4c5f37dff946", u"label": u"ap-ch-z420-2.rd.bbc.co.uk", "services": [{"type": "urn:x-nmos-opensourceprivatenamespace:service:pipelinemanager/v1.0"}]}]
        actual = self.query.parse_services_dict(NODES_RESPONSE, "nodes/", args, verbose=True)
        self.assertItemsEqual(expected, actual)

    def test_parse_services_dict_with_array_args_one_result(self):
        args = {'services.type': 'urn:x-nmos-opensourceprivatenamespace:service:pipelinemanager/v1.0'}
        expected = [{u"href": "http://172.29.176.88:12345/",
                     u"id": u"007ff4e5-fe72-4c4b-b858-4c5f37dff946", u"label": u"ap-ch-z420-2.rd.bbc.co.uk", "services": [{"type": "urn:x-nmos-opensourceprivatenamespace:service:pipelinemanager/v1.0"}]}]
        actual = self.query.parse_services_dict(NODES_RESPONSE, "nodes/", args, verbose=True)
        self.assertItemsEqual(expected, actual)

    def test_parse_services_dict_with_args_two_results(self):
        expected = [
            {u"href": "http://127.0.0.1:1234/path",
             u"id": u"efee1ab5-85f1-4ae3-b5d5-3ccc79ae76af", u"label": u"test_node", "services": []},
            {u"href": u"http://127.0.0.1:1234/path",
             u"id": u"90461aaa-a45a-48f0-ba2e-de51b45ce4ce", u"label": u"test_node", "services": [{"type": "urn:x-nmos-opensourceprivatenamespace:service:mdnsbridge/v1.0"}]}
        ]
        actual = self.query.parse_services_dict(NODES_RESPONSE, "nodes/", {'label': 'test_node'}, verbose=True)
        self.assertItemsEqual(expected, actual)

    def test_summarise(self):
        """ it should leave structure alone """
        self.assertEqual({}, self.query._summarise({}))
        self.assertEqual({}, self.query._summarise(None))
        self.assertEqual({"foo": 1, "bar": 2}, self.query._summarise({"foo": 1, "bar": 2}))

    def test_matches_path(self):
        passes = [
            ("a", "a"),
            ("a", None),
            ("http://localhost:8870/nodes/007ff4e5-fe72-4c4b-b858-4c5f37dff946/", "nodes"),
            ("resource/nodes/007ff4e5-fe72-4c4b-b858-4c5f37dff946/", "nodes/007ff4e5-fe72-4c4b-b858-4c5f37dff946"),
            ("nodes/007ff4e5-fe72-4c4b-b858-4c5f37dff946", "nodes"),
            ("nodes/007ff4e5-fe72-4c4b-b858-4c5f37dff946", "007ff4e5-fe72-4c4b-b858-4c5f37dff94"),
            ("/resource/flows/d90755e4-9919-4159-9715-30ec1f084978", "flows"),
            # This next one is kind of odd. Not sure an empty pattern should match, but follows
            # what the previous code did (regex would have been /.*().*/)
            ("nodes/007ff4e5-fe72-4c4b-b858-4c5f37dff946", ""),
        ]

        fails = [
            ("a", "b"),
            ("http://localhost:8870/nodes/007ff4e5-fe72-4c4b-b858-4c5f37dff946/", "flows"),
            ("resource/nodes/007ff4e5-fe72-4c4b-b858-4c5f37dff946/", "nodes/01234567"),
            ("nodes/007ff4e5-fe72-4c4b-b858-4c5f37dff946", "sources"),
            ("/resource/flows/d90755e4-9919-4159-9715-30ec1f084978", "nodes")
        ]

        for args in passes:
            self.assertTrue(self.query._matches_path(*args), args)

        for args in fails:
            self.assertFalse(self.query._matches_path(*args), args)
