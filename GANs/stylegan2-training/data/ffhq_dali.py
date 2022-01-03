# Copyright 2021 Sony Corporation.
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

from nvidia.dali.pipeline import Pipeline
import nvidia.dali.ops as ops
import nvidia.dali.types as types
from nvidia.dali.backend import TensorGPU

import nnabla as nn
import nnabla.functions as F
from nnabla.ext_utils import get_extension_context
from nnabla.utils.data_iterator import data_iterator_cache

import ctypes
import logging
import numpy as np


def feed_ndarray(dali_tensor, arr, dtype, ctx):
    """
    Copy contents of DALI tensor to NNabla's NdArray.
    Parameters
    ----------
    `dali_tensor` : nvidia.dali.backend.TensorCPU or nvidia.dali.backend.TensorGPU
                    Tensor from which to copy
    `arr` : nnabla.NdArray
            Destination of the copy
    `dtype` : Data type
    `ctx` : nnabla.Context
    """
    assert dali_tensor.shape() == list(arr.shape), \
        ("Shapes do not match: DALI tensor has size {0}"
         ", but NNabla Tensor has size {1}".format(dali_tensor.shape(), list(arr.size)))
    # turn raw int to a c void pointer
    c_type_pointer = ctypes.c_void_p(arr.data_ptr(dtype, ctx))
    dali_tensor.copy_to_external(c_type_pointer)
    return arr


class DataPipeline(Pipeline):

    def __init__(self, img_dir, img_size, batch_size, num_threads, device_id, num_gpus=1, seed=1):
        super(DataPipeline, self).__init__(
            batch_size, num_threads, device_id, seed=seed)
        self.input = ops.FileReader(file_root=img_dir,
                                    random_shuffle=True, num_shards=num_gpus, shard_id=device_id)
        self.decode = ops.ImageDecoder(device='mixed', output_type=types.RGB)

        self.res = ops.Resize(device="gpu", resize_x=img_size)
        self.cmn = ops.CropMirrorNormalize(device='gpu',
                                           image_type=types.RGB,
                                           mean=[0.5*255, 0.5*255, 0.5*255],
                                           std=[0.5*255, 0.5*255, 0.5*255],
                                           )
        self.rrc = ops.RandomResizedCrop(
            device='gpu', size=(img_size, img_size))

    def define_graph(self):
        jpegs, labels = self.input(name='Reader')
        images = self.decode(jpegs)

        images = self.res(images)
        images = self.cmn(images)
        return images, labels


