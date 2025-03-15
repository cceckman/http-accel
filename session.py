"""
Next-level of connection management: sessions, not just backpressure

"""

from amaranth.lib.wiring import In, Out, Signature
from amaranth.lib import stream


class SessionSignature(Signature):
    """
    Signature of a *session*: a reusable data stream interface.


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
    A bidirectional session-oriented data stream.
    A pair of SessionSignatures that control inbound and outbound data,
    and provide a bidirectional handshake for starting a new session.

    The sequence of usage is as follows:

    - At reset, inbound.active and outbound.active are both zero.
    - A new session starts with inbound.active raised
    - The session manager wait for outbound.active to be raised before
      passing data into inbound.data. inbound.data and outbound.data
      perform flow control as usual
    - Data flows for a while
    - At the end of a session, inbound.active OR outbound.active deasserts,
      after all data has been consumed (i.e. data.valid goes low for
      the final time)
    - The still-active end must continue consuming data until
      the other .active goes low
    - Once both .active are low, the session has been reset, and a new session
      can proceed
    """

    def __init__(self):
        super().__init__({
            "inbound": In(SessionSignature()),
            "outbound": Out(SessionSignature()),
        })
