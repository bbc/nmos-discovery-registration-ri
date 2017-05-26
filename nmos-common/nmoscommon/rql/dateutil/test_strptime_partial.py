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
from datetime import datetime
from .util import strptime_partial


class TestPartialStrptime(unittest.TestCase):

    def test_iso_format(self):

        self.assertEqual(strptime_partial('2009'), datetime(2009, 1, 1, 0, 0, 0))
        self.assertEqual(strptime_partial('2009-10'), datetime(2009, 10, 1, 0, 0, 0))
        self.assertEqual(strptime_partial('2009-10-12'), datetime(2009, 10, 12, 0, 0, 0))
        self.assertEqual(strptime_partial('2009-10-12T12'), datetime(2009, 10, 12, 12, 0, 0))
        self.assertEqual(strptime_partial('2009-10-12T12:01'), datetime(2009, 10, 12, 12, 1, 0))
        self.assertEqual(strptime_partial('2009-10-12T12:15:23'), datetime(2009, 10, 12, 12, 15, 23))
        self.assertEqual(strptime_partial('2009-10-12T12:15:23.12345'), datetime(2009, 10, 12, 12, 15, 23, 123450))
        self.assertEqual(strptime_partial('2009-10-12T12:15:23.12345Z'), datetime(2009, 10, 12, 12, 15, 23, 123450))

    def test_custom_format(self):
        self.assertEqual(strptime_partial('10:11', '%H:%M'), datetime(1900, 1, 1, hour=10, minute=11))
        self.assertEqual(strptime_partial('10', '%H:%M'), datetime(1900, 1, 1, hour=10, minute=0))

    def test_no_format(self):
        self.assertEqual(strptime_partial('', ''), datetime(1900, 1, 1))

if __name__ == '__main__':
    unittest.main()
