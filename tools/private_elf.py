"""Clear embedded ELF search paths; private launcher supplies library paths.
Does not alter code, imports, sonames, or global NAS loader configuration.
"""
import struct

def private_elf(data):
    if not data.startswith(b'\x7fELF'): return data,0
    if data[4:6] != b'\x02\x01': raise ValueError('Only little-endian ELF64 is supported')
    header=struct.unpack_from('<16sHHIQQQIHHHHHH',data)
    output=bytearray(data);changes=0
    for n in range(header[10]):
        segment=struct.unpack_from('<IIQQQQQQ',data,header[5]+n*header[9])
        if segment[0]!=2: continue
        for pos in range(segment[2],segment[2]+segment[5],16):
            tag,value=struct.unpack_from('<QQ',data,pos)
            if tag==0: break
            if tag in (15,29):
                # DT_RPATH -> empty DT_RUNPATH. Dynstr offset zero is the empty string.
                struct.pack_into('<QQ',output,pos,29,0);changes+=1
    return bytes(output),changes
