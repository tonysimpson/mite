import asyncio
import importlib
from .context import Context, add_context_extensions

def spec_import(spec):
    module, attr = spec.split(':', 1)
    return getattr(importlib.import_module(module), attr)


def init_journey(journey_spec):
    return spec_import(journey_spec)


def init_data_pools(journey):
    pass


def init_config(journey):
    pass


class LocalDataPoolAccess:
    def __init__(self, *args):
        pass


def get_extensions(journey):
    if hasattr(journey, '_mite_ctx_extensions'):
        return journey._mite_ctx_extensions
    return ['http']


def call_async(func, *args):
    return asyncio.get_event_loop().run_until_complete(func(*args))


def run_journey_spec_standalone(journey_spec):
    journey = init_journey(journey_spec)
    data_pools = init_data_pools(journey)
    config = init_config(journey)
    dpa = LocalDataPoolAccess(data_pools)
    ctx = Context(print)
    extensions = get_extensions(journey)
    add_context_extensions(ctx, extensions)
    call_async(journey, ctx, ctx.args)
