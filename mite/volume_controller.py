from collections import Counter
from importlib import import_module

from mite.protocols import NanomsgProtocol
from mite.allocators import FewestJobsAllocator


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
        identifier, jobs, killed_actions, capacity = self.executor_channel.receive().split()
        self.executors[identifier] = [Counter(jobs), killed_actions, capacity]

    def current_volumes_by_action(self):
        return sum([e[0] for e in self.executors.values()])

    def add_vms(self, package, scenario):
        getattr(import_module(scenario, '{}.scenarios'.format(package)))(self)

    def add_vm(self, vm):
        self.vms.append(vm)

    def remove_vm(self, vm):
        self.vms.remove(vm)

    def send_job(self, journey, package, *args, **kwargs):
        msg = {"identifier": self.allocator.allocate(),
               "journey": journey,
               "package": package,
               "args": args,
               "kwargs": kwargs}
        # To prevent over-allocation, will be corrected upon next receive from executor
        # Crappy and I hate it, think of better solution
        self.executors[msg["identifier"]][2] -= 1
        self.executor_channel.send(msg)

    def calculate_required_volumes(self):
        c = self.current_volumes_by_action()
        for vm in self.vms:
            yield vm, vm.current_required() - c[vm.identifier]

    def main_loop(self):
        while self.vms:
            self.update_volumes()
            for vm, required in self.calculate_required_volumes():
                self.send_job(*next(vm))
