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
    def __init__(self, registry):

        self.registry = registry
        self.service = {}
        self.service['name'] = "Node-Mock-Backend"
        self.service['type'] = "x-mock"
        self.service['pid'] = 999
        self.service['href'] = "http://localhost/bobbins"
        self.service['proxyHref'] = "localhost/bobbins"

        mocks = {}

        mocks['mockSource'] = {
                      "max_api_version" :"v1.1",
                      "description": "Capture Card Source Video",
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
                          "label": "CaptureCardSourceVideo",
                          "id": "c23c6a65-8e91-4f6c-a484-046363dbca29",
                          "device_id": "65fa8c20-890e-4b86-87b2-cfd9df91b7f8",
                          "clock_name": "clk1"
                    }

        mocks['mockFlow'] =  {
                     "description": "Test Card",
                     "tags": {},
                     "format": "urn:x-nmos:format:video",
                    "label": "Test Card",
                    "version": "1441704616:587121295",
                    "parents": [],
                    "source_id": "02c46999-d532-4c52-905f-2e368a2af6cb",
                    "device_id": "9126cc2f-4c26-4c9b-a6cd-93c4381c9be5",
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

        mocks['mockDeviceA'] = {
        "receivers": [],
        "label": "pipeline 3 default device",
        "description": "pipeline 3 default device",
        "tags": {},
        "version": "1441704616:592733242",
        "id": "9126cc2f-4c26-4c9b-a6cd-93c4381c9be5",
        "type": "urn:x-nmos:device:pipeline",
        "senders": [
            "d7aa5a30-681d-4e72-92fb-f0ba0f6f4c3e"
        ],
        "node_id": "3b8be755-08ff-452b-b217-c9151eb21193",
        "controls": [
            {
                "type": "urn:x-manufacturer:control:generic",
                "href": "wss://154.67.63.2:4535"
            }
        ]
                       }
    
        mocks['mockDeviceB'] = {
        "receivers": [
            "1eb53d65-ac83-441c-86f6-9b27df30ef0c"
        ],
        "label": "pipeline 2 default device",
        "description": "pipeline 2 default device",
        "tags": {},
        "version": "1441704514:993221361",
        "id": "05017e08-b329-45f9-a566-a3f99cc11e4d",
        "type": "urn:x-nmos:device:pipeline",
        "senders": [],
        "node_id": "3b8be755-08ff-452b-b217-c9151eb21193",
        "controls": []
        }

        mocks['mockSender'] = {
                "description": "Test Card", 
                "label": "Test Card", 
                "version": "1441704616:890020555", 
                "manifest_href": "http://172.29.80.65:12345/x-nmos/node/v1.1/self/pipelinemanager/run/pipeline/3/pipel/ipp_rtptxfefa/misc/sdp/stream.sdp", 
                "flow_id": "5fbec3b1-1b0f-417d-9059-8b94a47197ed", 
                "id": "d7aa5a30-681d-4e72-92fb-f0ba0f6f4c3e", 
                "transport": "urn:x-nmos:transport:rtp.mcast", 
                "device_id": "9126cc2f-4c26-4c9b-a6cd-93c4381c9be5",
                "tags": {}
                    }

        mocks['mockReceiver'] = {
            "description": "RTP receiver 1", 
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
            "device_id": "0d0cb97e-b96a-4a39-887f-d491492d9081", 
            "version": "1441895693:480000000", 
            "label": "Viewer 1", 
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
        while(True):
             registry.register_resource(service['name'], service['pid'], "source", mocks['mockSource']['id'], mocks['mockSource'])
             gevent.sleep(10)
             registry.unregister_resource(service['name'], service['pid'], "source", mocks['mockSource']['id'])
             gevent.sleep(4)
        registry.unregister_service(service['name'], service['pid'])
        
    def _runHeartbeat(self, registry, service):
        while(True):
            gevent.sleep(11)
            registry.heartbeat_service(service['name'], service['pid'])
