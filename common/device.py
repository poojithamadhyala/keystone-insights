"""Pick the best available torch device: CUDA > Apple MPS > CPU.

Same code runs unchanged on an NVIDIA box, an M-series Mac, or CI. Override with
LEASELENS_DEVICE=cpu|mps|cuda (e.g. to benchmark CPU on a Mac)."""

import os


def best_device() -> str:
    forced = os.environ.get("LEASELENS_DEVICE")
    if forced:
        return forced
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"
