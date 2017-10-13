import asyncio
from .context import Context, add_context_extensions
from .util import spec_import
from itertools import count
from collections import deque
import time


class TimeoutException(Exception):
    pass


class StopException(Exception):
    pass


class RunnerControllerTransportExample:
    async def initialise(self):
        """Returns runner id and the testname"""
        pass

    async def request_work(self, runner_id, current_work):
        """Takes a dict of id -> number pairs and returns and iterable of 
        (id, journey_spec, argument_datapool_id, number, minimum_duration)
        """
        pass
    
    async def checkin_and_checkout(self, runner_id, datapool_id, used_list):
        """Takes a datapool_id and a list of DataPoolItems and returns:
        A list of new DataPoolItems or and empty list or None if 
        the datapool is exhausted"""
        pass


class DataPoolProxy:
    def __init__(self, transport, runner_id, datapool_id, timeout=10):
        self._transport = transport
        self._runner_id = runner_id
        self._datapool_id = datapool_id
        self._timeout = timeout
        self._unused = deque()
        self._used = []
        self._getting_more = False
        self._waiting_queue = deque()
        self._stop = False

    async def checkout(self):
        if self._stop:
            raise StopException()
        if self._unused:
            return self._unused.popleft()
        future = self._create_waiting_future()
        if not self._getting_more:
            self._getting_more = True
            asyncio.ensure_future(self._get_more())
        return future

    async def checkin(self, dpi):
        self._used.append(dpi)

    def _create_waiting_future(self):
        future = asyncio.Future()
        self._waiting_queue.append((time.time() + self._timeout, future))

    def _do_waiting_timeout(self):
        if not self._waiting_queue:
            return
        t = time.time()
        active_waiting = deque()
        for timeout, future in self._waiting_queue:
            if timeout < t:
                future.set_exception(TimeoutException())
            else:
                active_waiting.append((timeout, future))
        self._waiting_queue = active_waiting

    def _do_waiting_stop_all(self):
        for _, future in self._waiting_queue:
            future.set_exception(StopException())
        self._waiting_queue = deque()

    def _do_waiting_have_unused(self):
        while self._waiting_queue and self._unused:
            _, future = self._waiting_queue.popleft()
            dpi = self._unused.popleft()
            future.set_result(dpi)

    async def _get_more(self):
        while self._waiting_queue:
            used = self._used
            self._used = []
            unused = _self._transport.checkin_and_checkout(self._runner_id, self._datapool_id, used)
            if unused is None:
                self._stop = True
                self._do_waiting_stop_all()
                return
            self._unused = deque(unused)
            self._do_waiting_have_unused()
            self._do_waiting_timeout()
            if self._waiting_queue:
                await asyncio.sleep(1)


class Runner:
    def __init__(self, transport, msg_sender):
        self._transport = transport
        self._msg_sender = msg_sender
        self._context_id_gen = count(1)
        self._work = {}
        self._datapool_proxies = {}

    def _current_work(self):
        return self._work

    async def run(self):
        self._id, self._test_name = await self._transport.initialise()
        self._base_id_data = {'test': self._test_name, 'runner_id': self._id}
        while True:
            work = await self._transport.request_work(self._id, self._current_work())
            for id, journey_spec, argument_datapool_id, number, minimum_duration in work:
                for i in range(number)
                    asyncio.ensure_future(self._execute(id, journey_spec, argument_id, minimum_duration))
            await asyncio.sleep(1)
    
    def _inc_work(self, id):
        self._work[id] += 1

    def _dec_work(self, id):
        self._work[id] -= 1
        if self._work[id] == 0:
            del self._work[id]

    async def _execute(self, id, journey_spec, argument_datapool_id, minimum_duration):
        start_time = time.time()
        journey = spec_import(journey_spec)
        id_data = {'journey': journey_spec}
        id_data.update(self._id_data)
        self._inc_work(id)
        while True:
            id_data['context_id'] = next(self._context_id_gen)
            id_data.update(self._id_data)
            context = Context(self._msg_sender, id_data=id_data)
            add_context_extensions(context, None) #TODO register and retrieve extensions on journeysi
            try:
                dpi = await self._checkout_data(argument_datapool_id)
            except (TimeoutException, StopException):
                break
            try:
                await journey(context, *dpi.data)
            except MiteError as me:
                context.send_msg('error', {'message': str(e)})
            except Exception as e:
                context.log_error()
            await self._checkin_data(argument_datapool_id, dpi)
            if time.time() > start_time + minimum_duration:
                break

    async def _checkout_data(self, datapool_id):
        if datapool_id not in self._datapool_proxies:
            self._datapool_proxies[datapool_id] = DataPoolProxy(self._transport, self._id, datapool_id)
        return await self._datapool_proxies[datapool_id].checkout()

    async def _checkin_data(self, datapool_id, dpi)
        await self._datapool_proxies[datapool_id].checkin(dpi)

