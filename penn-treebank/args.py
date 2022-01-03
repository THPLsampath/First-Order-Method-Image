# Copyright 2018,2019,2020,2021 Sony Corporation.
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


# def get_args(monitor_path='tmp.monitor', max_iter=10000, model_save_path=None, learning_rate=1e-3, batch_size=128, weight_decay=0, description=None):
def get_args():
    """
    Get command line arguments.
    Arguments set the default values of command line arguments.
    """
    import argparse
    import os
    parser = argparse.ArgumentParser()
    parser.add_argument('--context', '-c', type=str,
                        default="cudnn", help="Extension path. ex) cpu, cudnn.")
    parser.add_argument("--device-id", "-d", type=str, default='0',
                        help='Device ID the training run on. This is only valid if you specify `-c cudnn`.')
    parser.add_argument("--type-config", "-t", type=str, default='float',
                        help='Type of computation. e.g. "float", "half".')
    parser.add_argument("--work-dir", "-w", type=str,
                        default="tmp.result/")
    parser.add_argument("--save-dir", "-s", type=str,
                        default="params/")
    parser.add_argument("--batch-size", "-b", type=int, default=20)
    parser.add_argument("--learning-rate", "-l", type=float, default=20)
    parser.add_argument("--max-epoch", "-e", type=int, default=40)
    parser.add_argument("--monitor-interval", "-m", type=int, default=1000)
    parser.add_argument("--num-steps", "-n", type=int, default=35)
    parser.add_argument("--state-size", "-S", type=int, default=650)
    parser.add_argument("--num-layers", "-a", type=int, default=2)
    parser.add_argument("--gradient-clipping-max-norm",
                        "-g", type=int, default=0.25)
    parser.add_argument("--checkpoint", type=str, default=None,
                        help='path to checkpoint file')
    args = parser.parse_args()
    return args