class DALIGenericIterator(object):
    """
    General DALI iterator for NNabla. It can return any number of
    outputs from the DALI pipeline in the form of NNabla's Tensors.

    Parameters
    ----------
    pipelines : list of nvidia.dali.pipeline.Pipeline
                List of pipelines to use
    output_map : list of str
                 List of strings which maps consecutive outputs
                 of DALI pipelines to user specified name.
                 Outputs will be returned from iterator as dictionary
                 of those names.
                 Each name should be distinct
    size : int
           Epoch size.
    auto_reset : bool, optional, default = False
                 Whether the iterator resets itself for the next epoch
                 or it requires reset() to be called separately.
    stop_at_epoch : bool, optional, default = True
                 Whether to return a fraction of a full batch of data
                 such that the total entries returned by the
                 iterator == 'size'. Setting this flag to False will
                 cause the iterator to return the first integer multiple
                 of self._num_gpus * self.batch_size which exceeds 'size'.
    """

    def __init__(self,
                 pipelines,
                 output_map,
                 size,
                 auto_reset=False,
                 stop_at_epoch=True,
                 ):
        if not isinstance(pipelines, list):
            pipelines = [pipelines]
        self._num_gpus = len(pipelines)
        assert pipelines is not None, "Number of provided pipelines has to be at least 1"
        self.batch_size = pipelines[0].batch_size
        self._size = int(size)
        self._auto_reset = auto_reset
        self._stop_at_epoch = stop_at_epoch
        self._pipes = pipelines
        # Build all pipelines
        for p in self._pipes:
            p.build()
        # Use double-buffering of data batches
        self._data_batches = [[None, None] for i in range(self._num_gpus)]
        self._counter = 0
        self._current_data_batch = 0
        assert len(set(output_map)) == len(
            output_map), "output_map names should be distinct"
        self._output_categories = set(output_map)
        self.output_map = output_map

        # We need data about the batches (like shape information),
        # so we need to run a single batch as part of setup to get that info
        for p in self._pipes:
            p.schedule_run()
        self._first_batch = None
        self._first_batch = self.next()

    def __next__(self):
        if self._first_batch is not None:
            batch = self._first_batch
            self._first_batch = None
            return batch
        if self._counter >= self._size:
            if self._auto_reset:
                self.reset()
            # raise StopIteration
        # Gather outputs
        outputs = []
        for p in self._pipes:
            outputs.append(p.share_outputs())
        for i in range(self._num_gpus):
            device_id = self._pipes[i].device_id
            # initialize dict for all output categories
            category_outputs = dict()
            # segregate outputs into categories
            for j, out in enumerate(outputs[i]):
                category_outputs[self.output_map[j]] = out

            # Change DALI TensorLists into Tensors
            category_tensors = dict()
            category_shapes = dict()
            for category, out in category_outputs.items():
                category_tensors[category] = out.as_tensor()
                category_shapes[category] = category_tensors[category].shape()

            # If we did not yet allocate memory for that batch, do it now
            if self._data_batches[i][self._current_data_batch] is None:
                self._category_nnabla_type = dict()
                self._category_device = dict()
                nnabla_gpu_device = get_extension_context(
                    'cudnn', device_id=device_id)
                nnabla_cpu_device = get_extension_context('cpu')
                # check category and device
                for category in self._output_categories:
                    self._category_nnabla_type[category] = np.dtype(
                        category_tensors[category].dtype())
                    if type(category_tensors[category]) is TensorGPU:
                        self._category_device[category] = nnabla_gpu_device
                    else:
                        self._category_device[category] = nnabla_cpu_device

                nnabla_tensors = dict()
                for category in self._output_categories:
                    nnabla_tensors[category] = nn.NdArray(
                        category_shapes[category])

                self._data_batches[i][self._current_data_batch] = nnabla_tensors
            else:
                nnabla_tensors = self._data_batches[i][self._current_data_batch]

            # Copy data from DALI Tensors to nnabla tensors
            for category, tensor in category_tensors.items():
                feed_ndarray(tensor, nnabla_tensors[category],
                             dtype=self._category_nnabla_type[category],
                             ctx=self._category_device[category])

        for p in self._pipes:
            p.release_outputs()
            p.schedule_run()

        copy_db_index = self._current_data_batch
        # Change index for double buffering
        self._current_data_batch = (self._current_data_batch + 1) % 2
        self._counter += self._num_gpus * self.batch_size

        if (self._stop_at_epoch) and (self._counter > self._size):
            # First calculate how much data is required to return exactly self._size entries.
            diff = self._num_gpus * self.batch_size - \
                (self._counter - self._size)
            # Figure out how many GPUs to grab from.
            numGPUs_tograb = int(np.ceil(diff/self.batch_size))
            # Figure out how many results to grab from the last GPU (as a fractional GPU batch may be required to
            # bring us right up to self._size).
            mod_diff = diff % self.batch_size
            data_fromlastGPU = mod_diff if mod_diff else self.batch_size

            # Grab the relevant data.
            # 1) Grab everything from the relevant GPUs.
            # 2) Grab the right data from the last GPU.
            # 3) Append data together correctly and return.
            output = [db[copy_db_index]
                      for db in self._data_batches[0:numGPUs_tograb]]
            output[-1] = output[-1].copy()
            for category in self._output_categories:
                output[-1][category] = output[-1][category][0:data_fromlastGPU]

            return output

        return [db[copy_db_index] for db in self._data_batches]

    def next(self):
        """
        Returns the next batch of data.
        """
        return self.__next__()

    def __iter__(self):
        return self

    def reset(self):
        """
        Resets the iterator after the full epoch.
        DALI iterators do not support resetting before the end of the epoch
        and will ignore such request.
        """
        if (self._stop_at_epoch) and (self._counter >= self._size):
            self._counter = 0
        elif (not self._stop_at_epoch) and (self._counter >= self._size):
            self._counter = self._counter % self._size
        else:
            logging.warning(
                "DALI iterator does not support resetting while epoch is not finished. Ignoring...")


class DALIClassificationIterator(DALIGenericIterator):
    """
    DALI iterator for classification tasks for NNabla. It returns 2 outputs
    (data and label) in the form of NNabla's Tensor.

    Calling

    .. code-block:: python

       DALIClassificationIterator(pipelines, size)

    is equivalent to calling

    .. code-block:: python

       DALIGenericIterator(pipelines, ["data", "label"], size)

    Parameters
    ----------
    pipelines : list of nvidia.dali.pipeline.Pipeline
                List of pipelines to use
    size : int
           Epoch size.
    auto_reset : bool, optional, default = False
                 Whether the iterator resets itself for the next epoch
                 or it requires reset() to be called separately.
    stop_at_epoch : bool, optional, default = True
                 Whether to return a fraction of a full batch of data
                 such that the total entries returned by the
                 iterator == 'size'. Setting this flag to False will
                 cause the iterator to return the first integer multiple
                 of self._num_gpus * self.batch_size which exceeds 'size'.
    """

    def __init__(self,
                 pipelines,
                 size,
                 auto_reset=True,
                 stop_at_epoch=False,
                 ):
        super(DALIClassificationIterator, self).__init__(pipelines, ["data", "label"],
                                                         size, auto_reset=auto_reset,
                                                         stop_at_epoch=stop_at_epoch,
                                                         )
        self.size = self._size

    def next(self):
        """
        Returns the next batch (data, label). 
        """
        result = super(DALIClassificationIterator, self).next()
        if len(result) == 1:
            return result[0]["data"], result[0]["label"]
        data = result[0]
        label = result[1]
        return data, label


def get_dali_iterator_ffhq(data_config, img_size, batch_size, comm):
    pipes = [DataPipeline(data_config['path'], img_size,
                          batch_size, data_config['dali_threads'], comm.rank,
                          num_gpus=comm.n_procs, seed=1)]

    pipes[0].build()
    data_iterator_ = DALIClassificationIterator(pipes,
                                                pipes[0].epoch_size('Reader') // comm.n_procs)
    return data_iterator_
