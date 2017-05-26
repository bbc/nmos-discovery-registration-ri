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

def convert(obj, rtype, target_ver, downgrade_ver=None):
    # Ensure an API version is set on the object
    if "@_apiversion" not in obj:
        obj["@_apiversion"] = "v1.0"

    # Fix max supported API version
    if _api_ver_compare(target_ver, "v1.2") > 0:
        return None

    # Convert high versioned resources for low versioned output
    if _api_ver_compare(target_ver, "v1.2") < 0 and obj["@_apiversion"] == "v1.2":
        obj = _v1_2_to_v1_1(obj, rtype)
        obj["@_apiversion"] = "v1.1"
    if _api_ver_compare(target_ver, "v1.1") < 0 and obj["@_apiversion"] == "v1.1":
        obj = _v1_1_to_v1_0(obj, rtype)
        obj["@_apiversion"] = "v1.0"

    # Check if the object's API version is permitted in the output
    if target_ver == obj["@_apiversion"]:
        return obj
    elif downgrade_ver and _api_ver_compare(obj["@_apiversion"], downgrade_ver) >= 0:
        return obj

    # Fallback
    return None


def _remove_if_present(obj, key):
    if key in obj:
        del obj[key]
    return obj


def _api_ver_compare(first, second):
    ver_first = first[1:].split(".")
    ver_second = second[1:].split(".")
    if ver_first[0] < ver_second[0]:
        return -1
    elif ver_first[0] > ver_second[0]:
        return 1
    elif ver_first[1] < ver_second[1]:
        return -1
    elif ver_first[1] > ver_second[1]:
        return 1
    else:
        return 0


def _v1_1_to_v1_0(obj, rtype):
    if rtype == "nodes":
        for key in ["api", "description", "tags", "clocks"]:
            _remove_if_present(obj, key)

    elif rtype == "flows":
        for key in ["device_id", "media_type", "refclock", "colorspace",
                    "components", "frame_height", "frame_width",
                    "interlace_mode", "bit_depth", "sample_rate",
                    "DID_SDID", "grain_rate", "transfer_characteristic"]:
            _remove_if_present(obj, key)

    elif rtype == "devices":
        for key in ["controls", "description", "tags"]:
            _remove_if_present(obj, key)

    elif rtype == "receivers":
        obj['caps'] = {}

    elif rtype == "sources":
        for key in ["clock_name", "channels"]:
            _remove_if_present(obj, key)

    return obj


def _v1_2_to_v1_1(obj, rtype):
    if rtype == "nodes":
        for key in ["interfaces"]:
            _remove_if_present(obj, key)

    elif rtype == "receivers":
        for key in ["interface_bindings"]:
            _remove_if_present(obj, key)

    elif rtype == "senders":
        for key in ["interface_bindings", "caps"]:
            _remove_if_present(obj, key)

    return obj
