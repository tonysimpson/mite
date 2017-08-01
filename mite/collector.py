from datetime import datetime
from mite.protocols import NanomsgProtocol


class Collector:
    def __init__(self, port=9001):
        self.collection_channel = NanomsgProtocol()
        self.collection_channel.open_channel_to_data_sources(port)
        self.write_to_file()

    def write_to_file(self):
        result_file = "results_%s.log".format(datetime.now().strftime("%y_%m_%d_%H_%M_%S"))
        with open(result_file, 'w') as f:
            while True:
                f.write(self.collection_channel.receive())
