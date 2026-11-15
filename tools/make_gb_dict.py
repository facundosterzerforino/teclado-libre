"""Build a Gingerbread (Android 2.3) LatinIME binary dictionary from an AOSP
*.combined(.gz) word list.

Format (header-less, as read by native/src/dictionary.cpp in android-2.3.6_r1):
  node   := count:u8, entry*count
  entry  := char, flags_addr, [freq:u8 if terminal]
  char   := u8 (< 0xFF) | 0xFF hi:u8 lo:u8
  flags_addr := 1 byte if no children (bit 0x80 = terminal, bit 0x40 clear)
              | 3 bytes: (0x80 terminal | 0x40 has address | addr>>16 & 0x3F), addr>>8, addr
Children addresses are absolute offsets. The root node is at offset 0.
"""
import argparse
import gzip
import re


def read_wordlist(path):
    opener = gzip.open if path.endswith('.gz') else open
    words = {}
    with opener(path, 'rt', encoding='utf-8') as f:
        for line in f:
            m = re.match(r'^\s+word=([^,]+),f=(\d+)', line)
            if m:
                w, freq = m.group(1), int(m.group(2))
                words[w] = max(freq, words.get(w, 0))
    return words


class Node:
    __slots__ = ('children', 'freq', 'offset')

    def __init__(self):
        self.children = {}
        self.freq = 0  # 0 = not terminal
        self.offset = 0


def build_trie(words):
    root = Node()
    for w, freq in words.items():
        n = root
        for ch in w:
            n = n.children.setdefault(ch, Node())
        n.freq = max(1, min(255, freq))
    return root


def char_size(ch):
    return 1 if ord(ch) < 0xFF else 3


def node_size(n):
    size = 1
    for ch, c in n.children.items():
        size += char_size(ch) + (3 if c.children else 1) + (1 if c.freq else 0)
    return size


def layout(root):
    order, queue, pos = [], [root], 0
    while queue:  # breadth-first keeps the hot top levels together
        nxt = []
        for n in queue:
            if len(n.children) > 255:
                raise ValueError('More than 255 children in one node')
            n.offset = pos
            pos += node_size(n)
            order.append(n)
            # Leaves are never addressed (their address flag is clear): do not emit empty nodes.
            nxt.extend(n.children[k] for k in sorted(n.children) if n.children[k].children)
        queue = nxt
    if pos > 0x3FFFFF:
        raise ValueError('Dictionary too large for 22-bit addresses')
    return order, pos


def serialize(order, total):
    out = bytearray()
    for n in order:
        assert len(out) == n.offset
        out.append(len(n.children))
        for ch in sorted(n.children):
            c = n.children[ch]
            code = ord(ch)
            if code < 0xFF:
                out.append(code)
            else:
                out += bytes((0xFF, code >> 8, code & 0xFF))
            flags = 0x80 if c.freq else 0
            if c.children:
                a = c.children and c.offset
                out += bytes((flags | 0x40 | ((a >> 16) & 0x3F), (a >> 8) & 0xFF, a & 0xFF))
            else:
                out.append(flags)
            if c.freq:
                out.append(c.freq)
    assert len(out) == total
    return bytes(out)


def read_back(data):
    """Independent reader mirroring dictionary.cpp; yields (word, freq)."""
    def walk(pos, prefix):
        count = data[pos]; pos += 1
        for _ in range(count):
            code = data[pos]; pos += 1
            if code == 0xFF:
                code = (data[pos] << 8) | data[pos + 1]; pos += 2
            flag = data[pos]
            terminal = flag & 0x80
            if flag & 0x40:
                addr = ((flag & 0x3F) << 16) | (data[pos + 1] << 8) | data[pos + 2]; pos += 3
            else:
                addr = 0; pos += 1
            freq = 0
            if terminal:
                freq = data[pos]; pos += 1
            word = prefix + chr(code)
            if terminal:
                yield word, freq
            if addr:
                yield from walk(addr, word)
    yield from walk(0, '')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('wordlist')
    p.add_argument('output')
    p.add_argument('--max-words', type=int, default=60000)
    a = p.parse_args()
    words = read_wordlist(a.wordlist)
    latin1 = {w: f for w, f in words.items() if all(ord(c) < 0x100 and c.isprintable() for c in w)}
    top = dict(sorted(latin1.items(), key=lambda kv: (-kv[1], kv[0]))[:a.max_words])
    order, total = layout(build_trie(top))
    data = serialize(order, total)
    if data[0] >= 200 and data[1] in (0, 1):
        raise ValueError('Root would be misread as a versioned dictionary header')
    back = dict(read_back(data))
    assert back == {w: max(1, min(255, f)) for w, f in top.items()}, 'Round-trip mismatch'
    with open(a.output, 'wb') as f:
        f.write(data)
    print(f'{len(top)} words (of {len(words)}), min freq {min(top.values())}, {len(data)} bytes, round-trip OK')


if __name__ == '__main__':
    main()
