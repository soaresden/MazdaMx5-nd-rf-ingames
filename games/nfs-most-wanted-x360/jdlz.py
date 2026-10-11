"""EA JDLZ (version 2) compression."""
import bisect
import struct


def decompress(blob):
    assert blob[:4] == b'JDLZ', blob[:4]
    out_size, comp_size = struct.unpack_from('<II', blob, 8)
    src = blob[16:comp_size]
    out = bytearray(out_size)
    ip = op = 0
    f1 = f2 = 1
    n = len(src)
    while ip < n and op < out_size:
        if f1 == 1:
            f1 = src[ip] | 0x100
            ip += 1
        if f2 == 1:
            f2 = src[ip] | 0x100
            ip += 1
        if f1 & 1:
            b0, b1 = src[ip], src[ip + 1]
            ip += 2
            if f2 & 1:
                length = (((b0 & 0xF0) << 4) | b1) + 3
                dist = (b0 & 0x0F) + 1
            else:
                length = (b0 & 0x1F) + 3
                dist = (((b0 & 0xE0) << 3) | b1) + 17
            for _ in range(length):
                out[op] = out[op - dist]
                op += 1
            f2 >>= 1
        else:
            out[op] = src[ip]
            op += 1
            ip += 1
        f1 >>= 1
    if op != out_size:
        raise ValueError('JDLZ stream ended at %d of %d' % (op, out_size))
    return bytes(out)


SHORT_MAX_DIST, SHORT_MAX_LEN = 16, 4098
LONG_MAX_DIST, LONG_MAX_LEN = 2064, 34


def _tokens(data, depth=128, start=0, end=None):
    """LZ parse with one step of lazy matching: list of ('L', byte) or ('M', length, dist).

    Only data[start:end] is encoded; the bytes before start are history that matches may point
    into (JDLZ distances never exceed LONG_MAX_DIST)."""
    n = len(data) if end is None else end
    head = {}
    toks = []

    def add(p):
        if p + 3 <= n:
            head.setdefault(data[p:p + 3], []).append(p)

    def best(i):
        best_len = best_dist = 0
        # short distances (1..16) can give very long runs: test them directly
        for dist in range(1, min(SHORT_MAX_DIST, i) + 1):
            j = i - dist
            if data[j] != data[i]:
                continue
            k = 0
            lim = min(n - i, SHORT_MAX_LEN)
            while k < lim and data[j + k] == data[i + k]:
                k += 1
            if k > best_len:
                best_len, best_dist = k, dist
        if best_len < LONG_MAX_LEN and i + 3 <= n:
            for j in reversed(head.get(data[i:i + 3], [])[-depth:]):
                dist = i - j
                if dist > LONG_MAX_DIST:
                    break
                if dist <= SHORT_MAX_DIST:
                    continue
                lim = min(n - i, LONG_MAX_LEN)
                k = 3
                while k < lim and data[j + k] == data[i + k]:
                    k += 1
                if k > best_len:
                    best_len, best_dist = k, dist
                    if k == lim:
                        break
        return best_len, best_dist

    for p in range(max(0, start - LONG_MAX_DIST), start):
        add(p)
    i = start
    nxt = None
    while i < n:
        cur = nxt if nxt is not None else best(i)
        nxt = None
        if cur[0] >= 3 and i + 1 < n:
            add(i)
            later = best(i + 1)
            if later[0] > cur[0] + 1:
                toks.append(('L', data[i]))
                i += 1
                nxt = later
                continue
            for p in range(i + 1, i + cur[0]):
                add(p)
            toks.append(('M', cur[0], cur[1]))
            i += cur[0]
        elif cur[0] >= 3:
            toks.append(('M', cur[0], cur[1]))
            for p in range(i, i + cur[0]):
                add(p)
            i += cur[0]
        else:
            toks.append(('L', data[i]))
            add(i)
            i += 1
    return toks


def compress(data):
    """JDLZ stream laid out exactly as EA's JLZCompress writes it (decomp: Misc/LZCompress.cpp).

    The game's JLZDecompress counts the input bytes down (`while (Size != 0)`) and reloads a flag
    byte right after the token that empties it, the last token included. So the encoder reserves
    the next flag byte as soon as one is full, and its loop runs once past the end of the data
    (`while (Size >= 0)`), which adds one literal; unused flag bits are 1. A stream without these
    bytes makes the game's decoder run past its end and crash (read of guest 0x18).
    """
    return emit(_tokens(data), len(data))


