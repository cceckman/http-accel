import queue
import sys
from threading import Thread

from amaranth.sim import Simulator

from stream_fixtures import StreamSender, StreamCollector


class SimServer:
    """
    A holder for an Amaranth simulation of serial-connected component.

    This wraps the provided dut in a simulator,
    and provides access to the TX and RX lines via another thread.

    Use as a context manager:

    ```
    with SimServer(dut, dut.tx, dut.rx) as sim:
        sim.send([0, 1, 2, 3])
        v = sim.recv()
    ```
    """

    def __init__(self, dut, dut_tx, dut_rx):
        """
        Create a server.

        Arguments:
        dut:            An Amaranth component.
        dut_tx:         The device-under-test's TX line (outbound from device).
        dut_rx:         The device-under-test's RX line (inbound to device).
        """

        self._dut = dut
        self._dut_tx = dut_tx
        self._dut_rx = dut_rx
        self._data_in = None
        self._data_out = None
        self._sender = None
        self._sim_thread = None

    def send(self, b: bytes):
        """
        Transmit the provided bytes to the simulation.
        """
        assert self._sim_thread is not None, (
            "Simulation is not running; enter the context")
        self._data_in.put(b)

    def recv(self, count=None):
        """
        Receive bytes from the simulation.

        If count is set, receive at least `count` bytes (possibly more).
        Buffering is your problem!
        """
        assert self._sim_thread is not None, (
            "Simulation is not running; enter the context")
        buffer = bytes()
        while True:
            try:
                buffer += self._data_out.get(timeout=0.1)
            except queue.Empty:
                pass
            if not self._sim_thread.is_alive():
                # TODO: Raise exception?
                return buffer
            if count is None or len(buffer) >= count:
                return buffer

    def __enter__(self):
        """
        Start the simulation in a background thread.
        """

        assert self._sim_thread is None
        sim = Simulator(self._dut)
        sim.add_clock(1e-6)

        self._data_in = queue.Queue()
        self._data_out = queue.Queue()

        tx = self._sender = StreamSender(self._dut_rx)
        rx = StreamCollector(self._dut_tx)

        sim.add_process(rx.collect_queue(self._data_out))
        sim.add_testbench(tx.send_queue_active(self._data_in))

        # Start a new thread for simulation.
        # The Amaranth simulator provides its own async context,
        # but the .run() method is not itself async, so we have to use threads.
        self._sim_thread = Thread(target=self._run_sim(sim))
        self._sim_thread.start()
        return self

    def _run_sim(self, sim):
        def runnable():
            try:
                sys.stderr.write("running simulator\n")
                # Uncomment this line, and indent the next, to get debug info.
                # with sim.write_vcd("testout.vcd"):
                sim.run()
                sys.stderr.write("simulation complete\n")
            except Exception as e:
                sys.stderr.write(f"error in Amaranth simulation: {e}\n")
                # Try to force shutdown:
                self._sender.done = True
                raise e

        return runnable

    def __exit__(self, *args, **kwargs):
        assert self._sim_thread is not None
        # Shutting down the data input should shut down the simulator;
        # the data input is driving the tick.
        # self._data_in.shutdown()
        # .shutdown() is not available on python3.11,
        # so we have to use a flag.
        self._sender.done = True
        self._sim_thread.join()
