# Copyright (c) 2023  PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"
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

from setuptools import find_packages, setup

description = "PaddleMIX"

with open("requirements.txt") as fin:
    REQUIRED_PACKAGES = fin.read()


def read(file: str):
    current_dir = os.path.dirname(__file__)
    path = os.path.join(current_dir, file)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    return content


def read_version():
    """read version of paddlemix"""
    return read("VERSION")


def read_readme():
    “”“read readme of paddlemix”“”
    return read("README.md")


def read_requirements():
    content = read("requirements.txt")
    packages = content.split("\n")
    return packages


setup(
    name="paddlemix",
    packages=(find_packages() + find_packages(
        where="./ppdiffusers", exclude=["tests", "tests.*"])),
    package_dir={
        "": ".",
        "ppdiffusers": "./ppdiffusers/ppdiffusers",
    },
    version=read_version(),
    author="PaddleMIX Team",
    author_email="paddlemix@baidu.com",
    description=description,
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    url="",
    keywords=["paddle", "paddlemix"],
    install_requires=REQUIRED_PACKAGES,
    python_requires=">=3.6",
    entry_points={
        "console_scripts":
        ["ppdiffusers-cli=ppdiffusers.commands.ppdiffusers_cli:main"]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    license="Apache 2.0", )