def emit(tokens, out_size):
    """Write a token list as a JDLZ stream, with EA's layout (see compress)."""
    out = bytearray(b'\0\0')
    p_control, p_runtype = 0, 1
    control = runtype = 0xFF00
    for t in list(tokens) + [('L', 0)]:
        if t[0] == 'M':
            _, length, dist = t
            control >>= 1
            if dist > SHORT_MAX_DIST:
                runtype = (runtype >> 1) & 0x7F7F
                D = dist - 17
                out += bytes([((D >> 8) << 5) | (length - 3), D & 0xFF])
            else:
                runtype >>= 1
                L = length - 3
                out += bytes([((L >> 8) << 4) | (dist - 1), L & 0xFF])
        else:
            control = (control >> 1) & 0x7F7F
            out.append(t[1])
        if control < 256:
            out[p_control] = control
            p_control = len(out)
            out.append(0)
            control = 0xFF00
        if runtype < 256:
            out[p_runtype] = runtype
            p_runtype = len(out)
            out.append(0)
            runtype = 0xFF00
    while control & 0xFF00:
        control >>= 1
    out[p_control] = control
    while runtype & 0xFF00:
        runtype >>= 1
    out[p_runtype] = runtype
    header = b'JDLZ' + bytes([2, 0x10, 0, 0]) + struct.pack('<II', out_size, len(out) + 16)
    return header + bytes(out)


def game_decompress(blob):
    """Python copy of the game's JLZDecompress (exact input accounting). Raises if the stream
    would make it run past its end."""
    out_size, comp = struct.unpack_from('<II', blob, 8)
    size = comp - 18
    src = blob
    ip = 18
    out = bytearray(out_size + 4098)
    op = 0
    control = src[16] | 0x100
    runtype = src[17] | 0x100
    while size != 0:
        if size < 0 or ip > comp:
            raise ValueError('decoder runs past the end of the stream')
        if control & 1:
            b0, b1 = src[ip], src[ip + 1]
            if runtype & 1:
                run = (((b0 >> 4) << 8) | b1) + 3
                off = (b0 & 15) + 1
            else:
                off = (((b0 >> 5) << 8) | b1) + 17
                run = (b0 & 31) + 3
            for k in range(run):
                out[op + k] = out[op + k - off]
            op += run
            ip += 2
            size -= 2
            runtype >>= 1
        else:
            if op < out_size:
                out[op] = src[ip]
                op += 1
            ip += 1
            size -= 1
        control >>= 1
        if control == 1:
            size -= 1
            control = src[ip] | 0x100
            ip += 1
        if runtype == 1:
            size -= 1
            runtype = src[ip] | 0x100
            ip += 1
    return bytes(out[:out_size])


def parse(blob):
    """Token list of a JDLZ stream: [('L', byte) | ('M', length, dist)]."""
    out_size, comp_size = struct.unpack_from('<II', blob, 8)
    src = blob[16:comp_size]
    toks = []
    ip = op = 0
    f1 = f2 = 1
    n = len(src)
    while ip < n and op < out_size:
        if f1 == 1:
            f1 = src[ip] | 0x100
            ip += 1
        if f2 == 1:
            f2 = src[ip] | 0x100
            ip += 1
        if f1 & 1:
            b0, b1 = src[ip], src[ip + 1]
            ip += 2
            if f2 & 1:
                length = (((b0 & 0xF0) << 4) | b1) + 3
                dist = (b0 & 0x0F) + 1
            else:
                length = (b0 & 0x1F) + 3
                dist = (((b0 & 0xE0) << 3) | b1) + 17
            toks.append(('M', length, dist))
            op += length
            f2 >>= 1
        else:
            toks.append(('L', src[ip]))
            op += 1
            ip += 1
        f1 >>= 1
    return toks


def splice(blob, data, ranges):
    """Recompress `data`, a modified copy of what the JDLZ `blob` holds, re-encoding only around
    the changed byte ranges [(a, b)]. Elsewhere the original tokens are kept, so the stream stays
    byte for byte as EA compressed it there, and about as small."""
    toks = parse(blob)
    starts = []
    op = 0
    for t in toks:
        starts.append(op)
        op += 1 if t[0] == 'L' else t[1]
    assert op == len(data), (op, len(data))
    out = []
    k = 0  # next original token to copy
    for a, b in sorted(ranges):
        i = max(bisect.bisect_right(starts, a) - 1, k)  # token holding byte a
        # first boundary far enough after b that no kept token reads a changed byte
        j = bisect.bisect_left(starts, b + LONG_MAX_DIST)
        out += toks[k:i]
        end = starts[j] if j < len(starts) else len(data)
        out += _tokens(data, start=starts[i], end=end)
        k = j
    out += toks[k:]
    return emit(out, len(data))


def splice_to_fit(blob, data, ranges, limit, window=1 << 19):
    """splice(), then re-encode more unchanged windows of `window` bytes (our parser packs a little
    tighter than EA's, about 2 KB per MB) until the stream is at most `limit` bytes. Much faster
    than compress() on a big file. None if even the whole file does not fit."""
    ranges = sorted(ranges)
    new = splice(blob, data, ranges)
    pos = 0
    while len(new) > limit and pos < len(data):
        end = min(pos + window, len(data))
        if not any(a < end and pos < b for a, b in ranges):
            ranges = sorted(ranges + [(pos, end)])
            new = splice(blob, data, ranges)
        pos = end
    return new if len(new) <= limit else None
