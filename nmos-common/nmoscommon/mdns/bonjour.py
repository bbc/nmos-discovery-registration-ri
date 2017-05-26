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

import select
import sys
import pybonjour
import gevent
import socket
import time

service_address = None
timeout = 5
resolved = []
queried = []

__all__ = ["browse_for_services",
           "register_service",
           "MDNSEngine"]

def query_record_callback(port):
    def _inner(sdRef, flags, interfaceIndex, errorCode, fullname,
               rrtype, rrclass, rdata, ttl):
        global queried, service_address
        print "Query record callback"
        if errorCode == pybonjour.kDNSServiceErr_NoError:
            print "service_address = ({},{})".format(socket.inet_ntoa(rdata), port)
            service_address = (socket.inet_ntoa(rdata), port)
            queried.append(True)

    return _inner

def resolve_callback(sdRef, flags, interfaceIndex, errorCode, fullname,
                     hosttarget, port, txtRecord):
    global queried, resolved

    if errorCode != pybonjour.kDNSServiceErr_NoError:
        return

    query_sdRef = pybonjour.DNSServiceQueryRecord(interfaceIndex = interfaceIndex, fullname = hosttarget, rrtype = pybonjour.kDNSServiceType_A, callBack = query_record_callback(port))
    print "Service {} Resolved; Querying".format(hosttarget)

    while service_address is None and not queried:
        ready = select.select([query_sdRef], [], [], 5)
        if query_sdRef not in ready[0]:
            print 'Query record timed out'
            break
        pybonjour.DNSServiceProcessResult(query_sdRef)
    else:
        queried.pop()
    query_sdRef.close()
    resolved.append(True)


def browse_callback(sdRef, flags, interfaceIndex, errorCode, serviceName,
                    regtype, replyDomain):
    if errorCode != pybonjour.kDNSServiceErr_NoError:
        return

    if not (flags & pybonjour.kDNSServiceFlagsAdd):
        print 'Service removed'
        return

    print 'Service added; resolving'

    resolve_sdRef = pybonjour.DNSServiceResolve(0,
                                                interfaceIndex,
                                                serviceName,
                                                regtype,
                                                replyDomain,
                                                resolve_callback)

    try:
        while service_address is None and not resolved:
            ready = select.select([resolve_sdRef], [], [], timeout)
            if resolve_sdRef not in ready[0]:
                print 'Resolve timed out'
                break
            pybonjour.DNSServiceProcessResult(resolve_sdRef)
        else:
            resolved.pop()
    finally:
        resolve_sdRef.close()


def browse_for_services(regtype):
    global service_address
    browse_sdRef = pybonjour.DNSServiceBrowse(regtype=regtype,
                                              callBack=browse_callback)

    try:
        try:
            while service_address is None:
                ready = select.select([browse_sdRef], [], [])
                if browse_sdRef in ready[0]:
                    pybonjour.DNSServiceProcessResult(browse_sdRef)
        except KeyboardInterrupt:
            pass
    finally:
        browse_sdRef.close()
    return service_address

def callback_on_services(regtype, callback):
    global service_address
    service_address = None
    def _inner():
        global service_address
        browse_sdRef = pybonjour.DNSServiceBrowse(regtype=regtype,
                                                  callBack=browse_callback)

        try:
            while True:
                try:
                    ready = select.select([browse_sdRef], [], [])
                    if browse_sdRef in ready[0]:
                        pybonjour.DNSServiceProcessResult(browse_sdRef)
                    if service_address is not None:
                        callback(service_address)
                        service_address = None
                except KeyboardInterrupt:
                    pass
        finally:
            browse_sdRef.close()
        return service_address

    t = gevent.spawn(_inner)

def register_callback(sdRef, flags, errorCode, name, regtype, domain):
    if errorCode == pybonjour.kDNSServiceErr_NoError:
        print 'Registered service:'
        print '  name    =', name
        print '  regtype =', regtype
        print '  domain  =', domain


