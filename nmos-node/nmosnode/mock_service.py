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

from registry import FacadeRegistry
import gevent

class MockBackend:
    def __init__(self, registry, node_id):

        self.registry = registry
        self.node_id = node_id
        self.service = {}
        self.service['name'] = "Node-Mock-Backend"
        self.service['type'] = "x-mock"
        self.service['pid'] = 999
        self.service['href'] = "http://mock-url/mock-url"
        self.service['proxyHref'] = "http://mock-url/mock-url"

        mocks = {}

        mocks['mockSource'] = {
                      "max_api_version" :"v1.1",
                      "description": "Mock Source Description",
                      "format": "urn:x-nmos:format:video",
                      "tags": {
                               "SourceDeviceType": [
                                                    "HD Camera"
                                                    ],
                               "host": [
                                        "host1"
                                        ],
                               "Location": [
                                            "Location 1"
                                            ]
                               },
                      "caps": {},
                      "version": "1441722516:851371645",
                      "parents": [],
                          "label": "Mock Source Label",
                          "id": "c23c6a65-8e91-4f6c-a484-046363dbca29",
                          "device_id": "05017e08-b329-45f9-a566-a3f99cc11e4d",
                          "clock_name": "clk1"
                    }

        mocks['mockFlow'] =  {
                     "description": "Mock Flow Description",
                     "tags": {},
                     "format": "urn:x-nmos:format:video",
                    "label": "Mock Flow Label",
                    "version": "1441704616:587121295",
                    "parents": [],
                    "source_id": "c23c6a65-8e91-4f6c-a484-046363dbca29",
                    "device_id": "05017e08-b329-45f9-a566-a3f99cc11e4d",
                    "id": "5fbec3b1-1b0f-417d-9059-8b94a47197ed",
                    "media_type": "video/raw",
                    "frame_width": 1920,
                    "frame_height": 1080,
                    "interlace_mode": "interlaced_tff",
                    "colorspace": "BT709",
                    "components": [
                        {
                            "name": "Y",
                            "width": 1920,
                            "height": 1080,
                            "bit_depth": 10
                        },
                        {
                            "name": "Cb",
                            "width": 960,
                            "height": 1080,
                            "bit_depth": 10
                        },
                        {
                            "name": "Cr",
                            "width": 960,
                            "height": 1080,
                            "bit_depth": 10
                        }
                    ]
                    }

        mocks['mockDevice'] = {
        "receivers": [
            "1eb53d65-ac83-441c-86f6-9b27df30ef0c"
        ],
        "label": "Mock Device Label",
        "description": "Mock Device Description",
        "tags": {},
        "version": "1441704514:993221361",
        "id": "05017e08-b329-45f9-a566-a3f99cc11e4d",
        "type": "urn:x-nmos:device:pipeline",
        "senders": [],
        "node_id": self.node_id,
        "controls": []
        }

        mocks['mockSender'] = {
                "description": "Mock Sender Description", 
                "label": "Mock Sender Label", 
                "version": "1441704616:890020555", 
                "manifest_href": "http://mock-url/sdp/stream.sdp", 
                "flow_id": "5fbec3b1-1b0f-417d-9059-8b94a47197ed", 
                "id": "d7aa5a30-681d-4e72-92fb-f0ba0f6f4c3e", 
                "transport": "urn:x-nmos:transport:rtp.mcast", 
                "device_id": "05017e08-b329-45f9-a566-a3f99cc11e4d",
                "tags": {}
                    }

        mocks['mockReceiver'] = {
            "description": "Mock RTP Receiver Description", 
            "tags": {
                "Location": [
                    "Location 1"
                ]
            }, 
            "format": "urn:x-nmos:format:video", 
            "caps": {
                "media_types": [
                    "video/raw"
                ]
            },
            "device_id": "05017e08-b329-45f9-a566-a3f99cc11e4d", 
            "version": "1441895693:480000000", 
            "label": "Mock RTP Receiver Label", 
            "id": "1eb53d65-ac83-441c-86f6-9b27df30ef0c", 
            "transport": "urn:x-nmos:transport:rtp", 
            "subscription": {
                "sender_id": "d7aa5a30-681d-4e72-92fb-f0ba0f6f4c3e"
            }
        }

        self.dataGreenlet = gevent.spawn(self._runMockService, self.registry, self.service, mocks)
        self.heartbeatGreenlet = gevent.spawn(self._runHeartbeat, self.registry, self.service)

    def _runMockService(self, registry, service, mocks):
        registry.register_service(service['name'], service['type'], service['pid'], service['href'], service['proxyHref'])
        registry.register_resource(service['name'], service['pid'], "device", mocks['mockDevice']['id'], mocks['mockDevice'])
        registry.register_resource(service['name'], service['pid'], "source", mocks['mockSource']['id'], mocks['mockSource'])
        registry.register_resource(service['name'], service['pid'], "flow", mocks['mockFlow']['id'], mocks['mockFlow'])
        registry.register_resource(service['name'], service['pid'], "sender", mocks['mockSender']['id'], mocks['mockSender'])
        registry.register_resource(service['name'], service['pid'], "receiver", mocks['mockReceiver']['id'], mocks['mockReceiver'])

        
    def _runHeartbeat(self, registry, service):
        while(True):
            gevent.sleep(11)
            registry.heartbeat_service(service['name'], service['pid'])
