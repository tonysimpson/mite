from itertools import count


class ConfigManager:
    def __init__(self):
        self._version_id_gen = count(1)
        self._version = 0
        self._config = {}
        self._runner_version_map = {}

    def _get_changes_since(self, version):
        for key, (value, value_version) in self._config.items():
            if value_version > version:
                yield key, value

    def get_changes_for_runner(self, runner_id):
        if runner_id not in self._runner_version_map:
            version = 0
        else:
            version = self._runner_version_map[runner_id]
        self._runner_version_map[runner_id] = self._version
        return list(self._get_changes_since(version))

    def set(self, name, value):
        self._version = next(self._version_id_gen)
        self._config[name] = (value, self._version)

    def __repr__(self):
        return "ConfigManager(version={}, {})".format(
            self._version, " ,".join(["{}={}".format(k, v) for k, v in self._config.items()]))

    def __str__(self):
        self.__repr__()


