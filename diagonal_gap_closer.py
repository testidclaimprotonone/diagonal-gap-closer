#!/usr/bin/env python3
"""
Diagonal Gap Closer for pixel-art line art.

Usage:
    python diagonal_gap_closer.py input.png output.png
    python diagonal_gap_closer.py input.png output.png --background white
    python diagonal_gap_closer.py input.png output.png --background transparent
    python diagonal_gap_closer.py input.png output.png --strength conservative

Requires Pillow:
    python -m pip install pillow

This is a heuristic post-process, not a semantic line-art repair tool. Work on a copy
and inspect the result; it intentionally adds pixels at diagonal-only contacts.
"""
import argparse
from collections import Counter
from PIL import Image

def is_white(rgb, threshold):
    return rgb[0] >= threshold and rgb[1] >= threshold and rgb[2] >= threshold

def main():
    parser = argparse.ArgumentParser(description="Close diagonal-only gaps in pixel-art line art.")
    parser.add_argument("input", help="Input PNG")
    parser.add_argument("output", help="Output PNG")
    parser.add_argument("--background", choices=("auto", "transparent", "white"),
                        default="auto", help="How to identify the background (default: auto)")
    parser.add_argument("--white-threshold", type=int, default=245,
                        help="RGB minimum for white-background detection (default: 245)")
    parser.add_argument("--strength", choices=("conservative", "aggressive"),
                        default="conservative",
                        help="Conservative avoids ambiguous edits; aggressive fills more diagonal contacts")
    args = parser.parse_args()

    im = Image.open(args.input).convert("RGBA")
    w, h = im.size
    px = im.load()

    if args.background == "auto":
        transparent_count = sum(1 for y in range(h) for x in range(w) if px[x, y][3] < 255)
        corners = [px[0,0], px[w-1,0], px[0,h-1], px[w-1,h-1]]
        corner_white = sum(1 for p in corners if p[3] == 255 and is_white(p[:3], args.white_threshold))
        bg_mode = "transparent" if transparent_count > 0 else ("white" if corner_white >= 2 else "white")
    else:
        bg_mode = args.background

    def foreground(x, y):
        r, g, b, a = px[x, y]
        if bg_mode == "transparent":
            return a > 0
        return not (a == 0 or is_white((r, g, b), args.white_threshold))

    mask = [[foreground(x, y) for x in range(w)] for y in range(h)]
    original = [[px[x, y] for x in range(w)] for y in range(h)]
    additions = {}

    # Consider diagonal neighbor pairs only when both orthogonal bridge pixels are empty.
    # Pick the bridge pixel that best continues the local line. The output is computed
    # from the original mask so edits do not cascade during the same pass.
    directions = ((1, 1), (1, -1))
    for y in range(h):
        for x in range(w):
            if not mask[y][x]:
                continue
            for dx, dy in directions:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < w and 0 <= ny < h and mask[ny][nx]):
                    continue
                a = (x + dx, y)
                b = (x, y + dy)
                if not (0 <= a[0] < w and 0 <= a[1] < h and
                        0 <= b[0] < w and 0 <= b[1] < h):
                    continue
                if mask[a[1]][a[0]] or mask[b[1]][b[0]]:
                    continue

                # Count nearby foreground neighbors around each candidate bridge pixel.
                def support(c):
                    cx, cy = c
                    score = 0
                    for oy in (-1, 0, 1):
                        for ox in (-1, 0, 1):
                            xx, yy = cx + ox, cy + oy
                            if (ox or oy) and 0 <= xx < w and 0 <= yy < h and mask[yy][xx]:
                                score += 1
                    return score

                sa, sb = support(a), support(b)
                if sa == sb and args.strength == "conservative":
                    continue
                chosen = a if sa >= sb else b

                # In aggressive mode, ties are filled too; in conservative mode only
                # fill when one bridge pixel has clearer neighborhood support.
                if args.strength == "aggressive" or sa != sb:
                    # Copy a neighboring line pixel's color/alpha, preserving the outline color.
                    candidates = []
                    cx, cy = chosen
                    for oy in (-1, 0, 1):
                        for ox in (-1, 0, 1):
                            xx, yy = cx + ox, cy + oy
                            if 0 <= xx < w and 0 <= yy < h and mask[yy][xx]:
                                candidates.append(original[yy][xx])
                    if candidates:
                        # Most common local color; ties follow nearest-neighbor order.
                        color = Counter(candidates).most_common(1)[0][0]
                        additions[chosen] = color

    out = im.copy()
    opx = out.load()
    for (x, y), color in additions.items():
        opx[x, y] = color

    out.save(args.output)
    print(f"Background mode: {bg_mode}")
    print(f"Added {len(additions)} pixel(s). Saved: {args.output}")

if __name__ == "__main__":
    main()