def register_service(name, regtype, port):
    sdRef = pybonjour.DNSServiceRegister(name=name,
                                         regtype=regtype,
                                         port=port,
                                         callBack=register_callback)

    def register_main_loop():
        try:
            try:
                while True:
                    ready = select.select([sdRef], [], [])
                    if sdRef in ready[0]:
                        pybonjour.DNSServiceProcessResult(sdRef)
            except KeyboardInterrupt:
                pass
        finally:
            sdRef.close()

    t = gevent.spawn(register_main_loop)

class MDNSEngine(object):
    def __init__(self):
        self.greenlet = None
        self.running = False
        self.rlist = []
        self.unreg_queue = []

    def start(self):
        if self.greenlet is not None:
            self.stop()
        self.running = True
        self.greenlet = gevent.spawn(self.run)

    def stop(self):
        self.running = False
        if self.greenlet is not None:
            self.greenlet.kill()
        self.greenlet = None

    def close(self):
        for x in self.rlist:
            x[0].close()
            self.rlist.remove(x)

    def run(self):
        while self.running:
            for record in self.unreg_queue:
                self.unreg_queue.remove(record)
                if record in self.rlist:
                    self.rlist.remove(record)
                    record[0].close()
            rlist = [ x for x in self.rlist ]
            if len(rlist) > 0:
                ready = select.select([ x[0] for x in rlist ], [], [], 0.1)
                for x in ready[0]:
                    C = [ y for y in rlist if y[0] == x ]
                    if len(C) > 0:
                        C[0][1](x)
            else:
                time.sleep(0.1)

    def register(self, name, regtype, port, txtRecord=None, callback=None):
        if callback is None:
            callback = register_callback
        if txtRecord is None:
            txtRecord = {}
        if not isinstance(txtRecord, pybonjour.TXTRecord):
            txtRecord = pybonjour.TXTRecord(txtRecord)
        sdRef = pybonjour.DNSServiceRegister(name=name,
                                             regtype=regtype,
                                             port=port,
                                             callBack=callback,
                                             txtRecord=txtRecord)
        self.rlist.append([sdRef, pybonjour.DNSServiceProcessResult, name, regtype])
        return sdRef

    def update(self, name, regtype, txtRecord=None):
        recRef = self._find_record(name, regtype)
        if not recRef:
            return False
        if txtRecord is None:
            txtRecord = {}
        if not isinstance(txtRecord, pybonjour.TXTRecord):
            txtRecord = pybonjour.TXTRecord(txtRecord)
        pybonjour.DNSServiceUpdateRecord(recRef[0], None, 0, txtRecord, 0)
        return True

    def unregister(self, name, regtype):
        recRef = self._find_record(name, regtype)
        if not recRef:
            return False
        self.unreg_queue.append(recRef)
        return True

    def _find_record(self, name, regtype):
        recRef = None
        for record in self.rlist:
            if len(record) == 4:
                if record[2] == name and record[3] == regtype:
                    recRef = record
        return recRef

    def callback_on_services(self, regtype, callback, registerOnly=True, domain=None):
        def _query_record_callback(serviceName, regtype, port, txtRec, callback):
            def __inner(sdRef, flags, interfaceIndex, errorCode, fullname,
                        rrtype, rrclass, rdata, ttl):
#                print "_query_record_callback(%r, %r, %r, %r, %r, %r, %r, %r, %r)" % (sdRef, flags, interfaceIndex, errorCode, fullname, rrtype, rrclass, rdata, ttl)
                if errorCode == pybonjour.kDNSServiceErr_NoError:
                    callback({"action": "add", "name": serviceName, "type": regtype, "address": socket.inet_ntoa(rdata), "port": port, "txt": dict(txtRec), "interface": interfaceIndex})
                X = [ x for x in self.rlist if x[0] == sdRef ]
                for x in X:
                    self.rlist.remove(x)
                sdRef.close()

            return __inner

        def _resolve_callback(serviceName, regtype, callback):
            def __inner(sdRef, flags, interfaceIndex, errorCode, fullname,
                        hosttarget, port, txtRecord):
