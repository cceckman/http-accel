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
    - A new session becomes *half-open* when the client asserts inbound.active.
    - Subsequently, the server asserts outbound.active.
    - To end the session, both `inbound.active` and `outbound.active`
      will de-assert. This can happen in either order, but they cannot assert
      again until the beginning of the next session.
    - Once the session is established, data may flow according to the
      `stream.Signature` protocol: a byte is transferred on each cycle
      where `valid` and `ready` are both asserted.
      Data must not flow until both `active` signals have been asserted.
    - An `.active` signal must not deassert until all data from the
      corresponding source has been read (i.e. until the corresponding
      `.valid` has deasserted after transferring all bytes).
    - Once an `active` signal has deasserted, it must not re-assert until
      a new session has been established (i.e. the other signal has also
      deasserted).
    """

    def __init__(self):
        super().__init__({
            "inbound": In(SessionSignature()),
            "outbound": Out(SessionSignature()),
        })
