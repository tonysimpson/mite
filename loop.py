import minimalmite
import time
import asyncio
import logging
import sys
import msgpack

controller = minimalmite.SessionController()
logging.basicConfig()#level=logging.DEBUG)


S = int(sys.argv[1])
N = int(sys.argv[2])

results_file = open("results_%d_%d.msgpack" % (S, N), "wb")
packer = msgpack.Packer()

async def test():
    session = controller.create_new_session(metrics_callback=lambda d: results_file.write(packer.pack(d)))
    for i in range(N):
        try:
            await session.request('GET', 'http://127.0.0.1:9003')
        except Exception as e:
            print(e)
    print(N / (time.time() - st))

loop = asyncio.get_event_loop()
st = time.time()
loop.run_until_complete(asyncio.wait([test() for i in range(S)]))
print("TOTAL:", (S*N) / (time.time() - st))

