import asyncio
import logging
import serial
import traceback

from not_tcp.host import StreamProxy


log = logging.getLogger(__name__)


class HostSerial(StreamProxy):
    """
    The real deal: serving to the Fomu.
    """

    def __init__(self, path):
        """
        Arguments
        --------
        path: path to the serial device
        """
        self._path = path
        self._conn = None

    def __enter__(self):
        assert self._conn is None, "HostSerial is not reentrant"
        self._conn = serial.Serial(
            self._path, baudrate=9600, timeout=1, inter_byte_timeout=1)
        assert self._conn.is_open, "HostSerial failed to open device"

        return self

    def __exit__(self, exc_type, exc_value, exe_traceback):
        if exe_traceback is not None:
            traceback.print_tb(exe_traceback)

        self._conn.close()
        self._conn = None

    def send(self, b: bytes):
        if self._conn is None or not self._conn.is_open:
            log.error("HostSerial is not initialized")
            return
        self._conn.write(b)
        self._conn.flush()
        hex = b.hex(sep=' ')
        log.debug(f"Wrote {len(b)} bytes to serial: ", hex)

    def recv(self) -> bytes:
        if self._conn is None or not self._conn.is_open:
            log.error("HostSerial is not initialized")
            return bytes()

        # USB CDC is 64B, and we pad.
        v = self._conn.read(64)
        if v is None:
            return bytes()
        return v


async def amain(port):
    # TODO: Scan for devices, set up or reset.
    with HostSerial("/dev/ttyACM0") as srv:
        server = await asyncio.start_server(
            client_connected_cb=srv.client_connected,
            host="localhost",
            port=port
        )
        log.info(f"listening on port {port}\n")
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(amain(3278))
