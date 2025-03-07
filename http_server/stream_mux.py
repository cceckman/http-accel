from amaranth import Module, Array, Const
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream

class StreamMux(Component):
    """
    Takes in multiple streams and muxes to a single stream.

    Parameters:
    -----------
    mux_width: int
        Number of input channels.
    stream_width: int
        Width of each of the input streams.

    Attributes:
    inputs: Array(Stream(stream_width)), in
            Input datastreams
    select: Signal(log_2(stream_width)), in
            Selects between the possible datastreams
    out:    Stream(stream_width), out
            Selected datastream
    """

    def __init__(self, mux_width, stream_width, **kwargs):
        import math
        size = math.ceil(math.log2(mux_width))

        super().__init__({
            "input"  : In(stream.Signature(stream_width)).array(mux_width),
            "select" : In(size),
            "out"    : Out(stream.Signature(stream_width)),
        })
        self._mux_width = mux_width

        # Need to create an Amaranth Array instance to index with an Amaranth signal.
        self._input_array = Array([*self.input])

    def elaborate(self, _platform):
        m = Module()

        with m.If(self.select < self._mux_width):
            m.d.comb += [
                self.out.payload.eq(self._input_array[self.select].payload),
                self.out.valid.eq(self._input_array[self.select].valid),
                self._input_array[self.select].ready.eq(self.out.ready),
            ]
        with m.Else():
            m.d.comb += [
                self.out.payload.eq(Const(0)),
                self.out.valid.eq(Const(0)),
                self._input_array[self.select].ready.eq(Const(0)),
            ]

        return m
