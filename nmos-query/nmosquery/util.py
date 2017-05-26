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

import string

def translate_resourcetypes(url):
    """ translate urls such as /sources/{uid}/ -> sources/{uid} """
    trimmed = url.strip('/')
    split = trimmed.split('/')
    if len(split) >= 2:
        return "{}/{}".format(split[0], string.lower(split[1]))
    elif len(split) == 1:
        return split[0]
    else:
        return ''

def get_resourcetypes(url):
    """ Extract the resource type from a url in form /resource/{type} or just {type}/ """
    pos = url.find("/resource/")
    if pos < 0:
        return ""

    stem = url[pos + len("/resource/"):]
    slash = stem.find('/')
    if slash >= 0:
        return stem[:slash]

    return stem
