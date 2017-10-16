import asyncio

from .datapools import RecyclableIterableDataPool


async def journey(context, arg1, arg2):
    with context.transaction('test1'):
        context.send_msg('hello', {'args': (arg1, arg2)})
        await asyncio.sleep(0.5)


datapool = RecyclableIterableDataPool([(i, i+2) for i in range(5000)])


volumemodel = lambda start, end: 50


scenario = [
    ['mite.example:journey', 'mite.example:datapool', 'mite.example:volumemodel'],
]

