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

import gevent

from nmoscommon.logger import Logger


INTERVAL = 10
TIMEOUT = 9
LOCK_TIMEOUT = 15


class TooLong(Exception):
    pass


class GarbageCollect(object):

    parent_tab = {
        'devices':   [('nodes', 'node_id')],
        'senders':   [('devices', 'device_id')],
        'receivers': [('devices', 'device_id')],
        'sources':   [('devices', 'device_id')],
        'flows':     [('devices', 'device_id'), ('sources', 'source_id')]
    }

    def __init__(self, registry, identifier, logger=None, interval=INTERVAL):
        """
        interval
            Number of seconds between checks / collections. An interval of '0'
            means 'never check'.
        """
        self.registry = registry
        self.logger = Logger("garbage_collect", logger)
        self.identifier = identifier
        if interval > 0:
            gevent.spawn_later(interval, self.garbage_collect)

    def garbage_collect(self):
        # Check to see if garbage collection hasn't been done recently (by another aggregator)
        # Uses ETCD's prevExist=false function
        # See https://github.com/coreos/etcd/blob/master/Documentation/api.md#atomic-compare-and-swap
        try:
            flag = self.registry.put_garbage_collection_flag(host=self.identifier, ttl=LOCK_TIMEOUT)
            if flag.status_code != 201:
                self.logger.writeDebug("Not collecting - another collector has recently collected")
                return

            # Kick off a collection with a specified timeout.
            try:
                with gevent.Timeout(TIMEOUT, TooLong):
                    self._collect()

            finally:
                self.logger.writeDebug("remove flag")
                self._remove_flag()

        except Exception as e:
            self.logger.writeError("Could not write garbage collect flag: {}".format(e))

        finally:
            # Always schedule another
            gevent.spawn_later(INTERVAL, self.garbage_collect)
            self.logger.writeDebug("scheduled...")

    def _collect(self):
        try:
            self.logger.writeDebug("Collecting: {}".format(self.identifier))

            # create list of nodes still alive
            alive_nodes = []

            health_dict = self.registry.get_healths()
            for h in health_dict.get('/health', {}).keys():
                node_name = h.split('/')[-1]
                alive_nodes.append(node_name)

            # TODO: GETs... maybe getting the whole response in one go is better?
            # Maybe doing these async is a good idea? For now, this suffices.
            all_types = ["nodes", "devices", "senders", "receivers", "sources", "flows"]
            resources = {rtype: self.registry.get_all(rtype) for rtype in all_types}

            # Get a flat list of (type, resource) pairs for existing resources
            # TODO: combine with above
            all_resources = []
            for res_type, res in resources.items():
                all_resources += [(res_type, x) for x in res]

            # Initialise the removal queue with any dead nodes
            nodes = [x.strip('/') for x in self.registry.getresources("nodes")]

            # TODO: already have this above...
            kill_q = [('nodes', node_id) for node_id in nodes if node_id not in alive_nodes]

            # Create a list of (type, id) pairs of resources that should be removed.
            to_kill = []

            # Find orphaned resources
            kill_q += self.__find_dead_resources(all_resources, to_kill)

            # Process the removal queue.
            while kill_q:
                gevent.sleep(0.0)

                # Add these resources to the list of removals
                to_kill += kill_q

                # Reduce search space; this resource can never parent another
                # This proves to be faster in the long run.
                all_resources = [x for x in all_resources if (x[0], x[1]['id']) not in to_kill]

                # Look through remaining resources and get a new kill_q
                kill_q = self.__find_dead_resources(all_resources, to_kill)

            for resource_type, resource_id in to_kill:
                self.logger.writeInfo("removing resource: {}/{}".format(resource_type, resource_id))
                self.registry.delete(resource_type, resource_id)

        except self.registry.RegistryUnavailable:
            self.logger.writeWarning("registry unavailable")

        except TooLong:
            self.logger.writeWarning("took too long")

        except Exception as e:
            self.logger.writeError("unhandled exception: {}".format(e))

    def __find_dead_resources(self, all_resources, to_kill):

        def is_alive(parent_def):
            if parent_def in to_kill:
                return False
            parent_type, parent_id = parent_def
            found_parent = next((x for x in all_resources if x[0] == parent_type and x[1]['id'] == parent_id), None)
            return found_parent is not None

        # Build a list of resource to remove
        kill_q = []

        # Look through all remaining resources
        for child_type, child in all_resources:

            # We need never consider nodes; they should have already been marked.
            if child_type == "nodes":
                continue

            child_id = child['id']

            # Get parent for child. There is only ever one; anything with multiple
            # parent entries in the parent table has multiple entries for backward
            # compatibility, in order strongest->weakest.
            parents = [(parent_type, child.get(parent_key)) for parent_type, parent_key in self.parent_tab.get(child_type, (None, None))]
            parent = next((x for x in parents if x[1] is not None), None)
            if parent is None or not is_alive(parent):
                kill_q.append((child_type, child_id))

        return kill_q

    def _remove_flag(self):
        try:
            self.registry.delete_raw("garbage_collection")
        except Exception as e:
            self.logger.writeWarning("Could not remove flag: {}".format(e))
