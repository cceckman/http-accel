from amaranth import Module
from amaranth.lib.wiring import In, Out, Component
from amaranth.lib import stream


class SimpleLedHttp(Component):
    """
    SimpleLedHttp accepts an HTTP/1.0 request to change LED colors.

    Returns an HTTP OK status if accpeted.

    Expects a POST to the /led path with a body containing 8 hex
    characters corresponding to red, green, and blue LED values.

    Attributes
    ----------
    request: Signal(1), in
             Indicates the start of a new request.
    input:   Stream(8), in
             HTTP stream request

    red:      Signal(8), out
    green:    Signal(8), out
    blue:     Signal(8), out
              r/g/b values to send to LEDs.

    output:   Stream(8), out
              HTTP stream response
    complete: Signal(1), out
              Indicates completion of response. 
    """

    def __init__(self, **kwargs):
        super().__init__({
                "input"   : In(stream.Signature(8)),
                "request" : In(1),
                "red"     : Out(8),
                "green"   : Out(8),
                "blue"    : Out(8),
                "out"     : Out(stream.Signature(8)),
                "complete": Out(1)
            }, **kwargs)


    def elaborate(self, _platform):
        m = Module()

        # TODO: #3 - Implement for real. Currently has a sync block so simple_led_http_test
        # will elaborate.
        m.d.sync += [
            self.red.eq(self.input.payload)
        ]

        return m
