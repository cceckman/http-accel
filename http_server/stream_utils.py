from amaranth import Module, Signal
from amaranth.lib import stream

def tree_and(m: Module, inputs: list[Signal]) -> Signal:
    if len(inputs)==1:
        return inputs[0]
    elif len(inputs)==2:
        result = Signal(1)
        m.d.comb += result.eq(inputs[0] & inputs[1])
        return result
    else:
        l = len(inputs)
        left = tree_and(m, inputs[:l//2])
        right = tree_and(m, inputs[l//2:])
        return tree_and(m, [left, right])
    
def tree_or(m: Module, inputs: list[Signal]) -> Signal:
    if len(inputs)==1:
        return inputs[0]
    elif len(inputs)==2:
        result = Signal(1)
        m.d.comb += result.eq(inputs[0] | inputs[1])
        return result
    else:
        l = len(inputs)
        left = tree_or(m, inputs[:l//2])
        right = tree_or(m, inputs[l//2:])
        return tree_or(m, [left, right])

    
def fanout_stream(m: Module, input: stream.Signature, outputs: list[stream.Signature]):
    combined_ready = tree_and(m, [o.ready for o in outputs])
    m.d.comb += input.ready.eq(combined_ready)

    for o in outputs:
        m.d.comb += [
            o.valid.eq(input.valid),
            o.payload.eq(input.payload),
        ]
