# Copyright 2020,2021 Sony Corporation.
# Copyright 2021 Sony Group Corporation.
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

from . import (
    resnet,
    resnext,
    senet,
    mobilenet,
    efficientnet
)


def build_network(x, num_classes, arch, test=True, channel_last=False):

    from . import registry
    args = (x, num_classes)
    kwargs = dict(test=test, channel_last=channel_last)
    arch_fn = registry.query_arch_fn(arch)
    pred, hidden = arch_fn(*args, **kwargs)
    return pred, hidden
