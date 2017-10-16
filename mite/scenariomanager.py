from collections import namedtuple
from itertools import count
import time
import logging

from .utils import spec_import

logger = logging.getLogger(__name__)


WorkItem = namedtuple('WorkItem', 'journey_spec argument_datapool_id number minimum_duration'.split())


Scenario = namedtuple('Scenario', 'id journey_spec argument_datapool_id volumemodel'.split())


class ScenarioManager:
    def __init__(self, datapool_manager, period=1):
        self._period = period
        self._scenario_id_gen = count(1)
        self._datapool_manager = datapool_manager
        self._start_time = time.time()
        self._current_period_end = 0
        self._required = {}
        self._scenarios = []

    def _now(self):
        return time.time() - self._start_time

    def add_scenario(self, journey_spec, argument_datapool_spec, volumemodel_spec):
        scenario_id = next(self._scenario_id_gen)
        volumemodel = spec_import(volumemodel_spec)
        argument_datapool_id = self._datapool_manager.register(argument_datapool_spec)
        self._scenarios.append(Scenario(scenario_id, journey_spec, argument_datapool_id, volumemodel))

    def _update_required_and_period(self, start_of_period, end_of_period):
        required = {}
        for scenario in self._scenarios:
            number = scenario.volumemodel(start_of_period, end_of_period)
            required[scenario.id] = WorkItem(scenario.journey_spec, scenario.argument_datapool_id, number, self._period)
        self._current_period_end = end_of_period
        self._required = required
        logger.debug('ScenarioManager._update_required_and_period period_end=%r required=%r', self._current_period_end, self._required)

    def get_required_work(self):
        now = self._now()
        if now >= self._current_period_end:
            self._update_required_and_period(self._current_period_end, int(now + self._period))
        return self._required

    def checkin_block(self, datapool_id, ids):
        self._datapool_manager.checkin_block(datapool_id, ids)

    def checkout_block(self, datapool_id):
        return self._datapool_manager.checkout_block(datapool_id)

