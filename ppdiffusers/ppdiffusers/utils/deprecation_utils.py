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

import inspect
import warnings
from typing import Any, Dict, Optional, Union

from packaging import version


def deprecate(
        *args,
        take_from: Optional[Union[Dict, Any]]=None,
        standard_warn=True,
        stacklevel=2, ):
    from ..version import VERSION as __version__

    deprecated_kwargs = take_from
    values = ()
    if not isinstance(args[0], tuple):
        args = (args, )

    for attribute, version_name, message in args:
        if version.parse(version.parse(__version__)
                         .base_version) >= version.parse(version_name):
            raise ValueError(
                f"The deprecation tuple {(attribute, version_name, message)} should be removed since ppdiffusers'"
                f" version {__version__} is >= {version_name}")

        warning = None
        if isinstance(deprecated_kwargs,
                      dict) and attribute in deprecated_kwargs:
            values += (deprecated_kwargs.pop(attribute), )
            warning = f"The `{attribute}` argument is deprecated and will be removed in version {version_name}."
        elif hasattr(deprecated_kwargs, attribute):
            values += (getattr(deprecated_kwargs, attribute), )
            warning = f"The `{attribute}` attribute is deprecated and will be removed in version {version_name}."
        elif deprecated_kwargs is None:
            warning = f"`{attribute}` is deprecated and will be removed in version {version_name}."

        if warning is not None:
            warning = warning + " " if standard_warn else ""
            warnings.warn(
                warning + message, FutureWarning, stacklevel=stacklevel)

    if isinstance(deprecated_kwargs, dict) and len(deprecated_kwargs) > 0:
        call_frame = inspect.getouterframes(inspect.currentframe())[1]
        filename = call_frame.filename
        line_number = call_frame.lineno
        function = call_frame.function
        key, value = next(iter(deprecated_kwargs.items()))
        raise TypeError(
            f"{function} in {filename} line {line_number-1} got an unexpected keyword argument `{key}`"
        )

    if len(values) == 0:
        return
    elif len(values) == 1:
        return values[0]
    return values
