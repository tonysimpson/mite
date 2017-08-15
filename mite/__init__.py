import time
import asyncio
import random
import string

from urllib.parse import urlencode

from .exceptions import UnexpectedResponseCodeError


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


async def ensure_fixed_seperation(seperation, loop=None):
    def fixed_seperation():
        return seperation
    return ensure_seperation_from_callable(fixed_seperation, loop=loop)


async def ensure_average_seperation(mean_seperation, plus_minus=None, loop=None):
    if plus_minus is None:
        plus_minus = mean_seperation * .25

    def average_seperation():
        return mean_seperation + (random.random() * plus_minus * 2) - plus_minus

    return ensure_seperation_from_callable(average_seperation, loop=loop)


def check_status_code(resp, expected):
    if resp.status_code != expected:
        raise UnexpectedResponseCodeError(expected, resp)


def random_name(length=10):
    return ''.join([random.choice(string.ascii_lowercase) for _ in range(length)]).capitalize()


def random_phone_number(country_code='+44'):
    return ''.join([country_code, ''.join([random.choice(string.digits) for _ in range(10)])])


def url_builder(base_url, *args, **kwargs):
    new_args = []
    if args:
        url = base_url[:-1] if base_url.endswith('/') else base_url
        for arg in args:
            if arg.endswith('/') and arg != args[-1]:
                arg = arg[:-1]
            if not arg.startswith('/'):
                arg = ''.join(['/', arg])
            new_args.append(arg)
        url = ''.join([url, ''.join(new_args)])
    else:
        url = base_url
    if kwargs:
        url = ''.join([url, '?', urlencode(kwargs)])
    return url

