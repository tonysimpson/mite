from importlib import import_module

from minimalmite.protocols import NanomsgProtocol
from minimalmite.allocators import FewestJobsAllocator


class VolumeController:
    def __init__(self, package, scenario, protocol=NanomsgProtocol, executor_port=9000, deadline=10000,
                 allocator=FewestJobsAllocator):
        self.executors = {}
        self.banned_executors = []
        self.executor_channel = protocol()
        self.deadline = deadline
        self.executor_channel.open_channel_to_executors(port=executor_port, deadline=deadline)
        self.allocator = allocator(self)
        self.vms = []
        self.add_vms(package, scenario)
        self.main_loop()

    def update_volumes(self):
        identifier, async_jobs, sync_jobs, killed_actions, capacity = self.executor_channel.receive().split()
        self.executors[identifier] = [async_jobs, sync_jobs, killed_actions, capacity]

    def add_vms(self, package, scenario):
        getattr(import_module('{}.scenarios'.format(package)), scenario)(self)

    def add_vm(self, vm):
        self.vms.append(vm)

    def send_job(self, journey, package, *args, **kwargs):
        msg = {"identifier": self.allocator.allocate(),
               "journey": journey,
               "package": package,
               "args": args,
               "kwargs": kwargs}
        self.executor_channel.send(msg)

    def calculate_required_volume(self):
        return sum([vm.current_required() for vm in self.vms])

    def main_loop(self):
        pass
