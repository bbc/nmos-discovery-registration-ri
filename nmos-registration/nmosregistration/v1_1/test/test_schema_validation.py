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
import jsonschema

from nmosregistration.v1_1 import schema
from nmosregistration.v1_1.test import util

class SchemaValidCase(unittest.TestCase):

    def assertValidates(self, obj, against):
        try:
            jsonschema.validate(obj, against)
        except jsonschema.ValidationError as ex:
            self.fail("Validation failed: path={} {}".format(
                ex.schema_path,
                "\n".join([str(x) for x in ex.context])))

    def assertInvalid(self, obj, against):
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(obj, against)


class TestFlowSchema(SchemaValidCase):

    @classmethod
    def setUpClass(cls):
        cls.schema = schema.SCHEMA["flow"]

    def test_audio_ok(self):
        obj = util.json_fixture("fixtures/audio-flow.json")
        self.assertValidates(obj, self.schema)

    def test_audio_bad(self):
        obj = util.json_fixture("fixtures/audio-flow.json")
        del obj['source_id']
        self.assertInvalid(obj, self.schema)

    def test_video_ok(self):
        obj = util.json_fixture("fixtures/video-flow.json")
        self.assertValidates(obj, self.schema)

    def test_anc_ok(self):
        obj = util.json_fixture("fixtures/sdi-anc-flow.json")
        self.assertValidates(obj, self.schema)

    def test_2022_ok(self):
        obj = util.json_fixture("fixtures/2022-6-flow.json")
        self.assertValidates(obj, self.schema)

    def test_generic_data_ok(self):
        obj = util.json_fixture("fixtures/data-flow.json")
        self.assertValidates(obj, self.schema)


class TestSourceSchema(SchemaValidCase):

    @classmethod
    def setUpClass(cls):
        cls.schema = schema.SCHEMA["source"]

    def test_generic_refclock_none_ok(self):
        obj = util.json_fixture("fixtures/source-generic-refclock-none.json")
        self.assertValidates(obj, self.schema)

    def test_generic_refclock_ptp_ok(self):
        obj = util.json_fixture("fixtures/source-generic-refclock-ptp.json")
        self.assertValidates(obj, self.schema)

    def test_audio_refclock_none_ok(self):
        obj = util.json_fixture("fixtures/source-audio-refclock-none.json")
        self.assertValidates(obj, self.schema)

    def test_audio_refclock_ptp_ok(self):
        obj = util.json_fixture("fixtures/source-audio-refclock-ptp.json")
        self.assertValidates(obj, self.schema)


class TestNodeSchema(SchemaValidCase):

    @classmethod
    def setUpClass(cls):
        cls.schema = schema.SCHEMA["node"]

    def test_generic_node_ok(self):
        obj = util.json_fixture("fixtures/node.json")
        self.assertValidates(obj, self.schema)


class TestDeviceSchema(SchemaValidCase):

    @classmethod
    def setUpClass(cls):
        cls.schema = schema.SCHEMA["device"]

    def test_generic_device_ok(self):
        obj = util.json_fixture("fixtures/device.json")
        self.assertValidates(obj, self.schema)


class TestSenderSchema(SchemaValidCase):

    @classmethod
    def setUpClass(cls):
        cls.schema = schema.SCHEMA["sender"]

    def test_generic_sender_ok(self):
        obj = util.json_fixture("fixtures/sender.json")
        self.assertValidates(obj, self.schema)


class TestReceiverSchema(SchemaValidCase):

    @classmethod
    def setUpClass(cls):
        cls.schema = schema.SCHEMA["receiver"]

    def test_generic_receiver_ok(self):
        obj = util.json_fixture("fixtures/receiver.json")
        self.assertValidates(obj, self.schema)
