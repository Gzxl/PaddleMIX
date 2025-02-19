# Copyright (c) 2022 PaddlePaddle Authors. All Rights Reserved.
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
import argparse
import tempfile
from collections import OrderedDict

import paddle
import torch
from diffusers import \
    StableDiffusionDepth2ImgPipeline as \
    DiffusersStableDiffusionDepth2ImgPipeline
from paddlenlp.transformers import (CLIPTextConfig, CLIPTextModel,
                                    CLIPTokenizer, DPTConfig,
                                    DPTForDepthEstimation, DPTImageProcessor)

from ppdiffusers import AutoencoderKL, PNDMScheduler
from ppdiffusers import \
    StableDiffusionDepth2ImgPipeline as \
    PPDiffusersStableDiffusionDepth2ImgPipeline
from ppdiffusers import UNet2DConditionModel

paddle.set_device("cpu")


def convert_to_ppdiffusers(vae_or_unet, dtype="float32"):
    need_transpose = []
    for k, v in vae_or_unet.named_modules():
        if isinstance(v, torch.nn.Linear):
            need_transpose.append(k + ".weight")
    new_vae_or_unet = OrderedDict()
    for k, v in vae_or_unet.state_dict().items():
        if k not in need_transpose:
            new_vae_or_unet[k] = v.cpu().numpy().astype(dtype)
        else:
            new_vae_or_unet[k] = v.t().cpu().numpy().astype(dtype)
    return new_vae_or_unet


def convert_hf_clip_to_ppnlp_clip(clip, dtype="float32"):
    new_model_state = {}
    transformers2ppnlp = {
        ".encoder.": ".transformer.",
        ".layer_norm": ".norm",
        ".mlp.": ".",
        ".fc1.": ".linear1.",
        ".fc2.": ".linear2.",
        ".final_layer_norm.": ".ln_final.",
        ".embeddings.": ".",
        ".position_embedding.": ".positional_embedding.",
        ".patch_embedding.": ".conv1.",
        "visual_projection.weight": "vision_projection",
        "text_projection.weight": "text_projection",
        ".pre_layrnorm.": ".ln_pre.",
        ".post_layernorm.": ".ln_post.",
        ".vision_model.": ".",
    }
    ignore_value = ["position_ids"]
    donot_transpose = [
        "embeddings", "norm", "concept_embeds", "special_care_embeds"
    ]

    for name, value in clip.state_dict().items():
        # step1: ignore position_ids
        if any(i in name for i in ignore_value):
            continue
        # step2: transpose nn.Linear weight
        if value.ndim == 2 and not any(i in name for i in donot_transpose):
            value = value.t()
        # step3: hf_name -> ppnlp_name mapping
        for hf_name, ppnlp_name in transformers2ppnlp.items():
            name = name.replace(hf_name, ppnlp_name)
        # step4: 0d tensor -> 1d tensor
        if name == "logit_scale":
            value = value.reshape((1, ))

        new_model_state[name] = value.cpu().numpy().astype(dtype)

    new_config = {
        "max_text_length": clip.config.max_position_embeddings,
        "vocab_size": clip.config.vocab_size,
        "text_embed_dim": clip.config.hidden_size,
        "text_heads": clip.config.num_attention_heads,
        "text_layers": clip.config.num_hidden_layers,
        "text_hidden_act": clip.config.hidden_act,
        "projection_dim": clip.config.projection_dim,
        "initializer_range": clip.config.initializer_range,
        "initializer_factor": clip.config.initializer_factor,
    }
    return new_model_state, new_config


def check_keys(model, state_dict):
    cls_name = model.__class__.__name__
    missing_keys = []
    mismatched_keys = []
    for k, v in model.state_dict().items():
        if k not in state_dict.keys():
            missing_keys.append(k)
        if list(v.shape) != list(state_dict[k].shape):
            mismatched_keys.append(k)
    if len(missing_keys):
        missing_keys_str = ", ".join(missing_keys)
        print(f"{cls_name} Found missing_keys {missing_keys_str}!")
    if len(mismatched_keys):
        mismatched_keys_str = ", ".join(mismatched_keys)
        print(f"{cls_name} Found mismatched_keys {mismatched_keys_str}!")


