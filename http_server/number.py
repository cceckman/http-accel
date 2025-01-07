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
        m.d.comb += [
            mod10.eq(accumulator % Const(10)),
            div10.eq(accumulator // Const(10)),
        ]
        count = Signal(math.ceil(math.log2(max_chars)) + 1)

        m.submodules.buffer = buffer = memory.Memory(
            shape=unsigned(8), depth=max_chars, init=[])
        write = buffer.write_port()
        read = buffer.read_port(domain="comb")

        m.d.comb += [
            write.data.eq(mod10),
            write.addr.eq(count),
            write.en.eq(Const(0)),
            self.output.valid.eq(Const(0)),
        ]

        m.d.sync += [
            self.done.eq(Const(0)),
            Assert(~(self.output.valid & self.done)),
        ]
        with m.FSM():
            with m.State("idle"):
                with m.If(self.en):
                    # At the next clock edge (transition to decimate),
                    m.d.sync += [
                        Assert(count == 0, "at idle count is not zero"),
                        # Latch the input into the accumulator:
                        accumulator.eq(self.input),
                    ]
                    m.next = "decimate"
                with m.Else():
                    m.next = "idle"
                    m.d.sync += [
                        self.done.eq(Const(1)),
                    ]
            with m.State("decimate"):
                # Store one digit in memory.
                # We latched the most recent value into the accumulator,
                # so the mod10 signal is equal to "the current digit"
                # at the end of this cycle.
                # Store that digit.
                # The write port is synchronous to "sync",
                # so we can use .comb here.
                m.d.comb += [write.en.eq(Const(1)), ]

                with m.If(div10 != 0):
                    # We have more digits to process.
                    m.d.sync += [
                        accumulator.eq(div10),
                        count.eq(count + 1),
                    ]
                    m.next = "decimate"
                with m.Else():
                    m.next = "print"
            with m.State("print"):
                # Read one digit from memory into the output stream.
                # The read port is asynchronous;
                # but the output stream is synchronous to the sync domain.
                # So we set up all the reads combinatorially here.
                m.d.comb += [
                    read.addr.eq(count),
                    self.output.payload.eq(read.data + Const(ord('0'))),
                    self.output.valid.eq(Const(1)),
                ]

                # Decrement count, on the next clock cycle,
                # if we are able to consume this cycle.
                with m.If(self.output.ready):
                    # Advance count down.
                    with m.If(count != 0):
                        m.d.sync += [
                            count.eq(count - 1),
                        ]
                    with m.Else():
                        m.next = "idle"

        return m
