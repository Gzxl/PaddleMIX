# Copyright (c) 2023 PaddlePaddle Authors. All Rights Reserved.
# Copyright 2023 The HuggingFace Team. All rights reserved.
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

import os

from packaging import version

from ..version import VERSION as __version__
from . import initializer_utils
from .constants import (
    CONFIG_NAME, DEPRECATED_REVISION_ARGS, DIFFUSERS_CACHE, DOWNLOAD_SERVER,
    FASTDEPLOY_MODEL_NAME, FASTDEPLOY_WEIGHTS_NAME, FLAX_WEIGHTS_NAME,
    FROM_DIFFUSERS, FROM_HF_HUB, HF_MODULES_CACHE,
    HUGGINGFACE_CO_RESOLVE_ENDPOINT, LOW_CPU_MEM_USAGE_DEFAULT, NEG_INF,
    ONNX_EXTERNAL_WEIGHTS_NAME, ONNX_WEIGHTS_NAME, PADDLE_WEIGHTS_NAME,
    PPDIFFUSERS_CACHE, PPDIFFUSERS_DYNAMIC_MODULE_NAME,
    PPDIFFUSERS_MODULES_CACHE, PPNLP_BOS_RESOLVE_ENDPOINT, TEST_DOWNLOAD_SERVER,
    TEXT_ENCODER_ATTN_MODULE, TO_DIFFUSERS, TORCH_SAFETENSORS_WEIGHTS_NAME,
    TORCH_WEIGHTS_NAME, WEIGHTS_NAME, get_map_location_default, str2bool)
from .deprecation_utils import deprecate
from .doc_utils import replace_example_docstring
from .download_utils import (_add_variant, _get_model_file, bos_hf_download,
                             ppdiffusers_bos_dir_download,
                             ppdiffusers_url_download)
from .dynamic_modules_utils import get_class_from_dynamic_module
from .hub_utils import HF_HUB_OFFLINE, extract_commit_hash, http_user_agent
from .import_utils import (
    BACKENDS_MAPPING, ENV_VARS_TRUE_AND_AUTO_VALUES, ENV_VARS_TRUE_VALUES,
    DummyObject, OptionalDependencyNotAvailable, is_bs4_available,
    is_einops_available, is_fastdeploy_available, is_ftfy_available,
    is_inflect_available, is_k_diffusion_available, is_k_diffusion_version,
    is_librosa_available, is_note_seq_available, is_omegaconf_available,
    is_paddle_available, is_paddle_version, is_paddlenlp_available,
    is_paddlenlp_version, is_ppxformers_available, is_safetensors_available,
    is_scipy_available, is_tensorboard_available, is_torch_available,
    is_torch_version, is_unidecode_available, is_visualdl_available,
    is_wandb_available, requires_backends)
# custom load_utils
from .load_utils import is_torch_file, safetensors_load, smart_load, torch_load
from .logging import get_logger
from .outputs import BaseOutput
from .paddle_utils import rand_tensor, randint_tensor, randn_tensor
from .pil_utils import PIL_INTERPOLATION, numpy_to_pil, pd_to_pil, pt_to_pil

if is_paddle_available():
    from .testing_utils import (
        floats_tensor, image_grid, load_hf_numpy, load_image, load_numpy,
        load_pd, load_ppnlp_numpy, nightly, paddle_all_close, paddle_device,
        parse_flag_from_env, print_tensor_test, require_paddle_gpu, slow)

if is_torch_available():
    from .testing_utils import require_torch

logger = get_logger(__name__)


def apply_forward_hook(method):
    return method


from .testing_utils import export_to_video


def check_min_version(min_version):
    if version.parse(__version__) < version.parse(min_version):
        if "dev" in min_version:
            error_message = (
                "This example requires a source install from PaddleNLP ppdiffusers (see "
                "`https://huggingface.co/docs/diffusers/installation#install-from-source`),"
            )
        else:
            error_message = f"This example requires a minimum version of {min_version},"
        error_message += f" but the version found is {__version__}.\n"
        raise ImportError(error_message)
