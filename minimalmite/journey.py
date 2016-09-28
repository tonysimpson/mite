import threading

journey_context = threading.local()


def start_journey_context(protocol):
    journey_context._send = protocol.send


def send(message):
    journey_context._send(message)
