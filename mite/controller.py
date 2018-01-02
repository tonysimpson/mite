from collections import defaultdict, deque
from itertools import count
import time
import logging

logger = logging.getLogger(__name__)


class WorkTracker:
    def __init__(self):
        self._all_work = defaultdict(lambda :defaultdict(int))
        self._cached = None

    def set_actual(self, runner_id, work):
        if work != self._all_work[runner_id]:
            self._cached = None
            self._all_work[runner_id] = defaultdict(int, work)

    def add_assumed(self, runner_id, work):
        if work:
            self._cached = None
            current = self._all_work[runner_id]
            for k, v in work.items():
                current[k] += v
    
    def get_total_work(self, runner_ids):
        if self._cached is not None:
            return self._cached
        totals = defaultdict(int)
        for runner_id in runner_ids:
            for k, v in self._all_work[runner_id].items():
                totals[k] += v
        self._cached = totals
        return totals

    def get_runner_total(self, runner_id):
        return sum(self._all_work[runner_id].values())

    def remove_runner(self, runner_id):
        del self._all_work[runner_id]


class RunnerTracker:
    def __init__(self, timeout=10):
        self._hits = deque()
        self._last_seen = {}
        self._timeout = timeout

    def update(self, runner_id):
        t = time.time()
        self._last_seen[runner_id] = t
        self._hits.append(t)
        if self._hits[0] < t - self._timeout:
            self._hits.popleft()

    def get_hit_rate(self):
        t = time.time()
        while self._hits and self._hits[0] <  t - self._timeout:
            self._hits.popleft()
        return len(self._hits) / self._timeout

    def remove_runner(self, runner_id):
        del self._last_seen[runner_id]

    def get_active(self):
        t = time.time()
        return [k for k, v in self._last_seen.items() if v + self._timeout > t]

    def get_active_count(self):
        return len(self.get_active())


class Controller:
    def __init__(self, testname, scenario_manager, config_manager):
        self._testname = testname
        self._scenario_manager = scenario_manager
        self._runner_id_gen = count(1)
        self._work_tracker = WorkTracker()
        self._runner_tracker = RunnerTracker()
        self._config_manager = config_manager

    def hello(self):
        runner_id = next(self._runner_id_gen)
        return runner_id, self._testname, self._config_manager.get_changes_for_runner(runner_id)

    def _set_actual(self, runner_id, current_work):
        self._work_tracker.set_actual(runner_id, current_work)

    def _add_assumed(self, runner_id, work):
        self._work_tracker.add_assumed(runner_id, work)
    
    def _required_work_for_runner(self, runner_id, max_work=None):
        runner_total = self._work_tracker.get_runner_total(runner_id)
        active_runner_ids = self._runner_tracker.get_active()
        current_work = self._work_tracker.get_total_work(active_runner_ids)
        hit_rate = self._runner_tracker.get_hit_rate()
        work, scenario_volume_map = self._scenario_manager.get_work(current_work, runner_total, len(active_runner_ids), max_work, hit_rate)
        self._add_assumed(runner_id, scenario_volume_map) 
        return work

    def request_work(self, runner_id, current_work, completed_data_ids, max_work=None):
        self._set_actual(runner_id, current_work)
        self._runner_tracker.update(runner_id)
        self._scenario_manager.checkin_data(completed_data_ids)
        work = self._required_work_for_runner(runner_id, max_work)
        return work, self._config_manager.get_changes_for_runner(runner_id), not self._scenario_manager.is_active()

    def report(self, sender):
        required = self._scenario_manager.get_required_work()
        active_runner_ids = self._runner_tracker.get_active()
        actual = self._work_tracker.get_total_work(active_runner_ids)
        sender({
            'type': 'controller_report', 
            'time': time.time(),
            'test': self._testname,
            'required': required, 
            'actual': actual, 
            'num_runners': len(active_runner_ids)
        })

    def should_stop(self):
        return (not self._scenario_manager.is_active()) and self._runner_tracker.get_active_count() == 0

    def bye(self, runner_id):
        self._runner_tracker.remove_runner(runner_id)
        self._work_tracker.remove_runner(runner_id)


