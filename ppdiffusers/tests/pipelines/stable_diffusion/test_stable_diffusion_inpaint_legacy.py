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
import random
import unittest

import numpy as np
import paddle
from paddlenlp.transformers import CLIPTextConfig, CLIPTextModel, CLIPTokenizer
from PIL import Image

from ppdiffusers import (AutoencoderKL, DDIMScheduler,
                         DPMSolverMultistepScheduler, LMSDiscreteScheduler,
                         PNDMScheduler, StableDiffusionInpaintPipelineLegacy,
                         UNet2DConditionModel, UNet2DModel, VQModel)
from ppdiffusers.utils import floats_tensor, load_image, nightly, slow
from ppdiffusers.utils.testing_utils import (load_numpy, preprocess_image,
                                             require_paddle_gpu)


class StableDiffusionInpaintLegacyPipelineFastTests(unittest.TestCase):
    def tearDown(self):
        super().tearDown()
        gc.collect()
        paddle.device.cuda.empty_cache()

    @property
    def dummy_image(self):
        batch_size = 1
        num_channels = 3
        sizes = 32, 32
        image = floats_tensor(
            (batch_size, num_channels) + sizes, rng=random.Random(0))
        return image

    @property
    def dummy_uncond_unet(self):
        paddle.seed(0)
        model = UNet2DModel(
            block_out_channels=(32, 64),
            layers_per_block=2,
            sample_size=32,
            in_channels=3,
            out_channels=3,
            down_block_types=("DownBlock2D", "AttnDownBlock2D"),
            up_block_types=("AttnUpBlock2D", "UpBlock2D"), )
        return model

    @property
    def dummy_cond_unet(self):
        paddle.seed(0)
        model = UNet2DConditionModel(
            block_out_channels=(32, 64),
            layers_per_block=2,
            sample_size=32,
            in_channels=4,
            out_channels=4,
            down_block_types=("DownBlock2D", "CrossAttnDownBlock2D"),
            up_block_types=("CrossAttnUpBlock2D", "UpBlock2D"),
            cross_attention_dim=32, )
        return model

    @property
    def dummy_cond_unet_inpaint(self):
        paddle.seed(0)
        model = UNet2DConditionModel(
            block_out_channels=(32, 64),
            layers_per_block=2,
            sample_size=32,
            in_channels=9,
            out_channels=4,
            down_block_types=("DownBlock2D", "CrossAttnDownBlock2D"),
            up_block_types=("CrossAttnUpBlock2D", "UpBlock2D"),
            cross_attention_dim=32, )
        return model

    @property
    def dummy_vq_model(self):
        paddle.seed(0)
        model = VQModel(
            block_out_channels=[32, 64],
            in_channels=3,
            out_channels=3,
            down_block_types=["DownEncoderBlock2D", "DownEncoderBlock2D"],
            up_block_types=["UpDecoderBlock2D", "UpDecoderBlock2D"],
            latent_channels=3, )
        return model

    @property
    def dummy_vae(self):
        paddle.seed(0)
        model = AutoencoderKL(
            block_out_channels=[32, 64],
            in_channels=3,
            out_channels=3,
            down_block_types=["DownEncoderBlock2D", "DownEncoderBlock2D"],
            up_block_types=["UpDecoderBlock2D", "UpDecoderBlock2D"],
            latent_channels=4, )
        return model

    @property
    def dummy_text_encoder(self):
        paddle.seed(0)
        config = CLIPTextConfig(
            bos_token_id=0,
            eos_token_id=2,
            hidden_size=32,
            intermediate_size=37,
            layer_norm_eps=1e-05,
            num_attention_heads=4,
            num_hidden_layers=5,
            pad_token_id=1,
            vocab_size=1000, )
        return CLIPTextModel(config).eval()

    @property
    def dummy_extractor(self):
        def extract(*args, **kwargs):
            class Out:
                def __init__(self):
                    self.pixel_values = paddle.ones(shape=[0])

                def to(self, device):
                    self.pixel_values
                    return self

            return Out()

        return extract

    def test_stable_diffusion_inpaint_legacy(self):
        unet = self.dummy_cond_unet
        scheduler = PNDMScheduler(skip_prk_steps=True)
        vae = self.dummy_vae
        bert = self.dummy_text_encoder
        tokenizer = CLIPTokenizer.from_pretrained(
            "hf-internal-testing/tiny-random-clip")
        image = self.dummy_image.cpu().transpose(perm=[0, 2, 3, 1])[0]
        init_image = Image.fromarray(np.uint8(image)).convert("RGB")
        mask_image = (
            Image.fromarray(np.uint8(image + 4)).convert("RGB").resize(
                (32, 32)))
        sd_pipe = StableDiffusionInpaintPipelineLegacy(
            unet=unet,
            scheduler=scheduler,
            vae=vae,
            text_encoder=bert,
            tokenizer=tokenizer,
            safety_checker=None,
            feature_extractor=self.dummy_extractor, )
        sd_pipe.set_progress_bar_config(disable=None)
        prompt = "A painting of a squirrel eating a burger"
        generator = paddle.Generator().manual_seed(0)
        output = sd_pipe(
            [prompt],
            generator=generator,
            guidance_scale=6.0,
            num_inference_steps=2,
            output_type="np",
            image=init_image,
            mask_image=mask_image, )
        image = output.images
        generator = paddle.Generator().manual_seed(0)
        image_from_tuple = sd_pipe(
            [prompt],
            generator=generator,
            guidance_scale=6.0,
            num_inference_steps=2,
            output_type="np",
            image=init_image,
            mask_image=mask_image,
            return_dict=False, )[0]
        image_slice = image[0, -3:, -3:, -1]
        image_from_tuple_slice = image_from_tuple[0, -3:, -3:, -1]
        assert image.shape == (1, 32, 32, 3)
        expected_slice = np.array([
            0.01514593,
            0.46352747,
            0.34991893,
            0.29177475,
            0.5415823,
            0.56992227,
            0.39533705,
            0.67953515,
            0.5445507,
        ])
        assert np.abs(image_slice.flatten() - expected_slice).max() < 0.01
        assert np.abs(image_from_tuple_slice.flatten() - expected_slice).max(
        ) < 0.01

    def test_stable_diffusion_inpaint_legacy_batched(self):
        unet = self.dummy_cond_unet
        scheduler = PNDMScheduler(skip_prk_steps=True)
        vae = self.dummy_vae
        bert = self.dummy_text_encoder
        tokenizer = CLIPTokenizer.from_pretrained(
            "hf-internal-testing/tiny-random-clip")

        image = self.dummy_image.permute(0, 2, 3, 1)[0]
        init_image = Image.fromarray(np.uint8(image)).convert("RGB")
        init_images_tens = preprocess_image(init_image, batch_size=2)
        init_masks_tens = init_images_tens + 4

        # make sure here that pndm scheduler skips prk
        sd_pipe = StableDiffusionInpaintPipelineLegacy(
            unet=unet,
            scheduler=scheduler,
            vae=vae,
            text_encoder=bert,
            tokenizer=tokenizer,
            safety_checker=None,
            feature_extractor=self.dummy_extractor, )
        sd_pipe.set_progress_bar_config(disable=None)

        prompt = "A painting of a squirrel eating a burger"
        generator = paddle.Generator().manual_seed(0)
        images = sd_pipe(
            [prompt] * 2,
            generator=generator,
            guidance_scale=6.0,
            num_inference_steps=2,
            output_type="np",
            image=init_images_tens,
            mask_image=init_masks_tens, ).images

        assert images.shape == (2, 32, 32, 3)

        image_slice_0 = images[0, -3:, -3:, -1].flatten()
        image_slice_1 = images[1, -3:, -3:, -1].flatten()

        expected_slice_0 = np.array([
            0.50299895,
            0.6465979,
            0.3489662,
            0.28862774,
            0.59657216,
            0.41669005,
            0.19621253,
            0.27549136,
            0.39040852,
        ])
        expected_slice_1 = np.array([
            0.70079666,
            0.5616544,
            0.5304112,
            0.38820785,
            0.3118701,
            0.47477302,
            0.37215403,
            0.3785481,
            0.50153226,
        ])

        assert np.abs(expected_slice_0 - image_slice_0).max() < 1e-2
        assert np.abs(expected_slice_1 - image_slice_1).max() < 1e-2

    def test_stable_diffusion_inpaint_legacy_negative_prompt(self):
        unet = self.dummy_cond_unet
        scheduler = PNDMScheduler(skip_prk_steps=True)
        vae = self.dummy_vae
        bert = self.dummy_text_encoder
        tokenizer = CLIPTokenizer.from_pretrained(
            "hf-internal-testing/tiny-random-clip")
        image = self.dummy_image.cpu().transpose(perm=[0, 2, 3, 1])[0]
        init_image = Image.fromarray(np.uint8(image)).convert("RGB")
        mask_image = (
            Image.fromarray(np.uint8(image + 4)).convert("RGB").resize(
                (32, 32)))
        sd_pipe = StableDiffusionInpaintPipelineLegacy(
            unet=unet,
            scheduler=scheduler,
            vae=vae,
            text_encoder=bert,
            tokenizer=tokenizer,
            safety_checker=None,
            feature_extractor=self.dummy_extractor, )
        sd_pipe.set_progress_bar_config(disable=None)
        prompt = "A painting of a squirrel eating a burger"
        negative_prompt = "french fries"
        generator = paddle.Generator().manual_seed(0)
        output = sd_pipe(
            prompt,
            negative_prompt=negative_prompt,
            generator=generator,
            guidance_scale=6.0,
            num_inference_steps=2,
            output_type="np",
            image=init_image,
            mask_image=mask_image, )
        image = output.images
        image_slice = image[0, -3:, -3:, -1]
        assert image.shape == (1, 32, 32, 3)
        expected_slice = np.array([
            0.0,
            0.43941003,
            0.32130337,
            0.31442684,
            0.566114,
            0.56392324,
            0.3946159,
            0.6844422,
            0.5345681,
        ])
        assert np.abs(image_slice.flatten() - expected_slice).max() < 0.01

    def test_stable_diffusion_inpaint_legacy_num_images_per_prompt(self):
        unet = self.dummy_cond_unet
        scheduler = PNDMScheduler(skip_prk_steps=True)
        vae = self.dummy_vae
        bert = self.dummy_text_encoder
        tokenizer = CLIPTokenizer.from_pretrained(
            "hf-internal-testing/tiny-random-clip")
        image = self.dummy_image.cpu().transpose(perm=[0, 2, 3, 1])[0]
        init_image = Image.fromarray(np.uint8(image)).convert("RGB")
        mask_image = (
            Image.fromarray(np.uint8(image + 4)).convert("RGB").resize(
                (32, 32)))
        sd_pipe = StableDiffusionInpaintPipelineLegacy(
            unet=unet,
            scheduler=scheduler,
            vae=vae,
            text_encoder=bert,
            tokenizer=tokenizer,
            safety_checker=None,
            feature_extractor=self.dummy_extractor, )
        sd_pipe.set_progress_bar_config(disable=None)
        prompt = "A painting of a squirrel eating a burger"
        images = sd_pipe(
            prompt,
            num_inference_steps=2,
            output_type="np",
            image=init_image,
            mask_image=mask_image, ).images
        assert images.shape == (1, 32, 32, 3)
        batch_size = 2
        images = sd_pipe(
            [prompt] * batch_size,
            num_inference_steps=2,
            output_type="np",
            image=init_image,
            mask_image=mask_image, ).images
        assert images.shape == (batch_size, 32, 32, 3)
        num_images_per_prompt = 2
        images = sd_pipe(
            prompt,
            num_inference_steps=2,
            output_type="np",
            image=init_image,
            mask_image=mask_image,
            num_images_per_prompt=num_images_per_prompt, ).images
        assert images.shape == (num_images_per_prompt, 32, 32, 3)
        batch_size = 2
        images = sd_pipe(
            [prompt] * batch_size,
            num_inference_steps=2,
            output_type="np",
            image=init_image,
            mask_image=mask_image,
            num_images_per_prompt=num_images_per_prompt, ).images
        assert images.shape == (batch_size * num_images_per_prompt, 32, 32, 3)


