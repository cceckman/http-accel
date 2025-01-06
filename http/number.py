from amaranth import Module, Signal, unsigned, Const, Assert
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream
from amaranth.lib import memory


class Number(Component):
    """
    When activated, ASCII-prints an unsigned integer to its output.

    Parameters
    ----------
    width:  int
            Width of the number in bits.

    Attributes
    ----------
    input:  Signal(width), in
            Number to output.
    output: Stream(8), out
            The data stream to write the message to.
    en:     Signal(1), in
            One-shot trigger; start writing the message to output.
    done:   Signal(1), out
            High when inactive, i.e. writing is done.
    """
    # TODO: Make "output, en, done" a Signature.

    def __init__(self, width):
        super().__init__({
            "input": In(width),
            "output": Out(stream.Signature(unsigned(8))),
            "en": In(1),
            "done": Out(1, init=1),
        })
        self._width = width

    def elaborate(self, platform):
        m = Module()

        # For a value up to (2**width)-1, we may need up to
        #   log10((2**width)-1)
        # digits.
        # Wikipedia reminds us:
        #   log_b(x**d) == d log_b(x)
        # In this case:
        #   log_10(2**w) == w * log_10(2)
        import math
        max_chars = math.ceil(self._width * math.log10(2)) + 1
        # We add 1 for "safety" (in case I messed up the math there).

        # Internal signals:
        accumulator = Signal(self._width)
        mod10 = Signal(self._width)
        div10 = Signal(self._width)
        # TODO: ASCII conversion before or after memory?
        # Which one is faster?
        ascii = Signal(self._width)
        m.d.comb += [
            mod10.eq(accumulator % Const(10)),
            div10.eq(accumulator // Const(10)),
            ascii.eq(mod10 + Const(ord('0'))),
        ]
        count = Signal(math.ceil(math.log2(max_chars)) + 1)

        m.submodules.buffer = buffer = memory.Memory(
            shape=unsigned(8), depth=max_chars, init=[])
        write = buffer.write_port()
        read = buffer.read_port(transparent_for=(write,))

        m.d.sync += [
            self.done.eq(Const(0)),
            self.output.valid.eq(Const(0)),
            write.en.eq(Const(0)),
        ]
        m.d.comb += [
            write.data.eq(ascii),
            write.addr.eq(count),
            read.addr.eq(count),
            self.output.payload.eq(read.data),
        ]
        with m.FSM():
            with m.State("idle"):
                m.next = "idle"
                m.d.sync += [
                    self.done.eq(Const(1)),
                    self.output.valid.eq(Const(0)),
                ]
                with m.If(self.en):
                    # Kick things off.
                    m.d.sync += [
                        Assert(count == 0, "at idle count is not zero"),
                        # Latch the input
                        accumulator.eq(self.input),
                        # Acknowledge the request
                        self.done.eq(Const(0)),
                        # Immediately start storing
                        write.en.eq(Const(1)),
                    ]
                    m.next = "decimate"
            with m.State("decimate"):
                # Store one digit in memory.
                m.next = "decimate"
                m.d.sync += write.en.eq(Const(1))
                # The data is (combinatorially) equal to acc -> ASCII,
                # so at the "exit" of this state
                # we'll store a valid ASCII character.
                with m.If(div10 != 0):
                    m.d.sync += [
                        accumulator.eq(div10),
                        count.eq(count + 1),
                    ]
                with m.Else():
                    m.next = "print"
            with m.State("print"):
                m.d.sync += [
                    self.output.valid.eq(Const(1)),
                ]

                with m.If(self.output.ready):
                    # Advance count back down.
                    with m.If(count != 0):
                        m.d.sync += [count.eq(count - 1)]
                    with m.Else():
                        m.next = "idle"

        return m
