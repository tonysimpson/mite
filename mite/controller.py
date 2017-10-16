from collections import defaultdict, namedtuple
from itertools import count
import time


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
        return totals

    def get_runner_total(self, runner_id):
        return sum(self._all_work[runner_id].values())


class RunnerTracker:
    def __init__(self, timeout=10):
        self._last_seen = {}
        self._timeout = timeout

    def update(self, runner_id):
        self._last_seen[runner_id] = time.time()

    def get_active_count(self):
        t = time.time()
        return sum(1 for k, v in self._last_seen.items() if v + self._timeout > t)


WorkItem = namedtuple('WorkItem', 'journey_spec argument_datapool_id number minimum_duration'.split())


class Controller:
    def __init__(self, testname, scenario_manager):
        self._testname = testname
        self._scenario_manager = scenario_manager
        self._runner_id_gen = count(1)
        self._work_tracker = WorkTracker()
        self._runner_tracker = RunnerTracker()
        self._start_time = time.time()
    
    def initialise(self):
        return next(self._runner_id_gen), self._testname

    def _set_actual(self, runner_id, current_work):
        self._work_tracker.set_actual(runner_id, current_work)

    def _add_sssumed(self, runner_id, work):
        self._work_tracker.add_assumed(runner_id, work)

    def _now(self):
        return time.time() - self._start_time

    def _get_current_required_work(self):
        required = self._scenario_manager.get_required_work()
        current = self._work_tracker.get_total_work()
        diff = {}
        for id, current_num in current.items():
            if id in required:
                diff_num = required[id].number - current_num
                if diff_num > 0:
                    diff[id] = required[id]._replace(number=diff_num)
        return diff

    def _sum_workitem_dict(self, wi_dict):
        total = 0
        for wi in wi_dict.values():
            total += wi.number
        return total

    def _gen_required_work_for_runner(self, runner_id):
        required = self._get_current_required_work()
        required_total = self._sum_workitem_dict(required)
        runner_total = self._work_tracker.get_runner_total(runner_id)
        active_runners = self._runner_tracker.get_active_count()
        max_num = max(0, (required_total // active_runners) - runner_total)
        for id, wi in required:
            if max_num <= 0:
                break
            if max_num < wi.number:
                yield id, wi._replace(number=max_num)
                break
            else:
                max_num -= wi.number
                yield id, wi
    
    def work_request(self, runner_id, current_work):
        self._set_actual(runner_id, current_work)
        self._runner_tracker.update(runner_id)
        work = list(self._get_required_work_for_runner(runner_id))
        self._add_assumed(runner_id, {id: wi.number for id, wi in work.items()})
        return [(id, wi.journey_spec, wi.argument_datapool_id, wi.number, wi.minimum_duration) for id, wi in work]

    def checkin_and_checkout(self, runner_id, datapool_id, used_ids):
        self._scenario_manager.checkin_block(datapool_id, used_ids)
        return self._scenario_manager.checkout_block(datapool_id)

