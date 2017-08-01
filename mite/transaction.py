from traceback import format_exception

from mite.journey import send
from mite.exceptions import TestEnd


class _Transaction:
    def __init__(self, func=None, error_func=None, *error_args, **error_kwargs):
        self.func = func
        self.error_func = error_func
        self.error_args = error_args
        self.error_kwargs = error_kwargs

    def enter(self):
        send("START: {}".format(self.func.__name__))

    def exit(self, exc_type, exc_val, exc_tb):
        if exc_type is not None and exc_type != TestEnd:
            send("ERROR")
            send("".join(format_exception(exc_type, exc_val, exc_tb)))
        if self.error_func is not None:
            self.error_func(*self.error_args, **self.error_kwargs)
        send("STOP: {}".format(self.func.__name__))


class _SyncTransaction(_Transaction):

    def __init__(self, func=None, error_func=None, *error_args, **error_kwargs):
        super().__init__(func, error_func, *error_args, **error_kwargs)

    def __enter__(self):
        self.enter()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.exit(exc_type, exc_val, exc_tb)


class _AsyncTransaction(_Transaction):

    def __init__(self, func=None, error_func=None, *error_args, **error_kwargs):
        super().__init__(func, error_func, *error_args, **error_kwargs)

    async def __aenter__(self):
        self.enter()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.exit(exc_type, exc_val, exc_tb)


def wrap_transaction(func=None, error_func=None):

    def inner(*args, **kwargs):
        with _SyncTransaction(func, error_func):
            return func(*args, **kwargs)

    return inner


def wrap_async_transaction(func=None, error_func=None):

    async def inner(*args, **kwargs):
        async with _AsyncTransaction(func, error_func):
            return await func(*args, **kwargs)

    return inner
