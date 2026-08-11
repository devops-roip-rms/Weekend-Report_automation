from __future__ import annotations


class RecordingBrowserDriver:
    def create_synthetic_device(self, *_args, **_kwargs):
        raise RuntimeError("Recording browser automation is blocked until safe selectors and values are approved")

    def delete_synthetic_device(self, *_args, **_kwargs):
        raise RuntimeError("Recording browser cleanup is blocked until safe selectors and values are approved")
