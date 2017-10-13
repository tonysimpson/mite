from collections import defaultdict
from itertools import count
import time


class ControllerTransportExample:
    pass
    

class workTracker:
    def __init__(self):
        self._all_work = defaultdict(lambda :defaultdict(int))

    def set_actual(self, runner_id, work):
        self._all_work[runner_id] = defaultdict(int, work)

    def add_assumed(self, runner_id, work):
        current = self._all_work[runner_id]
        for k, v in work:
            current[k] += v
    
    def get_total_work(self):
        totals = defaultdict(int)
        for work in self._all_work.values():
            for k, v in work:
                totals[k] += v


class Controller:
    def __init__(self, testname, scenario_manager, period=10):
        self._testname = testname
        self._scenario_manager = scenario_manager
        self._period = period
        self._runner_id_gen = count(1)
        self._work_tracker = WorkTracker()
        self._current_period_expire = 0
        self._required = {} 
        self._start_time = time.time()
    
    def initialise(self):
        return next(self._runner_id_gen), self._testname

    def _set_actual(self, runner_id, current_work):
        self._work_tracker.set_actual(runner_id, current_work)

    def _now(self):
        return time.time() - self._start_time

    def _update_required_if_expired(self):
        now = self._now()
        if now > self._current_period_expire:
            new_period_expire = now + self._period
            self._required = self._scenario_manager.required(self._current_period_expire, new_period_expire)
            self._current_period_expire = new_period_expire

    def _calculate_required_work(self):

        
    
    def work_request(self, runner_id, current_work):
        self._set_actual(runner_id, current_work)
        return self._calculate_required_work()