#                print "_resolve_callback(%r, %r, %r, %r, %r, %r, %r, %r)" % (sdRef, flags, interfaceIndex, errorCode, fullname, hosttarget, port, txtRecord)
                if errorCode != pybonjour.kDNSServiceErr_NoError:
                    return

                query_sdRef = pybonjour.DNSServiceQueryRecord(interfaceIndex = interfaceIndex,
                                                              fullname = hosttarget,
                                                              rrtype = pybonjour.kDNSServiceType_A,
                                                              callBack = _query_record_callback(serviceName, regtype, port, pybonjour.TXTRecord.parse(txtRecord), callback))

                self.rlist.append((query_sdRef, pybonjour.DNSServiceProcessResult))

                X = [ x for x in self.rlist if x[0] == sdRef ]
                for x in X:
                    self.rlist.remove(x)
                sdRef.close()

            return __inner

        def _query_SRV_callback(serviceName, regtype, callback):
            def __inner(sdRef, flags, interfaceIndex, errorCode, fullname, rrtype, rrclass, rdata, ttl):
#                print "_query_SRV_callback(%r, %r, %r, %r, %r, %r, %r, %r, %r)" % (sdRef, flags, interfaceIndex, errorCode, fullname, rrtype, rrclass, rdata, ttl)
                if errorCode == pybonjour.kDNSServiceErr_NoError:
                    print "Got Data"
                X = [ x for x in self.rlist if x[0] == sdRef ]
                for x in X:
                    self.rlist.remove(x)
                sdRef.close()

            return __inner

        def _browse_callback(callback):
            def __inner(sdRef, flags, interfaceIndex, errorCode, serviceName,
                        regtype, replyDomain):
#                print "_browse_callback(%r, %r, %r, %r, %r, %r, %r)" % (sdRef, flags, interfaceIndex, errorCode, serviceName, regtype, replyDomain)
                if errorCode != pybonjour.kDNSServiceErr_NoError:
                    return

                if not (flags & pybonjour.kDNSServiceFlagsAdd):
                    if not registerOnly:
                        callback({"action": "remove", "name": serviceName, "type": regtype})
                    return

                if replyDomain == "local.":
                    resolve_sdRef = pybonjour.DNSServiceResolve(0,
                                                                interfaceIndex,
                                                                serviceName,
                                                                regtype,
                                                                replyDomain,
                                                                _resolve_callback(serviceName, regtype, callback))
                    self.rlist.append((resolve_sdRef, pybonjour.DNSServiceProcessResult))
                else:
                    query_sdRef = pybonjour.DNSServiceQueryRecord(interfaceIndex=interfaceIndex,
                                                                  fullname=serviceName + '.' + replyDomain,
                                                                  rrtype = pybonjour.kDNSServiceType_SRV,
                                                                  callBack = _query_SRV_callback(serviceName, regtype, callback))
                    self.rlist.append((query_sdRef, pybonjour.DNSServiceProcessResult))
            return __inner

        def _domain_callback(callback):
            def __inner(sdRef, flags, interfaceIndex, errorCode, replyDomain):
 #               print "_domain_callback(%r, %r, %r, %r, %r)" % (sdRef, flags, interfaceIndex, errorCode, replyDomain)
                if errorCode != pybonjour.kDNSServiceErr_NoError:
                    return

                sdRef = pybonjour.DNSServiceBrowse(regtype=regtype,
                                                    callBack=_browse_callback(callback),
                                                    domain=replyDomain)
                self.rlist.append((sdRef, pybonjour.DNSServiceProcessResult))
            return __inner

        if domain is None:
            sdRef = pybonjour.DNSServiceBrowse(regtype=regtype,
                                            callBack=_browse_callback(callback))
            self.rlist.append((sdRef, pybonjour.DNSServiceProcessResult))

            dRef = pybonjour.DNSServiceEnumerateDomains(pybonjour.kDNSServiceFlagsBrowseDomains,
                                                        callBack=_domain_callback(callback))
            self.rlist.append((dRef, pybonjour.DNSServiceProcessResult))
        else:
            sdRef = pybonjour.DNSServiceBrowse(regtype=regtype,
                                                callBack=_browse_callback(callback),
                                                domain=domain)
            self.rlist.append((sdRef, pybonjour.DNSServiceProcessResult))

        return sdRef

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

    e.callback_on_services(regtype, callback=print_results_callback, domain=domain)

    try:
        while True:
            time.sleep(0.1)
    except:
        pass

    e.stop()
    e.close()
