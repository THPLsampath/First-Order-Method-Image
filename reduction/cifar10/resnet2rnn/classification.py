# Copyright 2017,2018,2019,2020,2021 Sony Corporation.
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

from __future__ import absolute_import
from six.moves import range

import os
import sys

import nnabla as nn
import nnabla.logger as logger
import nnabla.functions as F
import nnabla.parametric_functions as PF
import nnabla.solvers as S
import nnabla.utils.save as save

from args import get_args
from cifar10_data import data_iterator_cifar10
from models import cifar10_resnet2rnn_prediction, res_unit_bottleneck, categorical_error

import functools


def train():
    args = get_args()

    # Get context.
    from nnabla.ext_utils import get_extension_context
    logger.info("Running in %s" % args.context)
    ctx = get_extension_context(
        args.context, device_id=args.device_id, type_config=args.type_config)
    nn.set_default_context(ctx)

    # Create CNN network for both training and testing.
    if args.net == "cifar10_resnet2rnn_10_prediction":
        model_prediction = functools.partial(
            cifar10_resnet2rnn_prediction, unrolls=[10])
    if args.net == "cifar10_resnet2rnn_15_prediction":
        model_prediction = functools.partial(
            cifar10_resnet2rnn_prediction, unrolls=[15])
    if args.net == "cifar10_resnet2rnn_3x3x4_prediction":
        model_prediction = functools.partial(
            cifar10_resnet2rnn_prediction, unrolls=[3, 3, 4])
    if args.net == "cifar10_resnet2rnn_5x5_prediction":
        model_prediction = functools.partial(
            cifar10_resnet2rnn_prediction, unrolls=[5, 5])
    if args.net == "cifar10_resnet2rnn_5_prediction":
        model_prediction = functools.partial(
            cifar10_resnet2rnn_prediction, unrolls=[5])
    if args.net == "cifar10_bresnet2rnn_10_prediction":
        model_prediction = functools.partial(cifar10_resnet2rnn_prediction, unrolls=[
                                             10], res_unit=res_unit_bottleneck)
    if args.net == "cifar10_bresnet2rnn_15_prediction":
        model_prediction = functools.partial(cifar10_resnet2rnn_prediction, unrolls=[
                                             15], res_unit=res_unit_bottleneck)
    if args.net == "cifar10_bresnet2rnn_3x3x4_prediction":
        model_prediction = functools.partial(cifar10_resnet2rnn_prediction, unrolls=[
                                             3, 3, 4], res_unit=res_unit_bottleneck)
    if args.net == "cifar10_bresnet2rnn_5x5_prediction":
        model_prediction = functools.partial(cifar10_resnet2rnn_prediction, unrolls=[
                                             5, 5], res_unit=res_unit_bottleneck)
    if args.net == "cifar10_bresnet2rnn_5_prediction":
        model_prediction = functools.partial(cifar10_resnet2rnn_prediction, unrolls=[
                                             5], res_unit=res_unit_bottleneck)

    # TRAIN
    maps = 64
    data_iterator = data_iterator_cifar10
    c = 3
    h = w = 32
    n_train = 50000
    n_valid = 10000
    # Create input variables.
    image = nn.Variable([args.batch_size, c, h, w])
    label = nn.Variable([args.batch_size, 1])
    # Create `teacher` model_prediction graph.
    pred = model_prediction(image, maps=maps, test=False)
    pred.persistent = True
    # Create loss function.
    loss = F.mean(F.softmax_cross_entropy(pred, label))

    # TEST
    # Create input variables.
    vimage = nn.Variable([args.batch_size, c, h, w])
    vlabel = nn.Variable([args.batch_size, 1])
    # Create teacher prediction graph.
    vpred = model_prediction(vimage, maps=maps, test=True)

    # Create Solver.
    solver = S.Adam(args.learning_rate)
    solver.set_parameters(nn.get_parameters())

    # Create monitor.
    from nnabla.monitor import Monitor, MonitorSeries, MonitorTimeElapsed
    monitor = Monitor(args.monitor_path)
    monitor_loss = MonitorSeries("Training loss", monitor, interval=10)
    monitor_err = MonitorSeries("Training error", monitor, interval=10)
    monitor_time = MonitorTimeElapsed("Training time", monitor, interval=100)
    monitor_verr = MonitorSeries("Test error", monitor, interval=1)

    # Initialize DataIterator
    data = data_iterator(args.batch_size, True)
    vdata = data_iterator(args.batch_size, False)
    best_ve = 1.0
    ve = 1.0
    # Training loop.
    for i in range(args.max_iter):
        if i % args.val_interval == 0:
            # Validation
            ve = 0.0
            for j in range(int(n_valid / args.batch_size)):
                vimage.d, vlabel.d = vdata.next()
                vpred.forward(clear_buffer=True)
                ve += categorical_error(vpred.d, vlabel.d)
            ve /= int(n_valid / args.batch_size)
            monitor_verr.add(i, ve)
        if ve < best_ve:
            nn.save_parameters(os.path.join(
                args.model_save_path, 'params_%06d.h5' % i))
            best_ve = ve
        # Training forward
        image.d, label.d = data.next()
        solver.zero_grad()
        loss.forward(clear_no_need_grad=True)
        loss.backward(clear_buffer=True)
        solver.weight_decay(args.weight_decay)
        solver.update()
        e = categorical_error(pred.d, label.d)
        monitor_loss.add(i, loss.d.copy())
        monitor_err.add(i, e)
        monitor_time.add(i)

    ve = 0.0
    for j in range(int(n_valid / args.batch_size)):
        vimage.d, vlabel.d = vdata.next()
        vpred.forward(clear_buffer=True)
        ve += categorical_error(vpred.d, vlabel.d)
    ve /= int(n_valid / args.batch_size)
    monitor_verr.add(i, ve)

    parameter_file = os.path.join(
        args.model_save_path, 'params_{:06}.h5'.format(args.max_iter))
    nn.save_parameters(parameter_file)


if __name__ == '__main__':
    train()
