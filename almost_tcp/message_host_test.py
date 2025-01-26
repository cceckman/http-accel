"""
Host-side tests for ATCP messages.
"""

import unittest
from message_host import Flags, Header


class TestMakeLayout(unittest.TestCase):

    def test_make_flags(self):
        layout = Flags()
        layout.fin = True
        layout.rst = True
        layout.ack = True
        layout.ecn = True

        self.assertEqual(layout.encode(), bytes([0x55]))

    def test_decode_header(self):
        data = bytes([0xAA, 0x98, 0x01, 0x02, 0x03,
                     0x04, 0x04, 0x05, 0x06, 0x07])
        header = Header.decode(data)
        self.assertEqual(header.flags.syn, True)
        self.assertEqual(header.flags.fin, False)
        self.assertEqual(header.stream, 0x98)
        self.assertEqual(header.length, 0x0102)


if __name__ == '__main__':
    unittest.main()