@slow
@require_paddle_gpu
class StableDiffusionInpaintLegacyPipelineSlowTests(unittest.TestCase):
    def tearDown(self):
        super().tearDown()
        gc.collect()
        paddle.device.cuda.empty_cache()

    def get_inputs(self, seed=0):
        generator = paddle.Generator().manual_seed(seed)
        init_image = load_image(
            "https://paddlenlp.bj.bcebos.com/data/images/input_bench_image.png")
        mask_image = load_image(
            "https://paddlenlp.bj.bcebos.com/data/images/input_bench_mask.png")
        inputs = {
            "prompt": "A red cat sitting on a park bench",
            "image": init_image,
            "mask_image": mask_image,
            "generator": generator,
            "num_inference_steps": 3,
            "strength": 0.75,
            "guidance_scale": 7.5,
            "output_type": "numpy",
        }
        return inputs

    def test_stable_diffusion_inpaint_legacy_pndm(self):
        pipe = StableDiffusionInpaintPipelineLegacy.from_pretrained(
            "CompVis/stable-diffusion-v1-4", safety_checker=None)
        pipe.set_progress_bar_config(disable=None)
        pipe.enable_attention_slicing()
        inputs = self.get_inputs()
        image = pipe(**inputs).images
        image_slice = image[0, 253:256, 253:256, -1].flatten()
        assert image.shape == (1, 512, 512, 3)
        expected_slice = np.array([
            0.27226633,
            0.29068208,
            0.3450312,
            0.21444553,
            0.26328486,
            0.34392387,
            0.18026042,
            0.24961185,
            0.3214044,
        ])
        assert np.abs(expected_slice - image_slice).max() < 0.0001

    def test_stable_diffusion_inpaint_legacy_batched(self):
        pipe = StableDiffusionInpaintPipelineLegacy.from_pretrained(
            "CompVis/stable-diffusion-v1-4", safety_checker=None)
        pipe.set_progress_bar_config(disable=None)
        pipe.enable_attention_slicing()

        inputs = self.get_inputs()
        inputs["prompt"] = [inputs["prompt"]] * 2
        inputs["image"] = preprocess_image(inputs["image"], batch_size=2)

        mask = inputs["mask_image"].convert("L")
        mask = np.array(mask).astype(np.float32) / 255.0
        mask = paddle.to_tensor(1 - mask)
        masks = paddle.stack([mask[None]] * 2, axis=0)
        inputs["mask_image"] = masks

        image = pipe(**inputs).images
        assert image.shape == (2, 512, 512, 3)

        image_slice_0 = image[0, 253:256, 253:256, -1].flatten()
        image_slice_1 = image[1, 253:256, 253:256, -1].flatten()

        expected_slice_0 = np.array([
            0.27526367,
            0.29158682,
            0.35184938,
            0.21504477,
            0.26708275,
            0.35169,
            0.18185198,
            0.2572803,
            0.32425082,
        ])
        expected_slice_1 = np.array([
            0.0,
            0.18929192,
            0.7068148,
            0.07977328,
            0.13444492,
            0.5016247,
            0.49761847,
            0.2830933,
            0.36412603,
        ])

        assert np.abs(expected_slice_0 - image_slice_0).max() < 1e-4
        assert np.abs(expected_slice_1 - image_slice_1).max() < 1e-4

    def test_stable_diffusion_inpaint_legacy_k_lms(self):
        pipe = StableDiffusionInpaintPipelineLegacy.from_pretrained(
            "CompVis/stable-diffusion-v1-4", safety_checker=None)
        pipe.scheduler = LMSDiscreteScheduler.from_config(pipe.scheduler.config)
        pipe.set_progress_bar_config(disable=None)
        pipe.enable_attention_slicing()
        inputs = self.get_inputs()
        image = pipe(**inputs).images
        image_slice = image[0, 253:256, 253:256, -1].flatten()
        assert image.shape == (1, 512, 512, 3)
        expected_slice = np.array([
            0.29036117,
            0.28907132,
            0.32839334,
            0.26510137,
            0.2820784,
            0.31148806,
            0.29358387,
            0.29515788,
            0.28257304,
        ])
        assert np.abs(expected_slice - image_slice).max() < 0.0001

    def test_stable_diffusion_inpaint_legacy_intermediate_state(self):
        number_of_steps = 0

        def callback_fn(step: int, timestep: int,
                        latents: paddle.Tensor) -> None:
            callback_fn.has_been_called = True
            nonlocal number_of_steps
            number_of_steps += 1
            if step == 1:
                latents = latents.detach().cpu().numpy()
                assert latents.shape == (1, 4, 64, 64)
                latents_slice = latents[0, -3:, -3:, -1]
                expected_slice = np.array([
                    -0.103,
                    1.415,
                    -0.02197,
                    -0.5103,
                    -0.5903,
                    0.1953,
                    0.75,
                    0.3477,
                    -1.356,
                ])
                assert np.abs(latents_slice.flatten() - expected_slice).max(
                ) < 0.001
            elif step == 2:
                latents = latents.detach().cpu().numpy()
                assert latents.shape == (1, 4, 64, 64)
                latents_slice = latents[0, -3:, -3:, -1]
                expected_slice = np.array([
                    0.4802,
                    1.154,
                    0.628,
                    0.2322,
                    0.2593,
                    -0.1455,
                    0.7075,
                    -0.1617,
                    -0.5615,
                ])
                assert np.abs(latents_slice.flatten() - expected_slice).max(
                ) < 0.001

        callback_fn.has_been_called = False
        pipe = StableDiffusionInpaintPipelineLegacy.from_pretrained(
            "CompVis/stable-diffusion-v1-4",
            safety_checker=None,
            paddle_dtype=paddle.float16, )
        pipe.set_progress_bar_config(disable=None)
        pipe.enable_attention_slicing()
        inputs = self.get_inputs()
        pipe(**inputs, callback=callback_fn, callback_steps=1)
        assert callback_fn.has_been_called
        assert number_of_steps == 2


