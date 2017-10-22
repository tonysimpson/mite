import time
import asyncio
import random

from .exceptions import MiteError
from .context import Context, add_context_extensions
from .runner import RunnerConfig


def test_context(extensions=('http',), **config):
    runner_config = RunnerConfig()
    runner_config._update(config.items())
    c = Context(print, runner_config)
    add_context_extensions(c, extensions)
    return c


class ensure_seperation_from_callable:
    def __init__(self, sep_callable, loop=None):
        self._sep_callable = sep_callable
        self._loop = loop

    async def __aenter__(self):
        self._start = time.time()

    def __enter__(self):
        self._start = time.time()

    def _sleep_time(self):
        return self._sep_callable() - (time.time() - self._start)
        
    async def __aexit__(self, *args):
        if self._loop is None:
            self._loop = asyncio.get_event_loop()
        sleep_time = self._sleep_time()
        if sleep_time > 0:
            await asyncio.sleep(sleep_time, loop=self._loop)
        
    def __exit__(self, *args):
        sleep_time = self._sleep_time()
        if self._sleep_time() > 0:
            time.sleep(sleep_time)


def ensure_fixed_seperation(seperation, loop=None):
    def fixed_seperation():
        return seperation
    return ensure_seperation_from_callable(fixed_seperation, loop=loop)


def ensure_average_seperation(mean_seperation, plus_minus=None, loop=None):
    if plus_minus is None:
        plus_minus = mean_seperation * .25

    def average_seperation():
        return mean_seperation + (random.random() * plus_minus * 2) - plus_minus

    return ensure_seperation_from_callable(average_seperation, loop=loop)


def require_extension(*extensions):
    def extended_journey(journey_func):
        setattr(journey_func, "_mite_extensions", extensions)
        return journey_func
    return extended_journey

