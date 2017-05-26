#!/usr/bin/python

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

import avahi
import dbus
import gevent
import socket
import time
import select
import gobject
from dbus.mainloop.glib import DBusGMainLoop
from gevent import monkey; monkey.patch_all()
import glib

__all__ = [ "MDNSEngine" ]

def _idle():
    gevent.sleep(0.1)
    return True

class MDNSEngine(object):
    def __init__(self):
        self.loop = DBusGMainLoop()
        self.bus = dbus.SystemBus(mainloop=self.loop)
        self.server = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME, '/'),
            'org.freedesktop.Avahi.Server')
        self.rlist = []
        self.unreg_queue = []
        self.greenlet = None
        self.running = False

    def start(self):
        if not gobject.MainLoop().is_running():
            self.greenlet = gevent.spawn(self.run)
            self.running = True

    def stop(self):
        if self.greenlet is not None:
            self._mainloop.quit()
            self.greenlet = None

    def close(self):
        for x in self.rlist:
            x[4].Free()
            self.rlist.remove(x)

    def run(self):
        glib.idle_add(_idle)
        self._mainloop = gobject.MainLoop()
        self._mainloop.run()

    def _findservice(self, name, regtype):
        for x in self.rlist:
            if x[0] == name and x[1] == regtype:
                return x[4]
        return None

    def register(self, name, regtype, port, txtRecord=None, callback=None):
        def _entrygroup_state_changed(name, regtype, port, txtRecord, callback):
            def _inner(state, error):
                if callback is not None:
                    if state == avahi.ENTRY_GROUP_COLLISION:
                        callback({ "action" : "collision", "name" : name, "regtype" : regtype, "port" : port, "txtRecord" : txtRecord})
                    elif state == avahi.ENTRY_GROUP_ESTABLISHED:
                        callback({ "action" : "established", "name" : name, "regtype" : regtype, "port" : port, "txtRecord" : txtRecord})
                    elif state == ENTRY_GROUP_FAILURE:
                        callback({ "action" : "failure", "name" : name, "regtype" : regtype, "port" : port, "txtRecord" : txtRecord})
            return _inner

        if txtRecord is None:
            txtRecord = {}
        entrygroup = self._findservice(name, regtype)
        if entrygroup is None:
            entrygroup = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME,
                                                            self.server.EntryGroupNew()),
                                         avahi.DBUS_INTERFACE_ENTRY_GROUP)
        if entrygroup.GetState() == avahi.ENTRY_GROUP_ESTABLISHED:
            entrygroup.Reset()
        entrygroup.connect_to_signal("StateChanged", _entrygroup_state_changed(name, regtype, port, txtRecord, callback))
        entrygroup.AddService(avahi.IF_UNSPEC,
                              avahi.PROTO_UNSPEC,
                              dbus.UInt32(0),
                              name,
                              regtype,
                              "local",
                              '',
                              port,
                              avahi.dict_to_txt_array(txtRecord))
        entrygroup.Commit()
        self.rlist.append((name, regtype, port, txtRecord, entrygroup))

    def update(self, name, regtype, txtRecord=None):
        if txtRecord is None:
            txtRecord = {}
        entrygroup = self._findservice(name, regtype)
        if entrygroup is not None:
            entrygroup.UpdateServiceTxt(avahi.IF_UNSPEC,
                                        avahi.PROTO_UNSPEC,
                                        dbus.UInt32(0),
                                        name,
                                        regtype,
                                        "local.",
                                        avahi.dict_to_txt_array(txtRecord))

    def unregister(self, name, regtype):
        for x in self.rlist:
            if x[0] == name and x[1] == regtype:
                x[4].Free()
                self.rlist.remove(x)

    def callback_on_services(self, regtype, callback, registerOnly=True, domain=None):

        def _error_handler(*args):
            print "Error: %r" % (args,)

        def _resolve_callback(callback):
            def _inner(interface, protocol, name, stype, domain, host, arprotocol, address, port, txt, flags):
                txtd = dict( x.split('=') for x in avahi.txt_array_to_string_array(txt) )
                callback({"action": "add", "name": name, "type": stype, "address": address, "port": port, "txt": txtd, "interface": interface})
            return _inner

        def _browse_callback(callback):
            def _inner(interface, protocol, name, stype, domain, flags):
                self.server.ResolveService(interface, protocol, name, stype, domain, avahi.PROTO_UNSPEC, dbus.UInt32(0),
                                           reply_handler=_resolve_callback(callback), error_handler=_error_handler)
            return _inner

        def _domain_callback(regtype, callback):
            def _inner(interface, protocol, domain, flags):
                sbrowser = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME,
                                                          self.server.ServiceBrowserNew(avahi.IF_UNSPEC,
                                                                                        avahi.PROTO_UNSPEC, regtype, domain, dbus.UInt32(0))),
                                      avahi.DBUS_INTERFACE_SERVICE_BROWSER)
                sbrowser.connect_to_signal("ItemNew", _browse_callback(callback))
                sbrowser.connect_to_signal("ItemRemove", _remove_callback(callback))
            return _inner

        def _remove_callback(callback):
            def _inner(interface, protocol, name, type, domain, flags):
                callback({"action": "remove", "name": name, "type": type})
            return _inner

        if domain is None:
            dbrowser = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME,
                                                          self.server.DomainBrowserNew(avahi.IF_UNSPEC,
                                                                                       avahi.PROTO_UNSPEC,
                                                                                       "",
                                                                                       0,
                                                                                       dbus.UInt32(0))),
                                      avahi.DBUS_INTERFACE_DOMAIN_BROWSER)
            dbrowser.connect_to_signal("ItemNew", _domain_callback(regtype, callback))
            sbrowser = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME,
                                                          self.server.ServiceBrowserNew(avahi.IF_UNSPEC,
                                                                                        avahi.PROTO_UNSPEC, regtype, "local", dbus.UInt32(0))),
                                      avahi.DBUS_INTERFACE_SERVICE_BROWSER)
            sbrowser.connect_to_signal("ItemNew", _browse_callback(callback))
        else:
            sbrowser = dbus.Interface(self.bus.get_object(avahi.DBUS_NAME,
                                                          self.server.ServiceBrowserNew(avahi.IF_UNSPEC,
                                                                                        avahi.PROTO_UNSPEC, regtype, domain, dbus.UInt32(0))),
                                      avahi.DBUS_INTERFACE_SERVICE_BROWSER)
            sbrowser.connect_to_signal("ItemNew", _browse_callback(callback))




if __name__ == "__main__":
    import sys
    from gevent import monkey; monkey.patch_all()

    def print_results_callback(data):
        print data

    e = MDNSEngine()
    e.start()

    regtype = "_nmos-node._tcp"
    domain = None
    if len(sys.argv) > 1:
        regtype = sys.argv[1]
    if len(sys.argv) > 2:
        domain = sys.argv[2]

    e.register("python_avahi_test", "_test._tcp", 12345, {"Potato" : "very"})

    e.callback_on_services(regtype, callback=print_results_callback, domain=domain)

    time.sleep(10)

    e.update("python_avahi_test", "_test._tcp", {"Potato" : "somewhat"})

    while True:
        time.sleep(1)

    e.stop()
    e.close()
