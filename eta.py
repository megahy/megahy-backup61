# Copyright (c) 2026 Marwan Megahy
# SPDX-License-Identifier: GPL-3.0-or-later
# This program is free software: you can redistribute it and/or modify it under the
# terms of the GNU General Public License version 3 or (at your option) any later
# version. See LICENSE.txt.
"""Rough, pause-aware copy ETA from observed file and byte rates. No benchmark."""
import math
import threading
import time


class CopyProgress:
    def __init__(self, clock=time.monotonic):
        self.clock=clock;self.lock=threading.Lock();self.started=None
        self.pause_started=None;self.paused_total=0.0;self.sizes={};self.done=set();self.bytes_verified=0

    def begin(self,sizes):
        with self.lock:
            self.sizes=dict(sizes);self.done=set();self.bytes_verified=0
            self.started=self.clock();self.pause_started=None;self.paused_total=0.0

    def pause(self):
        with self.lock:
            if self.started is not None and self.pause_started is None:self.pause_started=self.clock()

    def resume(self):
        with self.lock:
            if self.pause_started is not None:
                self.paused_total+=self.clock()-self.pause_started;self.pause_started=None

    def record(self,source,verified_bytes):
        with self.lock:
            if source not in self.done:
                self.done.add(source);self.bytes_verified+=max(0,verified_bytes)

    def snapshot(self):
        with self.lock:
            now=self.pause_started if self.pause_started is not None else self.clock()
            elapsed=0.0 if self.started is None else max(0.0,now-self.started-self.paused_total)
            remaining={p:n for p,n in self.sizes.items() if p not in self.done}
            known=[n for n in self.sizes.values() if n is not None]
            unknown=sum(n is None for n in self.sizes.values())
            bytes_left=sum(n for n in remaining.values() if n is not None)
            result=dict(eta_seconds=None,eta_basis='Estimating after a few completed files',copy_active_seconds=round(elapsed,1),bytes_verified=self.bytes_verified,bytes_total_known=sum(known),size_known_files=len(known),size_unknown_files=unknown,eta_files_remaining=len(remaining))
            if self.started is None:return result
            if not remaining:
                result.update(eta_seconds=0,eta_basis='Selected file attempts finished; rescan/report may still be running')
                return result
            if len(self.done)<3 or elapsed<2:return result
            if self.bytes_verified<1024*1024 and bytes_left>8*1024*1024:
                result['eta_basis']='Learning byte speed; larger files remain'
                return result
            file_eta=len(remaining)*elapsed/len(self.done)
            byte_eta=bytes_left*elapsed/self.bytes_verified if self.bytes_verified else 0.0
            estimate=max(file_eta,byte_eta)
            if math.isfinite(estimate):
                result['eta_seconds']=max(1,math.ceil(estimate))
                result['eta_basis']='Rough file-count and byte-rate estimate' if self.bytes_verified else 'File-count estimate; no verified byte-rate sample yet'
                if unknown:result['eta_basis']+='; some file sizes are unknown'
            return result
