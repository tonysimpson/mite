import asyncio
import threading
from importlib import import_module
from random import choice
from string import ascii_letters, digits
from mite.protocols import NanomsgProtocol

lock = threading.Lock()


class Executor:
    def __init__(self, package, identifier=None, controller_location="localhost", controller_port=9000,
                 protocol=NanomsgProtocol, collector_location=None, collector_port=9001, max_volume=1):
        self.identifier = identifier or ''.join([choice(ascii_letters+digits) for _ in range(8)])
        self.jobs = {}
        self.journeys = {}
        self.vc_channel = protocol()
        self.vc_channel.open_channel_to_vc(vc_location=controller_location, port=controller_port)
        self.collector_channel = protocol()
        self.collector_channel.open_channel_to_collector(collector_location=collector_location, port=collector_port)
        self.killed_actions = 0
        self.max_volume = max_volume
        self.event_loop = asyncio.get_event_loop()
        self.import_journeys(package)
        self.event_loop.run_until_complete(asyncio.wait(self.main_loop()))

    @staticmethod
    def import_journeys(package):
        module = import_module(package)
        for item in module.__all__:
            if 'journey' in item.lower():
                import_module(item, package)

    def get_free_capacity(self):
        return self.max_volume-(sum(self.jobs.values()))

    def update_volumes(self):
        self.vc_channel.send({
            "identifier": self.identifier,
            "jobs": self.jobs,
            "killed_actions": self.killed_actions,
            "free capacity": self.get_free_capacity()})

    def job_splitter(self, job):
        if job['identifier'] != self.identifier:
            return None, None
        journey = globals()[job['journey']]
        if asyncio.iscoroutinefunction(journey):
            return self.add_async_job(journey, *job['args'], **job['kwargs'])
        else:
            return self.add_sync_job(journey, *job['args'], **job['kwargs'])

    def receive_job(self):
        return self.vc_channel.receive()

    def add_async_job(self, action_identifier, journey, *args, **kwargs):
        with lock:
            self.jobs[action_identifier] += 1
        task = self.event_loop.create_task(journey(*args, **kwargs))
        task.add_done_callback(self._decrement_job_callback)
        return task

    def add_sync_job(self, action_identifier, job, *args, **kwargs):
        def job_with_callback():
            job(*args, **kwargs)
            self._decrement_job_callback(action_identifier)

        with lock:
            self.jobs[action_identifier] += 1
        job_thread = threading.Thread(target=job_with_callback)
        return job_thread

    def _decrement_job_callback(self, action_identifier):
        with lock:
            self.jobs[action_identifier] -= 1

    async def main_loop(self):
        while True:
            self.update_volumes()
            jobs = self.receive_job()
            a_job, s_job = self.job_splitter(jobs)
            if s_job:
                s_job.start()
            if a_job:
                self.event_loop.run_until_complete(a_job)