# async-wrapper

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![github action](https://github.com/phi-friday/async-wrapper/actions/workflows/check.yaml/badge.svg?event=push&branch=dev)](#)
[![PyPI version](https://badge.fury.io/py/async-wrapper.svg)](https://badge.fury.io/py/async-wrapper)
[![python version](https://img.shields.io/pypi/pyversions/async_wrapper.svg)](#)

## how to install
```shell
$ pip install async_wrapper
# or
$ pip install "async_wrapper[all]"
# or
$ pip install "async_wrapper[loky]"
```

## how to use
```python
from __future__ import annotations

import asyncio
import time

from async_wrapper import (
    async_to_sync,
    get_semaphore_class,
    get_task_group_factory,
    get_task_group_wrapper,
)


@async_to_sync("thread")
async def sample_func() -> int:
    await asyncio.sleep(1)
    return 1


result = sample_func()
assert isinstance(result, int)
assert result == 1


async def sample_func_2(x: int) -> int:
    await asyncio.sleep(1)
    return x


async def main():
    wrapper = get_task_group_wrapper("asyncio")
    factory = get_task_group_factory("asyncio")
    Semaphore = get_semaphore_class("asyncio")
    semaphore = Semaphore(2)

    start = time.perf_counter()
    async with factory() as task_group:
        wrapped = wrapper(sample_func_2, task_group, semaphore)
        value_1 = wrapped(1)
        value_2 = wrapped(2)
        value_3 = wrapped(3)
    end = time.perf_counter()

    assert isinstance(value_1.value, int)
    assert isinstance(value_2.value, int)
    assert isinstance(value_3.value, int)
    assert value_1.value == 1
    assert value_2.value == 2
    assert value_3.value == 3
    assert 1.5 < end - start < 2.5
```

## License

MIT, see [LICENSE](https://github.com/phi-friday/async-wrapper/blob/main/LICENSE).
