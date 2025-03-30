from amaranth import Module
from amaranth.lib.wiring import In

from .printer import AbstractPrinter
from .printer import Printer
from .printer_seq import PrinterSeq
from .bcd_counter import BcdCounter

class CountBody(AbstractPrinter):
    """
    When activated, prints out an body response appropriate for the /count endpoint

    Example output might look like (with some formatting):
    ```
    requests: 0010 
    ok_responses: 0008
    error_responses: 0002
    ```
    TODO: Due to bcd_counter adding leading zeros, this can't make valid JSON,
          as #s with leading zeros are interpreted as Octal. A hex counter 
          could work, or stripping the leading zeros.

    Attributes:
    ----------
    inc_requests : Signal(1), in
    inc_ok:      : Signal(1), in
    inc_error:   : Signal(1), in
                   Pulse each of these to increment the respective counters.

    AbstractPrinter Attributes
    ----------
    output: Stream(8), out
            The data stream to write the message to.
    en:     Signal(1), in
            One-shot trigger; start writing the message to output.
    done:   Signal(1), out
            High when inactive, i.e. writing is done.
    """

    inc_requests: In(1)
    inc_ok: In(1)
    inc_error: In(1)

    def __init__(self):
        super().__init__()

    def elaborate(self, _platform):
        m = Module()

        # PrinterSeq later adds these to their m.submodules.
        count_req = BcdCounter(4, ascii=True)
        count_ok = BcdCounter(4, ascii=True)
        count_error = BcdCounter(4, ascii=True)

        m.submodules.printer = printer = PrinterSeq([
            Printer("requests: "), count_req, 
            Printer(" ok_responses: "), count_ok,
            Printer(" error_responses: "), count_error,
            Printer("\r\n")
        ])

        m.d.comb += [
            self.done.eq(printer.done),
            self.output.payload.eq(printer.output.payload),
            self.output.valid.eq(printer.output.valid),

            printer.output.ready.eq(self.output.ready),
            printer.en.eq(self.en),

            count_req.inc.eq(self.inc_requests),
            count_ok.inc.eq(self.inc_ok),
            count_error.inc.eq(self.inc_error),
        ]

        return m
