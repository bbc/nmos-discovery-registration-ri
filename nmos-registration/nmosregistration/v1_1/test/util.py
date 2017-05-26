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

import json
import os


def load_fixture(filename, process=id):
    my_dir = os.path.dirname(os.path.realpath(__file__))
    print "LOAD", os.path.join(my_dir, filename)
    with open(os.path.join(my_dir, filename), "r") as fh:
        return process(fh)


def json_fixture(filename):
    """
    Load a test fixture from the current directory as a JSON object.
    """
    return load_fixture(filename, process=json.load)
