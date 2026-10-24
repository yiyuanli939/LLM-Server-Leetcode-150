from __future__ import annotations


# LC 722 Remove Comments
def strip_comments(lines: list[str]) -> list[str]:
    out: list[str] = []
    buf: list[str] = []
    in_block = False
    for line in lines:
        if not in_block:
            buf = []
        i, n = 0, len(line)
        while i < n:
            two = line[i:i + 2]
            if in_block:
                if two == "*/":
                    in_block = False
                    i += 2
                else:
                    i += 1
            elif two == "/*":
                in_block = True
                i += 2
            elif two == "//":
                break
            else:
                buf.append(line[i])
                i += 1
        if not in_block and buf:
            out.append("".join(buf))
    return out
