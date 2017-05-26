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
import uuid
import copy

import nmosregistration.modifier as modifier

class StdoutLogger:
    def writeDebug(self, s):
        print(s)

    def writeError(self, s):
        print(s)


class TestUuidCheck(unittest.TestCase):

    def setUp(self):
        self.check = modifier.UuidModifier()

    def test_lower(self):
        for i in range(100):
            test_uuid = unicode(uuid.uuid4())
            self.assertEqual(self.check.modify(test_uuid), test_uuid)

    def test_upper(self):
        for i in range(100):
            orig_uuid = unicode(uuid.uuid4())
            test_uuid = orig_uuid.upper()
            self.assertEqual(self.check.modify(test_uuid), orig_uuid)


class TestModification(unittest.TestCase):

    def setUp(self):
        self.modifier = modifier.RegModifier(logger=StdoutLogger())

    def _make_flow_resource(self):
        return {
            "type": u"flow",
            "data": {
                "format": u"urn:x-nmos:format:video",
                "tags": {
                    u"host": [u"ap-z820-1"],
                    u"location": [u"MCUK"]
                },
                "label": u"MCUK F55 UHD",
                "source_id": u"042a4126-0208-443d-bda6-833ffc27ed51",
                "node_id": u"a6b4e145-6110-4857-997f-c35165eb0a14",
                "id": u"d553e551-e5df-4e46-8973-45f4cacf1172"
            }
        }

    def _make_device_resource(self):
        return {
            "type": u"device",
            "data": {
                "label": u"My Device Name",
                "node_id": u"f116b7b5-0fd6-4ea5-bd46-018f7d7c3eaf",
                "id": u"bbef23eb-5cfd-4b0c-a0e9-92406d4b42f6",
                "receivers": [
                    u"e7684263-51bf-4c69-baf8-43932e453c66",
                    u"c5cb10f9-2584-4f49-a1da-6a52903fd990",
                    u"73801e4d-6787-4e48-a39c-2a512c00527a"
                ],
                "senders": [
                    u"9aba4e98-de16-47dc-980f-c4dd3bcbb27b"
                ]
            }
        }

    def _make_receiver_resource(self):
        return {
            "type": u"receiver",
            "data": {
                "description": u"",
                "tags": [],
                "format": u"urn:x-nmos:format:video",
                "label": u"ap-z220-0 RTPRx",
                "node_id": u"3b8be755-08ff-452b-b217-c9151eb21193",
                "device_id": u"31430634-beaa-41ed-94b4-ab4c06e81764",
                "caps": "",
                "id": u"c969b9f7-1304-42bc-99be-f33647ccfb97",
                "transport": u"urn:x-nmos:transport:rtp",
                "subscription": {
                    "sender_id": u""
                }
            }
        }

    def test_valid_flow(self):
        resource = self._make_flow_resource()
        self.assertEqual(self.modifier.modify(copy.deepcopy(resource)), resource)

    def test_valid_device(self):
        resource = self._make_device_resource()
        self.assertEqual(self.modifier.modify(copy.deepcopy(resource)), resource)

    def test_valid_receiver(self):
        resource = self._make_receiver_resource()
        self.assertEqual(self.modifier.modify(copy.deepcopy(resource)), resource)

    def test_corrected_device(self):
        orig_resource = self._make_device_resource()
        resource = copy.deepcopy(orig_resource)
        resource["data"]["senders"][0] = resource["data"]["senders"][0].upper()
        self.assertEqual(orig_resource, self.modifier.modify(resource))

    def test_corrected_flow(self):
        orig_resource = self._make_flow_resource()
        resource = copy.deepcopy(orig_resource)
        resource["data"]["id"] = resource["data"]["id"].upper()
        self.assertEqual(orig_resource, self.modifier.modify(resource))

if __name__ == '__main__':
    unittest.main()
