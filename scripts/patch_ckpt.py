#!/usr/bin/env python3
"""Utility to patch Lightning checkpoint metadata for terratorch inference."""
import argparse
import torch


def main():
    parser = argparse.ArgumentParser(description="Patch terratorch checkpoint to clear legacy hyper-parameters")
    parser.add_argument("input", help="Path to original checkpoint")
    parser.add_argument("output", help="Where to write patched checkpoint")
    args = parser.parse_args()

    ckpt = torch.load(args.input, map_location="cpu")

    modified = False
    for key in ("hyper_parameters", "hparams"):
        if key in ckpt and ckpt[key]:
            ckpt[key] = {}
            modified = True

    if not modified:
        print("No hyper-parameter metadata found; nothing to patch.")
    else:
        torch.save(ckpt, args.output)
        print(f"Patched checkpoint saved to {args.output}")


if __name__ == "__main__":
    main()
