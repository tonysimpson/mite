from collections import defaultdict, deque
from itertools import count
import time
import logging

logger = logging.getLogger(__name__)


class WorkTracker:
    def __init__(self):
        self._all_work = defaultdict(lambda :defaultdict(int))
        self._total_work = defaultdict(int)

    def set_actual(self, runner_id, work):
        for k, v in self._all_work[runner_id].items():
            self._total_work[k] -= v
        for k, v in work.items():
            self._total_work[k] += v
        self._all_work[runner_id] = defaultdict(int, work)

    def add_assumed(self, runner_id, work):
        current = self._all_work[runner_id]
        for k, v in work.items():
            current[k] += v
            self._total_work[k] += v
    
    def get_total_work(self, runner_ids):
        for expired_runner_id in set(self._all_work.keys()) - set(runner_ids):
            self.remove_runner(expired_runner_id)
        return self._total_work

    def get_runner_total(self, runner_id):
        return sum(self._all_work[runner_id].values())

    def remove_runner(self, runner_id):
        for k, v in self._all_work[runner_id].items():
            self._total_work[k] -= v
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
    

class OnlineMean:
    def __init__(self):
        self.mean = 0
        self.n = 0

    def update(self, value):
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n


class LifespaneEstimationSpawnRateLimiter:
    def __init__(self, initial_lifespan_estimate=10):
        self._lifespan_mean = OnlineMean()
        self._lifespan_mean.update(initial_lifespan_estimate)
        self._birth_times = deque()

    def update_births(self, num):
        t = time.time()
        for i in range(num):
            self._birth_times.append(t)

    def update_deaths(self, num):
        t = time.time()
        for i in range(num):
            st = self._birth_times.popleft()
            self._lifespan_mean.update(t - st)



class RateLimiter:
    def __init__(self, initial_birth_rate_limit=100, time_window=10, growth_rate=2):
        self._birth_rate_limit = initial_birth_rate_limit
        self._time_window = time_window
        self._growth_rate = growth_rate
        self._deaths = deque()

    def update(self, number_of_deaths):
        if number_of_deaths > 0:
            t = time.time()
            self._deaths.append((t, number_of_deaths))
            while self._deaths:
                if t > self._deaths[0][0] + self._time_window:
                    self._deaths.popleft()
            new_limit = (sum(i[1] for i in self._deaths) / self._time_window) * self._growth_rate 
            self._birth_rate_limit = new_limit if new_limit > self._birth_rate_limit

    def get_limit(self, hit_rate):
        return self._birth_rate_limit / hit_rate if hit_rate > 0 else 0


class Controller:
    def __init__(self, testname, scenario_manager, config_manager):
        self._testname = testname
        self._scenario_manager = scenario_manager
        self._runner_id_gen = count(1)
        self._work_id_gen = count(1)
        self._work_tracker = WorkTracker()
        self._runner_tracker = RunnerTracker()
        self._rate_limiter = RateLimiter()
        self._config_manager = config_manager

    def hello(self):
        runner_id = next(self._runner_id_gen)
        return runner_id, self._testname, self._config_manager.get_changes_for_runner(runner_id)

    
    def _required_work_for_runner(self, runner_id, max_work=None):
        runner_total = self._work_tracker.get_runner_total(runner_id)
        active_runner_ids = self._runner_tracker.get_active()
        current_work = self._work_tracker.get_total_work(active_runner_ids)
        hit_rate = self._runner_tracker.get_hit_rate()
        work, scenario_volume_map = self._scenario_manager.get_work(current_work, runner_total, len(active_runner_ids), max_work, hit_rate)
        self._add_assumed(runner_id, scenario_volume_map) 
        return work

    def request_work(self, runner_id, completed_work_ids, max_work=None):
        self._update_with_completed_work_ids(runner_id, completed_work_ids)
        limit = self._calculate_limits(max_work)
        current_work = self._work_tracker.get_total_work(self._runner_tracker.get_active())
        work = self._scenario_manager.get_work(current_work, limit)
        self._config_manager.get_changes_for_runner(runner_id)
        runner_should_continue = not self._scenario_manager.is_active()
        config_delta = self._config_manager.get_changes_for_runner(runner_id)
        return work, config_delta, runner_should_continue

    def bye(self, runner_id):
        self._runner_tracker.remove_runner(runner_id)
        self._work_tracker.remove_runner(runner_id)

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


    def _update_with_completed_work_ids(self, runner_id, completed_work_ids):
        self._runner_tracker.remove_work(runner_id, completed_work_ids)
        for work_id in completed_work_ids:
            scenario_id, data_id = self._work_id_to_scenario_and_data_id.pop(work_id)
            self._work_tracker.end_work(runner_id, scenario_id)
            self._scenario_manager.checkin_data(scenario_id, data_id)
