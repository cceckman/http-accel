"""
Next-level of connection management: sessions, not just backpressure

"""

from amaranth import Module, Signal, unsigned, Const
from amaranth.lib.wiring import Component, In, Out, Signature
from amaranth.lib import stream
from amaranth.lib.data import UnionLayout, ArrayLayout, Struct
from amaranth.lib.fifo import SyncFIFOBuffered


class SessionSignature(Signature):
    """
    Signature of a *session*: handshake'd data.


    Attributes
    ----------
    active: Indicates the session is, or is desired to be, active.
        Level-indicative: Deasserts after all data is sent for the session.
    data: Data for this session.
    """

    def __init__(self):
        super().__init__({
            "active": Out(1),
            "data": Out(stream.Signature(8)),
        })


class BidiSessionSignature(Signature):
    """
    - Start with inbound.session_active raised: "new request"
    - Wait for outbound.session_active to be raised before inputting data
    - Data flows
    - Wait until outbound data flushed before deasserting session_active
    - Early termination (e.g. 400): flush inbound data until inbound.session_active deasserted
    - Both zero --> reset state

    """

    def __init__(self):
        super().__init__({
            "inbound": In(SessionSignature()),
            "outbound": Out(SessionSignature()),
        })
