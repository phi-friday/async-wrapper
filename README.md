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

import time

import anyio

from async_wrapper import TaskGroupWrapper, async_to_sync


@async_to_sync("thread")
async def sample_func() -> int:
    await anyio.sleep(1)
    return 1


async def sample_func_2(x: int) -> int:
    await anyio.sleep(1)
    return x


def main():
    result = sample_func()
    assert isinstance(result, int)
    assert result == 1


async def async_main():
    semaphore = anyio.Semaphore(2)

    start = time.perf_counter()
    async with anyio.create_task_group() as task_group:
        wrapper = TaskGroupWrapper(task_group)
        func = wrapper.wrap(sample_func_2, semaphore)
        value_1 = func(1)
        value_2 = func(2)
        value_3 = func(3)
    end = time.perf_counter()

    assert isinstance(value_1.value, int)
    assert isinstance(value_2.value, int)
    assert isinstance(value_3.value, int)
    assert value_1.value == 1
    assert value_2.value == 2
    assert value_3.value == 3
    assert 1.5 < end - start < 2.5


if __name__ == "__main__":
    main()
    anyio.run(async_main)
```

## License

MIT, see [LICENSE](https://github.com/phi-friday/async-wrapper/blob/main/LICENSE).
