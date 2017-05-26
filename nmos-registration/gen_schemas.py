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

import sys
import json
import pprint

def get_schema(name, dir):

    def process(obj):
        if isinstance(obj, dict):
            if len(obj) == 1 and "$ref" in obj:
                return get_schema(obj['$ref'], dir)
            return {k: process(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [process(x) for x in obj]
        else:
            return obj

    local = {}
    filename = "{}/{}".format(dir, name)
    with open(filename, 'r') as fh:
        local = process(json.load(fh))
    return local


if __name__ == '__main__':
    supported_types = ["node", "device", "source", "flow", "sender", "receiver"]
    schema_dir = sys.argv[1]
    schema = {}

    for name in supported_types:
        schema[name] = get_schema("{}.json".format(name), schema_dir)

    print '"""'
    print 'Defines mapping of resource types to schema'
    print 'Generated. Do not edit!'
    print '"""'
    print 'SCHEMA = ', pprint.pprint(schema)
