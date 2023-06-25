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
$ pip install "async_wrapper[anyio]"
# or
$ pip install "async_wrapper[joblib]"
```

## how to use
```python
import asyncio

from aiotools import TaskGroup
# or(>=py311)
# from asyncio.taskgroups import TaskGroup

from async_wrapper import async_to_sync, get_taskgroup_wrapper


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
    wrapper = get_taskgroup_wrapper("asyncio")
    async with TaskGroup() as task_group:
        value_1 = wrapper(sample_func_2, task_group)(1)
        value_2 = wrapper(sample_func_2, task_group)(2)

    assert isinstance(value_1.value, int)
    assert isinstance(value_2.value, int)
    assert value_1.value == 1
    assert value_2.value == 2
```

## License

MIT, see [LICENSE](https://github.com/phi-friday/async-wrapper/blob/main/LICENSE).
