import asyncio

from .datapools import RecyclableIterableDataPool


async def journey(ctx, arg1, arg2):
    with ctx.transaction('test1'):
        ctx.send('test_message', content=ctx.config.get('test_msg', 'Not set'))
        await asyncio.sleep(0.5)


datapool = RecyclableIterableDataPool([(i, i+2) for i in range(5000)])


volumemodel = lambda start, end: 10


def scenario():
    return [
        ['mite.example:journey', datapool, volumemodel],
    ]

