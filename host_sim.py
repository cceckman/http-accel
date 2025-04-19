
import logging
import asyncio

from sim_server import SimServer
from not_tcp.host import StreamProxy


log = logging.getLogger(__name__)


class HostSimulator(SimServer, StreamProxy):
    # Multiple inheritance is not a *crime*, it's just an abuse of the rules.
    # Tax avoidance is not tax evasion!
    pass


async def run_server(port):
    import ntcp_http
    dut = ntcp_http.NtcpHttpServer()

    with HostSimulator(dut, dut.tx, dut.rx) as srv:
        server = await asyncio.start_server(
            client_connected_cb=srv.client_connected, host="localhost",
            port=port)
        log.info(f"listening on port {port}\n")
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(run_server(3278))
