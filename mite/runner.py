import asyncio
from itertools import count
from collections import deque
import time
import logging

from .context import Context
from .utils import spec_import
from . import MiteError


logger = logging.getLogger(__name__)


class RunnerControllerTransportExample:
    async def hello(self):
        """Returns:
            runner_id
            test_name
            config_list - k, v pairs
            """
        pass

    async def request_work(self, runner_id, current_work, completed_data_ids, max_work):
        """\
        Takes:
            runner_id
            current_work - dict of scenario_id, currnet volume
            completed_data_ids - list of scenario_id, scenario_data_id pairs
            max_work - may be None to indicate no limit
        Returns:
            work - list of (scenario_id, scenario_data_id, journey_spec, args) - args and scenario_data_id may be None together
            config_list - k, v pairs
            stop
        """
        pass
    
    async def bye(self, runner_id):
        """\
        Takes:
            runner_id
        """
        pass


class RunnerConfig:
    def __init__(self):
        self._config = {}

    def __repr__(self):
        return "RunnerConfig({})".format(", ".join(["{}={}".format(k, v) for k, v in self._config.items()]))

    def _update(self, kv_list):
        for k, v in kv_list:
            self._config[k] = v

    def get(self, key, default=None):
        try:
            return self._config[key]
        except KeyError:
            if default is not None:
                return default
            else:
                raise
 
    def get_fallback(self, *keys, default=None):
        for key in keys:
            try:
                return self._config[key]
            except KeyError:
                pass
        if default is not None:
            return default
        raise KeyError("None of {} found".format(keys))


class Runner:
    def __init__(self, transport, msg_sender, loop_wait=1, max_work=None):
        self._transport = transport
        self._msg_sender = msg_sender
        self._work = {}
        self._datapool_proxies = {}
        self._stop = False
        self._loop_wait = loop_wait
        self._max_work = max_work

    def _inc_work(self, id):
        if id in self._work:
            self._work[id] += 1
        else:
             self._work[id] = 1

    def _dec_work(self, id):
        self._work[id] -= 1
        if self._work[id] == 0:
            del self._work[id]

    def _current_work(self):
        logger.debug("Runner current_work=%r", self._work)
        return self._work

    def should_stop(self):
        return self._stop

    async def run(self):
        context_id_gen = count(1)
        config = RunnerConfig()
        runner_id, test_name, config_list = await self._transport.hello()
        config._update(config_list)
        running = []
        logger.debug("Entering run loop")
        completed_data_ids = []
        while not self._stop:
            work, config_list, self._stop = await self._transport.request_work(runner_id, self._current_work(), completed_data_ids, self._max_work)
            config._update(config_list)
            logger.debug("requested_work=%r", work)
            work_len = len(work)
            for num, (scenario_id, scenario_data_id, journey_spec, args) in enumerate(work):
                id_data = {
                    'test': test_name,
                    'runner_id': runner_id,
                    'journey': journey_spec,
                    'context_id': next(context_id_gen),
                    'scenario_id': scenario_id,
                    'scenario_data_id': scenario_data_id
                }
                context = Context(self._msg_sender, config, id_data=id_data, should_stop_func=self.should_stop)
                delay = self._loop_wait * (num / work_len)
                future = asyncio.ensure_future(self._execute(context, scenario_id, scenario_data_id, journey_spec, args, delay=delay))
                running.append(future)
            if running:
                completed, _running = await asyncio.wait(running, timeout=self._loop_wait)
                running = list(_running)
                completed_data_ids = [(scenario_id, scenario_data_id) for scenario_id, scenario_data_id in [i.result() for i in completed] if scenario_data_id is not None]
            else:
                await asyncio.sleep(self._loop_wait)
                completed_data_ids = []
        while running:
            _, config_list, _ = await self._transport.request_work(runner_id, self._current_work(), completed_data_ids, 0)
            config._update(config_list)
            completed, running = await asyncio.wait(running, timeout=self._loop_wait)
            completed_data_ids = [(scenario_id, scenario_data_id) for scenario_id, scenario_data_id in [i.result() for i in completed] if scenario_data_id is not None]
        await self._transport.request_work(runner_id, self._current_work(), completed_data_ids, 0)
        self._transport.bye(runner_id)

    async def _execute(self, context, scenario_id, scenario_data_id, journey_spec, args, delay=0):
        logger.debug('Runner._execute starting scenario_id=%r scenario_data_id=%r journey_spec=%r args=%r delay=%r', scenario_id, scenario_data_id, journey_spec, args, delay)
        await asyncio.sleep(delay)
        self._inc_work(scenario_id)
        try:
            journey = spec_import(journey_spec)
            if args is None:
                await journey(context)
            else:
                await journey(context, *args)
        except MiteError as me:
            context.send('error', message=str(me), **me.fields)
        except Exception as e:
            context.log_error()
            await asyncio.sleep(1)
        self._dec_work(scenario_id)
        return scenario_id, scenario_data_id

