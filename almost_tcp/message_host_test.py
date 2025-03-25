"""
Host-side tests for ATCP messages.
"""

from message_host import Flags, Header


def test_make_flags():
    layout = Flags()
    layout.fin = True
    layout.rst = True
    layout.ack = True
    layout.ecn = True

    assert layout.encode() == bytes([0x55])


def test_decode_header():
    data = bytes([0xAA, 0x98, 0x01, 0x02, 0x03,
                 0x04, 0x04, 0x05, 0x06, 0x07])
    header = Header.decode(data)
    assert header.flags.syn
    assert not header.flags.fin
    assert header.stream == 0x98
    assert header.length == 0x0102