def convert_diffusers_stable_diffusion2_0_depth_to_ppdiffusers(
        pretrained_model_name_or_path, output_path=None):
    # 0. load diffusers pipe and convert to ppdiffusers weights format
    diffusers_pipe = DiffusersStableDiffusionDepth2ImgPipeline.from_pretrained(
        pretrained_model_name_or_path, use_auth_token=True)
    vae_state_dict = convert_to_ppdiffusers(diffusers_pipe.vae)
    unet_state_dict = convert_to_ppdiffusers(diffusers_pipe.unet)
    depth_estimator_state_dict = convert_to_ppdiffusers(
        diffusers_pipe.depth_estimator)
    text_encoder_state_dict, text_encoder_config = convert_hf_clip_to_ppnlp_clip(
        diffusers_pipe.text_encoder)

    # 1. vae
    pp_vae = AutoencoderKL.from_config(diffusers_pipe.vae.config)
    pp_vae.set_dict(vae_state_dict)
    check_keys(pp_vae, vae_state_dict)
    # 2. unet
    pp_unet = UNet2DConditionModel.from_config(diffusers_pipe.unet.config)
    pp_unet.set_dict(unet_state_dict)
    check_keys(pp_unet, unet_state_dict)
    # 3. text_encoder
    pp_text_encoder = CLIPTextModel(
        CLIPTextConfig.from_dict(text_encoder_config))
    pp_text_encoder.set_dict(text_encoder_state_dict)
    check_keys(pp_text_encoder, text_encoder_state_dict)
    # 4. scheduler
    pp_scheduler = PNDMScheduler.from_config(diffusers_pipe.scheduler.config)

    with tempfile.TemporaryDirectory() as tmpdirname:
        # 5. depth_estimator
        diffusers_pipe.depth_estimator.config.save_pretrained(tmpdirname)
        config = DPTConfig.from_pretrained(tmpdirname, return_dict=True)
        pp_depth_estimator = DPTForDepthEstimation(config)
        pp_depth_estimator.set_dict(depth_estimator_state_dict)
        check_keys(pp_depth_estimator, depth_estimator_state_dict)
        # 6. tokenizer
        diffusers_pipe.tokenizer.save_pretrained(tmpdirname)
        pp_tokenizer = CLIPTokenizer.from_pretrained(tmpdirname)

        # 7. feature_extractor
        diffusers_pipe.feature_extractor.save_pretrained(tmpdirname)
        pp_feature_extractor = DPTImageProcessor.from_pretrained(tmpdirname)

        # 8. create ppdiffusers pipe
        paddle_pipe = PPDiffusersStableDiffusionDepth2ImgPipeline(
            vae=pp_vae,
            text_encoder=pp_text_encoder,
            tokenizer=pp_tokenizer,
            unet=pp_unet,
            feature_extractor=pp_feature_extractor,
            depth_estimator=pp_depth_estimator,
            scheduler=pp_scheduler, )

        # 9. save_pretrained
        paddle_pipe.save_pretrained(output_path)
    return paddle_pipe


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pytorch model weights to Paddle model weights.")
    parser.add_argument(
        "--pretrained_model_name_or_path",
        type=str,
        default="stabilityai/stable-diffusion-2-depth",
        help="Path to pretrained model or model identifier from huggingface.co/models.",
    )
    parser.add_argument(
        "--output_path",
        type=str,
        default="stable-diffusion-2-depth",
        help="The model output path.", )
    args = parser.parse_args()
    ppdiffusers_pipe = convert_diffusers_stable_diffusion2_0_depth_to_ppdiffusers(
        args.pretrained_model_name_or_path, args.output_path)
