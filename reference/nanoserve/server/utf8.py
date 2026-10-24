"""Reference: server.utf8_ok."""
from __future__ import annotations


# LC 393 UTF-8 Validation
def utf8_valid(data: list[int]) -> bool:
    need = 0  # continuation bytes still expected for the current character
    for byte in data:
        if need:
            if byte >> 6 != 0b10:
                return False
            need -= 1
        elif byte >> 7 == 0:
            continue
        elif byte >> 5 == 0b110:
            need = 1
        elif byte >> 4 == 0b1110:
            need = 2
        elif byte >> 3 == 0b11110:
            need = 3
        else:  # 10xxxxxx as a leading byte, or 11111xxx
            return False
    return need == 0
