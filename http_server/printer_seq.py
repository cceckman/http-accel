from amaranth import Module, Signal
from amaranth.lib.wiring import connect

from printer import AbstractPrinter
from stream_mux import StreamMux

class PrinterSeq(AbstractPrinter):
    """
    When activated, activates sub-printers in sequence.

    AbstractPrinter Attributes
    ----------
    output: Stream(8), out
            The data stream to write the message to.
    en:     Signal(1), in
            One-shot trigger; start writing the message to output.
    done:   Signal(1), out
            High when inactive, i.e. writing is done.
    """

    def __init__(self, sequence):
        self._sequence = sequence
        super().__init__()

    def elaborate(self, _platform):
        m = Module()

        m.d.comb += [
            self.done.eq(self._sequence[-1].done),
            self._sequence[0].en.eq(self.en),
        ]

        m.submodules.output_mux = output_mux = StreamMux(mux_width=len(self._sequence), stream_width=8)
        m.d.comb += [
            self.output.payload.eq(output_mux.out.payload),
            self.output.valid.eq(output_mux.out.valid),
            output_mux.out.ready.eq(self.output.valid),
        ]

        for i in range(0, len(self._sequence)):
            m.submodules += self._sequence[i]

            m.d.comb += self._sequence[i].en.eq(self.en)

            connect(m, self._sequence[i].output, output_mux.input[i])
            if i == 0:
                with m.If(~self._sequence[1].done):
                    m.d.comb += output_mux.select.eq(0)
            else:
                with m.If(self._sequence[i-1].done & ~self._sequence[i].done):
                    m.d.comb += output_mux.select.eq(i),

        return m
