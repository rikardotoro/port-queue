from port_queue import __version__
from port_queue.errors import PortQueueError, SaturatedPortError


def test_version_is_exposed():
    assert __version__ == "0.1.0"


def test_saturated_port_error_is_a_port_queue_error():
    assert issubclass(SaturatedPortError, PortQueueError)
