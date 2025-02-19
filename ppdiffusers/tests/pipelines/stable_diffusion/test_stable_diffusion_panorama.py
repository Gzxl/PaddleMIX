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

import gc
import unittest

import numpy as np
import paddle
from paddlenlp.transformers import CLIPTextConfig, CLIPTextModel, CLIPTokenizer

from ppdiffusers import (AutoencoderKL, DDIMScheduler,
                         EulerAncestralDiscreteScheduler, LMSDiscreteScheduler,
                         PNDMScheduler, StableDiffusionPanoramaPipeline,
                         UNet2DConditionModel)
from ppdiffusers.utils import slow
from ppdiffusers.utils.testing_utils import require_paddle_gpu

from ..pipeline_params import TEXT_TO_IMAGE_BATCH_PARAMS, TEXT_TO_IMAGE_PARAMS
from ..test_pipelines_common import PipelineTesterMixin


class StableDiffusionPanoramaPipelineFastTests(PipelineTesterMixin,
                                               unittest.TestCase):
    pipeline_class = StableDiffusionPanoramaPipeline
    params = TEXT_TO_IMAGE_PARAMS
    batch_params = TEXT_TO_IMAGE_BATCH_PARAMS

    def get_dummy_components(self):
        paddle.seed(0)
        unet = UNet2DConditionModel(
            block_out_channels=(32, 64),
            layers_per_block=1,
            sample_size=32,
            in_channels=4,
            out_channels=4,
            down_block_types=("DownBlock2D", "CrossAttnDownBlock2D"),
            up_block_types=("CrossAttnUpBlock2D", "UpBlock2D"),
            cross_attention_dim=32, )
        scheduler = DDIMScheduler()
        paddle.seed(0)
        vae = AutoencoderKL(
            block_out_channels=[32, 64],
            in_channels=3,
            out_channels=3,
            down_block_types=["DownEncoderBlock2D", "DownEncoderBlock2D"],
            up_block_types=["UpDecoderBlock2D", "UpDecoderBlock2D"],
            latent_channels=4, )
        paddle.seed(0)
        text_encoder_config = CLIPTextConfig(
            bos_token_id=0,
            eos_token_id=2,
            hidden_size=32,
            intermediate_size=37,
            layer_norm_eps=1e-05,
            num_attention_heads=4,
            num_hidden_layers=5,
            pad_token_id=1,
            vocab_size=1000, )
        text_encoder = CLIPTextModel(text_encoder_config).eval()
        tokenizer = CLIPTokenizer.from_pretrained(
            "hf-internal-testing/tiny-random-clip")
        components = {
            "unet": unet,
            "scheduler": scheduler,
            "vae": vae,
            "text_encoder": text_encoder,
            "tokenizer": tokenizer,
            "safety_checker": None,
            "feature_extractor": None,
        }
        return components

    def get_dummy_inputs(self, seed=0):
        generator = paddle.Generator().manual_seed(seed=seed)
        inputs = {
            "prompt": "a photo of the dolomites",
            "generator": generator,
            "height": None,
            "width": None,
            "num_inference_steps": 1,
            "guidance_scale": 6.0,
            "output_type": "numpy",
        }
        return inputs

    def test_stable_diffusion_panorama_default_case(self):
        components = self.get_dummy_components()
        sd_pipe = StableDiffusionPanoramaPipeline(**components)
        sd_pipe.set_progress_bar_config(disable=None)
        inputs = self.get_dummy_inputs()
        image = sd_pipe(**inputs).images
        image_slice = image[0, -3:, -3:, -1]
        assert image.shape == (1, 64, 64, 3)
        expected_slice = np.array([
            0.28862977,
            0.2441951,
            0.2683525,
            0.33122095,
            0.28755113,
            0.46375293,
            0.254181,
            0.30616608,
            0.4785265,
        ])
        assert np.abs(image_slice.flatten() - expected_slice).max() < 0.01

    # override to speed the overall test timing up.
    def test_inference_batch_consistent(self):
        super().test_inference_batch_consistent(batch_sizes=[1, 2])

    # override to speed the overall test timing up.
    def test_inference_batch_single_identical(self):
        super().test_inference_batch_single_identical(batch_size=2)

    def test_stable_diffusion_panorama_negative_prompt(self):
        components = self.get_dummy_components()
        sd_pipe = StableDiffusionPanoramaPipeline(**components)
        sd_pipe.set_progress_bar_config(disable=None)
        inputs = self.get_dummy_inputs()
        negative_prompt = "french fries"
        output = sd_pipe(**inputs, negative_prompt=negative_prompt)
        image = output.images
        image_slice = image[0, -3:, -3:, -1]
        assert image.shape == (1, 64, 64, 3)
        expected_slice = np.array([
            0.28995812,
            0.24463832,
            0.2682391,
            0.33033937,
            0.2868188,
            0.46267676,
            0.25425047,
            0.3066897,
            0.47881347,
        ])
        assert np.abs(image_slice.flatten() - expected_slice).max() < 0.01

    def test_stable_diffusion_panorama_euler(self):
        components = self.get_dummy_components()
        components["scheduler"] = EulerAncestralDiscreteScheduler(
            beta_start=0.00085, beta_end=0.012, beta_schedule="scaled_linear")
        sd_pipe = StableDiffusionPanoramaPipeline(**components)
        sd_pipe.set_progress_bar_config(disable=None)
        inputs = self.get_dummy_inputs()
        image = sd_pipe(**inputs).images
        image_slice = image[0, -3:, -3:, -1]
        assert image.shape == (1, 64, 64, 3)
        expected_slice = np.array([
            0.32409406,
            0.2660764,
            0.41739762,
            0.18994612,
            0.32522476,
            0.4869789,
            0.13573006,
            0.14128971,
            0.32650158,
        ])
        assert np.abs(image_slice.flatten() - expected_slice).max() < 0.01

    def test_stable_diffusion_panorama_pndm(self):
        components = self.get_dummy_components()
        components["scheduler"] = PNDMScheduler()
        sd_pipe = StableDiffusionPanoramaPipeline(**components)
        sd_pipe.set_progress_bar_config(disable=None)
        inputs = self.get_dummy_inputs()
        with self.assertRaises(ValueError):
            _ = sd_pipe(**inputs).images


