import mite
import time
import asyncio
import logging
import sys
import msgpack
from pympler.tracker import SummaryTracker

logging.basicConfig()#level=logging.DEBUG)


S = int(sys.argv[1])
N = int(sys.argv[2])

#results_file = open("results_%d_%d.msgpack" % (S, N), "wb")
packer = msgpack.Packer()

async def test():
    session = mite.Session()
    try:
        await asyncio.gather(*[session.request('GET', 'http://127.0.0.1:9003') for i in range(N)])
    except Exception as e:
        print('error:', repr(e))
    print(N / (time.time() - st))
    await session.wait_for_done()

loop = asyncio.get_event_loop()
st = time.time()
loop.run_until_complete(asyncio.wait([test() for i in range(S)]))
print("TOTAL:", (S*N) / (time.time() - st))

