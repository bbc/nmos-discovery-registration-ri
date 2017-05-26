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

"""
The modifier performs changes to the incoming data to ensure it conforms to
internal standard for the registry
"""

import types


class CustomModifier(object):
    def modify(self, data):
        return data


class UuidModifier(CustomModifier):
    def modify(self, data):
        if data is not None:
            return data.lower()
        else:
            return data


GENERAL_SCHEMA = {
    'data': {
        'id': UuidModifier
    }
}

SCHEMA = {
    'node': {
    },
    'source': {
        'data': {
            'node_id': UuidModifier
        }
    },
    'flow': {
        'data': {
            'node_id': UuidModifier,
            'source_id': UuidModifier
        }
    },
    'device': {
        'data': {
            'node_id': UuidModifier,
            'receivers': [
                UuidModifier
            ],
            'senders': [
                UuidModifier
            ]
        }
    },
    'sender': {
        'data': {
            'node_id': UuidModifier,
            'device_id': UuidModifier,
            'flow_id': UuidModifier
        }
    },
    'receiver': {
        'data': {
            'node_id': UuidModifier,
            'device_id': UuidModifier,
            'subscription': {
                'sender_id': UuidModifier
            }
        }
    }
}


class RegModifier(object):
    def __init__(self, logger):
        self.logger = logger

    def modify(self, data):
        """
        Check data against any applicable schema(s).
        Returns: Corrected data
        """
        # Check against the general schema
        resource = self._modify_against_schema(data, GENERAL_SCHEMA)

        # Check specifics for object type
        specific_schema = SCHEMA.get(data['type'], None)
        if specific_schema is not None:
            data = self._modify_against_schema(resource, specific_schema)
        else:
            self.logger.writeInfo("No specific schema for validating resource of type {}".format(data['type']))

        return data

    def _modify_against_schema(self, data, schema):
        for k, vtype in schema.iteritems():
            if k in data.keys():
                if type(vtype) is list:
                    for child_schema in vtype:
                        if type(child_schema) is dict:
                            # Dict describes a subresource which has a schema
                            for child_data in data[k]:
                                data[k][child_data] = self._modify_against_schema(child_data, child_schema)
                        elif isinstance(child_schema, (type, types.ClassType)) and issubclass(child_schema, CustomModifier) and len(vtype) == 1:
                            # List of attributes, each with the same modifier
                            custom = child_schema()
                            for index, val in enumerate(data[k]):
                                data[k][index] = custom.modify(val)
                elif isinstance(vtype, (type, types.ClassType)) and issubclass(vtype, CustomModifier):
                    custom = vtype()
                    data[k] = custom.modify(data[k])
                elif type(vtype) is dict:
                    data[k] = self._modify_against_schema(data[k], schema[k])
                else:
                    raise Exception("Unrecognised schema check: {}".format(vtype))
        return data