@slow
@require_paddle_gpu
class StableDiffusionPanoramaSlowTests(unittest.TestCase):
    def tearDown(self):
        super().tearDown()
        gc.collect()
        paddle.device.cuda.empty_cache()

    def get_inputs(self, seed=0):
        generator = paddle.Generator().manual_seed(seed=seed)
        inputs = {
            "prompt": "a photo of the dolomites",
            "generator": generator,
            "num_inference_steps": 3,
            "guidance_scale": 7.5,
            "output_type": "numpy",
        }
        return inputs

    def test_stable_diffusion_panorama_default(self):
        model_ckpt = "stabilityai/stable-diffusion-2-base"
        scheduler = DDIMScheduler.from_pretrained(
            model_ckpt, subfolder="scheduler")
        pipe = StableDiffusionPanoramaPipeline.from_pretrained(
            model_ckpt, scheduler=scheduler, safety_checker=None)
        pipe.set_progress_bar_config(disable=None)
        pipe.enable_attention_slicing()
        inputs = self.get_inputs()
        image = pipe(**inputs).images
        image_slice = image[0, -3:, -3:, -1].flatten()
        assert image.shape == (1, 512, 2048, 3)
        expected_slice = np.array([
            0.34261876,
            0.3045774,
            0.34545267,
            0.33774284,
            0.3431282,
            0.33453488,
            0.3094663,
            0.32646674,
            0.32534528,
        ])
        assert np.abs(expected_slice - image_slice).max() < 0.01

    def test_stable_diffusion_panorama_k_lms(self):
        pipe = StableDiffusionPanoramaPipeline.from_pretrained(
            "stabilityai/stable-diffusion-2-base", safety_checker=None)
        pipe.scheduler = LMSDiscreteScheduler.from_config(pipe.scheduler.config)
        pipe.set_progress_bar_config(disable=None)
        pipe.enable_attention_slicing()
        inputs = self.get_inputs()
        image = pipe(**inputs).images
        image_slice = image[0, -3:, -3:, -1].flatten()
        assert image.shape == (1, 512, 2048, 3)
        expected_slice = np.array([
            0.0,
            0.01188838,
            0.02675471,
            0.00534895,
            0.02325496,
            0.01234779,
            0.0348064,
            0.0,
            0.02607787,
        ])
        assert np.abs(expected_slice - image_slice).max() < 0.01

    def test_stable_diffusion_panorama_intermediate_state(self):
        number_of_steps = 0

        def callback_fn(step: int, timestep: int,
                        latents: paddle.Tensor) -> None:
            callback_fn.has_been_called = True
            nonlocal number_of_steps
            number_of_steps += 1
            if step == 1:
                latents = latents.detach().cpu().numpy()
                assert latents.shape == (1, 4, 64, 256)
                latents_slice = latents[0, -3:, -3:, -1]
                expected_slice = np.array([
                    0.7392851114273071,
                    -0.16683124005794525,
                    0.2063215672969818,
                    -0.09840865433216095,
                    0.18722617626190186,
                    -0.08375956118106842,
                    0.06995373964309692,
                    -0.20892930030822754,
                    -0.157355397939682,
                ])
                assert np.abs(latents_slice.flatten() - expected_slice).max(
                ) < 0.05
            elif step == 2:
                latents = latents.detach().cpu().numpy()
                assert latents.shape == (1, 4, 64, 256)
                latents_slice = latents[0, -3:, -3:, -1]
                expected_slice = np.array([
                    0.7368452548980713,
                    -0.16317462921142578,
                    0.20289096236228943,
                    -0.10271137207746506,
                    0.1873130351305008,
                    -0.08454630523920059,
                    0.06944799423217773,
                    -0.20782311260700226,
                    -0.15696658194065094,
                ])
                assert np.abs(latents_slice.flatten() - expected_slice).max(
                ) < 0.05

        callback_fn.has_been_called = False
        model_ckpt = "stabilityai/stable-diffusion-2-base"
        scheduler = DDIMScheduler.from_pretrained(
            model_ckpt, subfolder="scheduler")
        pipe = StableDiffusionPanoramaPipeline.from_pretrained(
            model_ckpt, scheduler=scheduler, safety_checker=None)
        pipe.set_progress_bar_config(disable=None)
        pipe.enable_attention_slicing()
        inputs = self.get_inputs()
        pipe(**inputs, callback=callback_fn, callback_steps=1)
        assert callback_fn.has_been_called
        assert number_of_steps == 3
