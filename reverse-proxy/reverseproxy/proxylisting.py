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

from nmoscommon.webapi import *
from os import listdir
from os.path import isfile, join

ALIAS_SITES="/etc/apache2/sites-enabled/"
PROXY_SITES="/etc/apache2/sites-available/"

class ProxyListingAPI(WebAPI):
    def __init__(self):
        super(ProxyListingAPI, self).__init__()

    @resource_route("/")
    def base(self):
        alias_list = ["x-nmos-opensourceprivatenamespace/", "x-nmos/"]
        for conffile in listdir(ALIAS_SITES):
            if isfile(join(ALIAS_SITES, conffile)) and conffile.endswith(".conf"):
                with open(join(ALIAS_SITES, conffile)) as aliasfile:
                    # If site is enabled and has an Alias, list the first level of it
                    for line in aliasfile:
                        if "Alias " in line:
                            line_bits = line.split("Alias ")[1].split(" ")
                            line_bits = line_bits[0].split("/")
                            alias_list.append(line_bits[1].strip() + "/")
        alias_list = list(set(alias_list)) # De-duplicate
        alias_list.sort()
        return alias_list

    @resource_route("/x-nmos-opensourceprivatenamespace/")
    def x_nmos_private(self):
        return self.get_apis("x-nmos-opensourceprivatenamespace")

    @resource_route("/x-nmos/")
    def x_nmos(self):
        return self.get_apis("x-nmos")

    def get_apis(self, delimiter):
        api_list = []
        for conffile in listdir(PROXY_SITES):
            if isfile(join(PROXY_SITES, conffile)) and conffile.endswith(".conf") and conffile.startswith("nmos-api-"):
                with open(join(PROXY_SITES, conffile)) as proxyfile:
                    # If site is available and has a Location, list the second level of it
                    for line in proxyfile:
                        if "<Location " in line:
                            line_bits = line.split("<Location ")[1].split(">")
                            line_bits = line_bits[0].split("/")
                            if line_bits[1] == delimiter:
                                api_list.append(line_bits[2].strip() + "/")
        api_list = list(set(api_list)) # De-duplicate
        api_list.sort()
        return api_list
