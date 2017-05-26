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
import time
import jsonschema

from flask import request, abort, make_response

from nmoscommon.webapi import route, jsonify, traceback, returns_json

from nmosregistration.etcd_util import etcd_unpack
from nmosregistration.modifier import RegModifier
from nmosregistration.common import schema

VALID_TYPES = ['node', 'source', 'flow', 'device', "receiver", "sender"]
TIMELINE_MAPPING = {'flowsegment': 'flows'}
REGISTRY_PORT = 4001
NODE_SEEN_TTL = 12  # seconds until a node considered "dead".


class RoutesCommon(object):

    def __init__(self, logger, registry, api_version="v1.0", api_schema=schema):
        self.logger = logger
        self.registry = registry
        self.modifier = RegModifier(logger=self.logger)
        self.api_version = api_version
        self.api_schema = api_schema

    def _ensure_parents(self, resource_type, resource):
        if resource_type == "device":
            if not self.registry.resource_exists("nodes", resource["node_id"]):
                return False, "Node {} does not exist".format(resource["node_id"])
        elif resource_type in ["receiver", "sender", "source"]:
            if not self.registry.resource_exists("devices", resource["device_id"]):
                return False, "Device {} does not exist".format(resource["device_id"])
        elif resource_type == "flow":
            if not self.registry.resource_exists("sources", resource["source_id"]):
                return False, "Source {} does not exist".format(resource["source_id"])
        return True, ""

    def _add_resource(self, body):
        """Register a resource."""
        jobj = json.loads(body)

        # Put resource to registry, return HTTP response
        try:
            for key in ['type', 'data']:
                if key not in jobj:
                    abort(400, 'Attribute "{}" is mandatory for "resource" type'.format(key))

            # 'id' is always mandatory
            if 'id' not in jobj['data']:
                abort(400, 'Attribute "id" is mandatory for "node" type')

            modified = self.modifier.modify(jobj)
            resource_type = modified['type']
            resource_data = modified['data']

            if resource_type not in VALID_TYPES:
                abort(400, 'resource: "type" attribute is malformed, expected one of {}'.format(VALID_TYPES))

            resource_id = resource_data['id']
            resource_type_plural = resource_type + "s"

            # Validate against the schema
            jsonschema.validate(resource_data, self.api_schema.SCHEMA[resource_type])

            # Ensure any parents are present
            ok, message = self._ensure_parents(resource_type, resource_data)
            if not ok:
                abort(400, message)

            # Add in the API version we are registering with
            resource_data['@_apiversion'] = self.api_version

            reg_response = self.registry.put(resource_type_plural, resource_id, json.dumps(resource_data), port=REGISTRY_PORT)
            reg_response.autocorrect_location_header = False
            reg_response.headers["Location"] = "/x-nmos/registration/{}/resource/{}/{}/".format(self.api_version, resource_type_plural, resource_id)

            self.logger.writeInfo("register {} {}: {}".format(resource_type, resource_id, reg_response.status_code))

            # Add an initial heartbeat if this is a node resource
            if resource_type == 'node':
                hb_r = self.registry.put_health(resource_id, int(time.time()), ttl=NODE_SEEN_TTL, port=REGISTRY_PORT)
                if hb_r.status_code not in [204, 201, 200]:
                    self.logger.writeWarning("could not add initial heartbeat: {}".format(hb_r))
                    return hb_r

            return reg_response

        except jsonschema.ValidationError as ex:
            self.logger.writeWarning("Validation error: {}, in {}".format(ex.message, jobj))
            abort(400, ex.message)

        except self.registry.RegistryUnavailable:
            self.logger.writeWarning("Could not put resource to registry.")
            abort(500, "Registry unavailable")

    def _health(self, node_id):
        """
        Perform health check for particular resource
        """

        # check node is registered
        try:
            check_r = self.registry.get("nodes", node_id, port=REGISTRY_PORT)
        except self.registry.RegistryUnavailable:
            self.logger.writeWarning("Registry unavailable.")
            abort(500, "Registry unavailable")

        if check_r is None:
            self.logger.writeDebug("heartbeat: node '{}' not registered".format(node_id))
            return 404

        try:
            r = self.registry.put_health(node_id, int(time.time()), ttl=NODE_SEEN_TTL, port=REGISTRY_PORT)
        except self.registry.RegistryUnavailable:
            self.logger.writeWarning("Registry unavailable.")
            abort(500, "Registry unavailable")

        if r.status_code == 404:
            data = json.loads(r.data)
            if 'errorCode' in data:
                if int(data['errorCode']) == 100:  # key does not exist, so node has been culled
                    self.logger.writeDebug("heartbeat: node '{}' did not exist".format(node_id))
                    return 404

        elif r.status_code not in [201,200]:
            self.logger.writeWarning("couldn't register heartbeat ({}: {})".format(r.status_code, r.reason))
            return 404

        return 204

    def _delete(self, resource_type, resource_id):
        """
        Delete a particular resource from the registry
        """
        # TODO: there is an issue here; when a node is deleted, do we
        # tidy up it's resources?  Assume for now: (1) the facade has
        # cleaned up any resources it registered (in a clean shutdown)
        # (2) if the shutdown was not clean, client apps will notice
        # the node health check and act accordingly.
        # Stale data will still need to be cleaned up eventually.
        self.logger.writeInfo("unregister {} {}".format(resource_type, resource_id))
        try:
            r = self.registry.delete(resource_type, resource_id, port=REGISTRY_PORT)
        except self.registry.RegistryUnavailable:
            self.logger.writeWarning("Couldn't delete resource. Registry unavailable.")
            abort(500, "Registry unavailable")
        return r

    @route('/')
    def __versionroot(self):
        return [ 'resource', 'health/' ]

    @route('/resource', methods=['GET', 'POST'], auto_json=False)
    def __resource(self):
        if request.method == 'POST':
            r = self._add_resource(request.get_data())
            if r.status_code/100 == 2:
                representation = json.loads(r.json()["node"]["value"])
                # strip out any metadata
                remove_keys = (x for x in representation.keys() if x.startswith("@_"))
                for k in remove_keys:
                    del representation[k]
                response = make_response(jsonify(representation), r.status_code)
                response.autocorrect_location_header = False
                response.headers["Location"] = r.headers.get("Location", "")
                return response

            else:
                self.logger.writeInfo("POST resource response: {}".format(r.content))
                abort(r.status_code)
        else:
            return jsonify([ "{}s".format(x) for x in VALID_TYPES ])

    @route('/resource/<resource_type>')
    def __resource_type(self, resource_type):
        try:
            r = self.registry.getresources(resource_type)
        except:
            traceback.print_exc()
            raise
        return r

    @route('/timeline', methods=['GET', 'POST'], auto_json=False)
    def __timeline(self):
        if request.method == 'POST':
            payload = json.loads(request.get_data())

            def mandatory(data, key):
                if key not in data:
                    abort(400, description="Required '{}' attribute missing".format(key))
                return data[key]

            rtype = mandatory(payload, 'type')          # which type of parent does this belong to?
            flow_id = mandatory(payload['data'], 'id')          # parent id (which flow?)
            store_id = mandatory(payload['data'], 'store_id')   # container (where?)
            min_ts = mandatory(payload['data'], 'min_ts_utc')   # 'in' time

            # map the type passed in to an internal storage type
            if rtype not in TIMELINE_MAPPING:
                abort(400, "No mapping for type {}".format(rtype))
            mapped_type = TIMELINE_MAPPING[rtype]

            # key for storage in registry
            key = "timeline/{}/{}/{}/{}".format(mapped_type, flow_id, store_id, min_ts)

            resp = self.registry.put_raw(key, json.dumps(payload['data']))

            if resp.status_code not in [200, 201]:
                abort(400, "Bad response from etcd: {}".format(resp.content))
            response = make_response('', resp.status_code)

            # Location header allows DELETE to remove, as below
            response.autocorrect_location_header = False
            response.headers["location"] = "/{}".format(key)
            return response

        elif request.method == 'GET':
            # debug path, used internally
            @returns_json
            def payload():
                return ['flows']
            return payload()

    @route('/timeline/<rtype>', methods=['GET'])
    def __timeline_type(self, rtype):
        rev_mapping = dict((v, k) for k, v in TIMELINE_MAPPING.iteritems())
        if rtype not in rev_mapping:
            abort(400, "No mapping for type '{}'".format(rtype))
        reg_key = "timeline/{}".format(rtype)
        reg_response = self.registry.get_raw(reg_key, recurse=False)
        if reg_response.status_code != 200:
            abort(400, "Bad response from registry: {}".format(reg_response.content))
        timeline = etcd_unpack(reg_response.json())
        return [x[len('/timeline/flows/'):] for x in timeline['/timeline/flows'].keys()]

    @route('/timeline/<type>/<path:key>', methods=['DELETE'])
    def __timeline_delete(self, type, key):
        return self.registry.delete_raw('timeline/{}/{}'.format(type, key))

    @route('/resource/<resource_type>/<rname>', methods=['GET', 'DELETE'])
    def __resource_type_name(self, resource_type, rname):
        if request.method == 'DELETE':
            r = self._delete(resource_type, rname)
            if r.status_code/100 == 2:
                return (204, '')
            abort(r.status_code)
        else:
            try:
                r = self.registry.get(resource_type, rname)
            except:
                traceback.print_exc()
                raise

            if r is None:
                abort(404)
            return r

    @route('/health/')
    def __health(self):
        return ['nodes/',]

    @route('/health/nodes/')
    def __health_type(self):
        return self.registry.getresources('nodes')

    @route('/health/nodes/<k>', methods=['GET', 'POST'])
    def __health_type_name(self, k):
        if request.method == 'POST':
            r = self._health(k)
            if r != 204:
                abort(404)

        try:
            health = self.registry.get_health(k, port=REGISTRY_PORT)
        except self.registry.RegistryUnavailable:
            abort(500, "Registry unavailable")

        if health is None:
            abort(404)
        else:
            return { 'health' : health }
