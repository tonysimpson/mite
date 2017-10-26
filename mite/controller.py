from collections import defaultdict
from itertools import count
import time
import logging

logger = logging.getLogger(__name__)


class WorkTracker:
    def __init__(self):
        self._all_work = defaultdict(lambda :defaultdict(int))

    def set_actual(self, runner_id, work):
        self._all_work[runner_id] = defaultdict(int, work)
        logger.debug("WorkTracker.set_actual runner_id=%r actual=%r" % (runner_id, work))

    def add_assumed(self, runner_id, work):
        current = self._all_work[runner_id]
        for k, v in work.items():
            current[k] += v
    
    def get_total_work(self):
        totals = defaultdict(int)
        for work in self._all_work.values():
            for k, v in work.items():
                totals[k] += v
        return totals

    def get_runner_total(self, runner_id):
        return sum(self._all_work[runner_id].values())

    def remove_runner(self, runner_id):
        del self._all_work[runner_id]


class RunnerTracker:
    def __init__(self, timeout=10):
        self._last_seen = {}
        self._timeout = timeout

    def update(self, runner_id):
        self._last_seen[runner_id] = time.time()

    def remove_runner(self, runner_id):
        del self._last_seen[runner_id]

    def get_active_count(self):
        t = time.time()
        return sum(1 for k, v in self._last_seen.items() if v + self._timeout > t)


class Controller:
    def __init__(self, testname, scenario_manager, config_manager):
        self._testname = testname
        self._scenario_manager = scenario_manager
        self._runner_id_gen = count(1)
        self._work_tracker = WorkTracker()
        self._runner_tracker = RunnerTracker()
        self._config_manager = config_manager
        self._start_time = time.time()
    
    def hello(self):
        runner_id = next(self._runner_id_gen)
        return runner_id, self._testname, self._config_manager.get_changes_for_runner(runner_id)

    def _set_actual(self, runner_id, current_work):
        self._work_tracker.set_actual(runner_id, current_work)

    def _add_assumed(self, runner_id, work):
        self._work_tracker.add_assumed(runner_id, work)
    
    def _required_work_for_runner(self, runner_id, max_work=None):
        runner_total = self._work_tracker.get_runner_total(runner_id)
        active_runners = self._runner_tracker.get_active_count()
        current_work = self._work_tracker.get_total_work()
        work, scenario_volume_map = self._scenario_manager.get_work(current_work, runner_total, active_runners, max_work)
        self._add_assumed(runner_id, scenario_volume_map) 
        return work

    def work_request(self, runner_id, current_work, completed_data_ids, max_work=None):
        self._set_actual(runner_id, current_work)
        self._runner_tracker.update(runner_id)
        self._scenario_manager.checkin_data(completed_data_ids)
        work = self._required_work_for_runner(runner_id, max_work)
        logger.debug('Controller.work_request returning runner_id=%s work=%r', runner_id, work)
        return work, self._config_manager.get_changes_for_runner(runner_id), False

    def bye(self, runner_id):
        self._runner_tracker.remove_runner(runner_id)
        self._work_tracker.remove_runner(runner_id)


