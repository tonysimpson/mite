import asyncio
import threading
from importlib import import_module
from random import choice
from string import ascii_letters, digits
from minimalmite.protocols import NanomsgProtocol


class Executor:
    def __init__(self, identifier=None, controller_location="localhost", controller_port=9000, protocol=NanomsgProtocol,
                 collector_location=None, collector_port=9001, max_volume=1):
        self.identifier = identifier or ''.join([choice(ascii_letters+digits) for _ in range(8)])
        self.async_jobs = 0
        self.sync_jobs = 0
        self.vc_channel = protocol()
        self.vc_channel.open_channel_to_vc(vc_location=controller_location, port=controller_port)
        self.collector_channel = protocol()
        self.collector_channel.open_channel_to_collector(collector_location=collector_location, port=collector_port)
        self.killed_actions = 0
        self.max_volume = max_volume
        self.event_loop = asyncio.get_event_loop()
        self.event_loop.run_until_complete(asyncio.wait(self.main_loop()))

    @staticmethod
    def import_journey(job):
        return import_module("{}.journeys".format(job['package']), job['journey'])

    def get_free_capacity(self):
        return self.max_volume-(self.sync_jobs+self.async_jobs)

    def update_volumes(self):
        volumes = "{} {} {} {} {}".format(
            self.identifier,
            self.async_jobs,
            self.sync_jobs,
            self.killed_actions,
            self.get_free_capacity())
        self.vc_channel.send(volumes)

    def job_splitter(self, jobs):
        a_jobs = []
        s_jobs = []
        for job in jobs:
            if job['identifier'] != self.identifier:
                continue
            journey = self.import_journey(job)
            if asyncio.iscoroutinefunction(journey):
                a_jobs.append(self.add_async_job(journey, *job['args'], **job['kwargs']))
            else:
                s_jobs.append(self.add_sync_job(journey, *job['args'], **job['kwargs']))
        return a_jobs, s_jobs

    def receive_jobs(self):
        return self.vc_channel.receive()

    def add_async_job(self, job, *args, **kwargs):
        self.async_jobs += 1
        task = self.event_loop.create_task(job(*args, **kwargs))
        task.add_done_callback(self._decrement_async_callback)
        return task

    def add_sync_job(self, job, *args, **kwargs):
        def job_with_callback():
            job(*args, **kwargs)
            self._decrement_sync_callback()

        self.sync_jobs += 1
        job_thread = threading.Thread(target=job_with_callback)
        return job_thread

    def _decrement_async_callback(self):
        self.async_jobs -= 1

    def _decrement_sync_callback(self):
        self.sync_jobs -= 1

    async def main_loop(self):
        while True:
            self.update_volumes()
            jobs = self.receive_jobs()
            a_jobs, s_jobs = self.job_splitter(jobs)
            for s in s_jobs:
                s.start()
            self.event_loop.run_until_complete(a_jobs)
