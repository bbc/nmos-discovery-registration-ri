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

from nmosquery import util

class TestQueryUtils(unittest.TestCase):

    def test_get_resourcetypes_extract(self):
        """ it should extract the type unmolested """
        self.assertEqual("nodes", util.get_resourcetypes("/resource/nodes"))
        self.assertEqual("dests", util.get_resourcetypes("http://localhost:8080/resource/dests/"))
        self.assertEqual("flows", util.get_resourcetypes("/resource/flows/ABCDEF"))
        self.assertEqual("nodes", util.get_resourcetypes("http://localhost:8080/resource/nodes/ABCDEF/"))

    def test_get_resourcetypes_none(self):
        """ no match should yield no type """
        self.assertEqual("", util.get_resourcetypes("http://localhost:8080/rubbish/nodes"))
        self.assertEqual("", util.get_resourcetypes("resource/flows/ABCDEF"))
        self.assertEqual("", util.get_resourcetypes("/resources/flows/ABCDEF"))

    def test_translate_resourcetypes_type(self):
        """ it extracts the type only if no uid is given """
        self.assertEqual("nodes", util.translate_resourcetypes("/nodes"))
        self.assertEqual("nodes", util.translate_resourcetypes("/nodes/"))
        self.assertEqual("banana", util.translate_resourcetypes("/banana"))

    def test_translate_resourcetypes_type_uid(self):
        """ it extracts the type and uid, and lowercases the uid """
        self.assertEqual("nodes/007ff4e5-fe72-4c4b-b858-4c5f37dff946",
                         util.translate_resourcetypes("/nodes/007ff4e5-fe72-4c4b-b858-4c5f37dff946/"))
        self.assertEqual("nodes/007ff4e5-fe72-4c4b-b858-4c5f37dff946",
                         util.translate_resourcetypes("/nodes/007FF4E5-FE72-4C4B-B858-4C5F37DFF946"))
