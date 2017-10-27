from collections import namedtuple
from itertools import count
import time
import logging
import random

from .datapools import DataPoolExhausted

logger = logging.getLogger(__name__)


Scenario = namedtuple('Scenario', 'journey_spec datapool volumemodel'.split())


class StopScenario(Exception):
    pass


def _volume_dicts_remove_a_from_b(a, b):
    diff = dict(b)
    for scenario_id, current_num in a.items():
        if scenario_id in diff:
            diff[scenario_id] -= current_num
            if diff[scenario_id] < 1:
                del diff[scenario_id]
    return diff


class ScenarioManager:
    def __init__(self, start_delay=0, period=1):
        self._period = period
        self._scenario_id_gen = count(1)
        self._in_start = start_delay > 0
        self._start_delay = start_delay
        self._start_time = time.time()
        self._current_period_end = 0
        self._required = {}
        self._scenarios = {}

    def _now(self):
        return time.time() - self._start_time

    def add_scenario(self, journey_spec, datapool, volumemodel):
        scenario_id = next(self._scenario_id_gen)
        self._scenarios[scenario_id] = Scenario(journey_spec, datapool, volumemodel)

    def _update_required_and_period(self, start_of_period, end_of_period):
        required = {}
        for scenario_id, scenario in list(self._scenarios.items()):
            try:
                number = int(scenario.volumemodel(start_of_period, end_of_period))
            except StopScenario:
                logger.info('ScenarioManager.get_work Removed scenario %d due because volume model raised StopScenario', scenario_ids)
                del self._scenarios[scenario_id]
            else:
                required[scenario_id] = number
        self._current_period_end = end_of_period
        self._required = required
        logger.debug('ScenarioManager._update_required_and_period period_end=%r required=%r', self._current_period_end, self._required)

    def get_required_work(self):
        if self._in_start:
            if self._now() > self._start_delay:
                self._in_start = False
                self._start_time = time.time()
            else:
                return self._required
        now = self._now()
        if now >= self._current_period_end:
            self._update_required_and_period(self._current_period_end, int(now + self._period))
        return self._required

    def get_work(self, current_work, num_runner_current_work , num_runners, max_num=None):
        required = self.get_required_work()
        diff = _volume_dicts_remove_a_from_b(current_work, required)
        total = sum(required.values())
        num = max(0, (total / num_runners) - num_runner_current_work)
        if max_num is not None:
            num = min(max_num, num)
        def _yield(diff):
            for k, v in diff.items():
                for i in range(v):
                    yield k
        logger.debug('ScenarioManager.get_work diff=%r num=%r', diff, num)
        scenario_ids = list(_yield(diff))
        random.shuffle(scenario_ids)
        work = []
        scenario_volume_map = {}
        logger.debug('ScenarioManager.get_work scenario_ids=%r', scenario_ids)
        for scenario_id in scenario_ids:
            if len(work) >= num:
                break
            if scenario_id in self._scenarios:
                scenario = self._scenarios[scenario_id]
                if scenario.datapool is None:
                    work.append((scenario_id, None, scenario.journey_spec, None))
                else:
                    try:
                        dpi = scenario.datapool.checkout()
                    except DataPoolExhausted:
                        logger.info('ScenarioManager.get_work Removed scenario %d because data pool exhausted', scenario_ids)
                        del self._scenarios[scenario_id]
                        continue
                    else:
                        if dpi is None:
                            continue
                        work.append((scenario_id, dpi.id, scenario.journey_spec, dpi.data))
                if scenario_id in scenario_volume_map:
                    scenario_volume_map[scenario_id] += 1
                else:
                    scenario_volume_map[scenario_id] = 1
        return work, scenario_volume_map

    def is_active(self):
        return self._in_start or bool(self._scenarios)

    def checkin_data(self, ids):
        for scenario_id, scenario_data_id in ids:
            if scenario_id in self._scenarios:
                self._scenarios[scenario_id].datapool.checkin(scenario_data_id)



