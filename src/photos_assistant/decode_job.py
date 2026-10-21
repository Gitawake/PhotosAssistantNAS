#!/usr/bin/env python3
"""Invoked only after privilege drop and network isolation."""
import os
from pathlib import Path
import sys
from worker import Decoder

def main():
    if os.geteuid()==0: raise RuntimeError('Refusing root decoding')
    work=Path(sys.argv[1]);preview=bool(int(sys.argv[2]));video=bool(int(sys.argv[3]))
    decoder=Decoder(Path(__file__).resolve().parent/'runtime');decoder.nested=True
    decoder.source_fd=int(sys.argv[4]);source='fd:';ext=sys.argv[5]
    decoder.expected_size=tuple(map(int,sys.argv[6:8])) or (0,0)
    if preview: decoder.generate(source,ext,work)
    if video: decoder.transcode(source,work)

if __name__=='__main__': main()
