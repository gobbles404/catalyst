"""Observe process memory before, during, and after an allocation."""

import numpy as np
import psutil

MIB = 1024**2


def main() -> None:
    process = psutil.Process()
    before = process.memory_info().rss

    data = np.ones(32 * MIB, dtype=np.uint8)
    holding = process.memory_info().rss

    del data
    released = process.memory_info().rss

    print(f"Before allocation: {before / MIB:.1f} MiB")
    print(f"Holding array:     {holding / MIB:.1f} MiB")
    print(f"After release:     {released / MIB:.1f} MiB")
    print(f"Increase while held: {(holding - before) / MIB:+.1f} MiB")


if __name__ == "__main__":
    main()
