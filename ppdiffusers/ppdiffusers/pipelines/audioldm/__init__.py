# Copyright (c) 2023 PaddlePaddle Authors. All Rights Reserved.
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

from ...utils import (OptionalDependencyNotAvailable, is_paddle_available,
                      is_paddlenlp_available, is_paddlenlp_version)

try:
    if not (is_paddlenlp_available() and is_paddle_available() and
            is_paddlenlp_version(">=", "2.5.2")):
        raise OptionalDependencyNotAvailable()
except OptionalDependencyNotAvailable:
    from ...utils.dummy_paddle_and_paddlenlp_objects import AudioLDMPipeline
else:
    from .pipeline_audioldm import AudioLDMPipeline
