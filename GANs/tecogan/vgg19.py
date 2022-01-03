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

import numpy as np
import nnabla as nn
import nnabla.functions as F
import nnabla.parametric_functions as PF
from utils.utils import deprocess
from args import get_config


def get_vgg_feat(input_var):
    """
        Exactly the same architecture used for LPIPS.
                Returns output features from conv1 to relu5_4, classification layers are dropped.
    """
    #assert input_var.shape[1] == 3
    act1 = F.relu(PF.convolution(input_var, outmaps=64,
                                 kernel=(3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv1"), True)
    act1 = F.relu(PF.convolution(act1, outmaps=64, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv2"), True)

    act2 = F.max_pooling(act1, kernel=(2, 2), stride=(2, 2), channel_last=True)
    act2 = F.relu(PF.convolution(act2, outmaps=128, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv3"), True)
    act2 = F.relu(PF.convolution(act2, outmaps=128, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv4"), True)

    act3 = F.max_pooling(act2, kernel=(2, 2), stride=(2, 2), channel_last=True)
    act3 = F.relu(PF.convolution(act3, outmaps=256, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv5"), True)
    act3 = F.relu(PF.convolution(act3, outmaps=256, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv6"), True)
    act3 = F.relu(PF.convolution(act3, outmaps=256, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv7"), True)
    act3 = F.relu(PF.convolution(act3, outmaps=256, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv8"), True)

    act4 = F.max_pooling(act3, kernel=(2, 2), stride=(2, 2), channel_last=True)
    act4 = F.relu(PF.convolution(act4, outmaps=512, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv9"), True)
    act4 = F.relu(PF.convolution(act4, outmaps=512, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv10"), True)
    act4 = F.relu(PF.convolution(act4, outmaps=512, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv11"), True)
    act4 = F.relu(PF.convolution(act4, outmaps=512, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv12"), True)

    act5 = F.max_pooling(act4, kernel=(2, 2), stride=(2, 2), channel_last=True)
    act5 = F.relu(PF.convolution(act5, outmaps=512, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv13"), True)
    act5 = F.relu(PF.convolution(act5, outmaps=512, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv14"), True)
    act5 = F.relu(PF.convolution(act5, outmaps=512, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv15"), True)
    act5 = F.relu(PF.convolution(act5, outmaps=512, kernel=(
        3, 3), pad=(1, 1), channel_last=True, fix_parameters=True, name="conv16"), True)

    return [act2, act3, act4, act5]


class VGG19(object):
    """
        Load VGG19 pretrained weights and
        return output features from conv1 to relu5_4.
        """

    def __init__(self):
        conf = get_config()

        with nn.parameter_scope("vgg19"):
            if not conf.train.checkpoint:
                print("Loading pre-trained vgg19 weights from ",
                      conf.train.vgg_pre_trained_weights)
                nn.load_parameters(conf.train.vgg_pre_trained_weights)

                # drop all the affine layers from pre-trained model for finetuning.
                drop_layers = ['classifier/0/affine',
                               'classifier/3/affine', 'classifier/6/affine']
                for layers in drop_layers:
                    nn.parameter.pop_parameter((layers + '/W'))
                    nn.parameter.pop_parameter((layers + '/b'))
            self.mean = nn.Variable.from_numpy_array(np.asarray(
                [123.68, 116.78, 103.94]).reshape(1, 1, 1, 3))

    def __call__(self, x):
        with nn.parameter_scope("vgg19"):
            results = list()
            input = deprocess(x)
            x_in = F.sub2(input * 255.0, self.mean)
            features = get_vgg_feat(x_in)
            for i in range(len(features)):
                orig_deep_feature = features[i]
                orig_len = (F.sum((orig_deep_feature ** 2),
                                  axis=[3], keepdims=True)+1e-12) ** 0.5
                results.append(orig_deep_feature / orig_len)
            return results
