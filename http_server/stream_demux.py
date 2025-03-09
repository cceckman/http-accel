from amaranth import Module, Array, Const
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream

class StreamDemux(Component):
    """
    Takes in a single stream and demuxes it to multiple possible outputs.

    Parameters:
    -----------
    mux_width: int
        Number of output channels.
    stream_width: int
        Width of each of the streams.

    Attributes:
    input:  Stream(stream_width), in
            Input datastream
    select: Signal(log_2(stream_width)), in
            Selects between the possible datastream outputs
    outs:   Array(Stream(stream_width)), out
            Selected datastream
    """

    def __init__(self, mux_width, stream_width, **kwargs):
        import math
        size = math.ceil(math.log2(mux_width))

        super().__init__({
            "input"  : In(stream.Signature(stream_width)),
            "select" : In(size),
            "outs"   : Out(stream.Signature(stream_width)).array(mux_width),
        })
        self._mux_width = mux_width

        # Need to create an Amaranth Array instance to index with an Amaranth signal.
        self._output_array = Array([*self.outs])

    def elaborate(self, _platform):
        m = Module()

        with m.If(self.select < self._mux_width):
            m.d.comb += [
                self._output_array[self.select].payload.eq(self.input.payload),
                self._output_array[self.select].valid.eq(self.input.valid),
                self.input.ready.eq(self._output_array[self.select].ready)
            ]
        with m.Else():
            m.d.comb += [
                self._output_array[self.select].payload.eq(Const(0)),
                self._output_array[self.select].valid.eq(Const(0)),
                self.input.ready.eq(Const(0)),
            ]

        return m