@nightly
@require_paddle_gpu
class StableDiffusionInpaintLegacyPipelineNightlyTests(unittest.TestCase):
    def tearDown(self):
        super().tearDown()
        gc.collect()
        paddle.device.cuda.empty_cache()

    def get_inputs(self, dtype="float32", seed=0):
        generator = paddle.Generator().manual_seed(seed)
        init_image = load_image(
            "https://huggingface.co/datasets/diffusers/test-arrays/resolve/main/stable_diffusion_inpaint/input_bench_image.png"
        )
        mask_image = load_image(
            "https://huggingface.co/datasets/diffusers/test-arrays/resolve/main/stable_diffusion_inpaint/input_bench_mask.png"
        )
        inputs = {
            "prompt": "A red cat sitting on a park bench",
            "image": init_image,
            "mask_image": mask_image,
            "generator": generator,
            "num_inference_steps": 50,
            "strength": 0.75,
            "guidance_scale": 7.5,
            "output_type": "numpy",
        }
        return inputs

    def test_inpaint_pndm(self):
        sd_pipe = StableDiffusionInpaintPipelineLegacy.from_pretrained(
            "runwayml/stable-diffusion-v1-5")
        sd_pipe
        sd_pipe.set_progress_bar_config(disable=None)
        inputs = self.get_inputs()
        image = sd_pipe(**inputs).images[0]
        expected_image = np.array([[0.7330009, 0.80003107, 0.8268216],
                                   [0.73606366, 0.801595, 0.8470554]])
        max_diff = np.abs(expected_image - image[0][0:2]).max()
        assert max_diff < 0.001

    def test_inpaint_ddim(self):
        sd_pipe = StableDiffusionInpaintPipelineLegacy.from_pretrained(
            "runwayml/stable-diffusion-v1-5")
        sd_pipe.scheduler = DDIMScheduler.from_config(sd_pipe.scheduler.config)
        sd_pipe
        sd_pipe.set_progress_bar_config(disable=None)
        inputs = self.get_inputs()
        image = sd_pipe(**inputs).images[0]
        expected_image = load_numpy(
            "https://huggingface.co/datasets/diffusers/test-arrays/resolve/main/stable_diffusion_inpaint_legacy/stable_diffusion_1_5_ddim.npy"
        )
        expected_image = np.array([[0.7290994, 0.794852, 0.82096446],
                                   [0.7330909, 0.79727536, 0.8420528]])
        max_diff = np.abs(expected_image - image[0][0:2]).max()
        assert max_diff < 0.001

    def test_inpaint_lms(self):
        sd_pipe = StableDiffusionInpaintPipelineLegacy.from_pretrained(
            "runwayml/stable-diffusion-v1-5")
        sd_pipe.scheduler = LMSDiscreteScheduler.from_config(
            sd_pipe.scheduler.config)
        sd_pipe
        sd_pipe.set_progress_bar_config(disable=None)
        inputs = self.get_inputs()
        image = sd_pipe(**inputs).images[0]
        expected_image = np.array([[0.74595624, 0.81757987, 0.84589916],
                                   [0.74728143, 0.81736475, 0.86543]])
        max_diff = np.abs(expected_image - image[0][0:2]).max()
        assert max_diff < 0.001

    def test_inpaint_dpm(self):
        sd_pipe = StableDiffusionInpaintPipelineLegacy.from_pretrained(
            "runwayml/stable-diffusion-v1-5")
        sd_pipe.scheduler = DPMSolverMultistepScheduler.from_config(
            sd_pipe.scheduler.config)
        sd_pipe
        sd_pipe.set_progress_bar_config(disable=None)
        inputs = self.get_inputs()
        inputs["num_inference_steps"] = 30
        image = sd_pipe(**inputs).images[0]
        expected_image = np.array([[0.7310472, 0.7970823, 0.8231524],
                                   [0.7348697, 0.799358, 0.8439586]])
        max_diff = np.abs(expected_image - image[0][0:2]).max()
        assert max_diff < 0.001
