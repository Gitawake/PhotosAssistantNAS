"""Clear embedded ELF search paths; private launcher supplies library paths.
Does not alter code, imports, sonames, or global NAS loader configuration.
"""
import struct

def elf_needed(data):
    """Read ELF64 DT_NEEDED names without executing upstream binaries."""
    if not data.startswith(b'\x7fELF'): return []
    if data[4:6] != b'\x02\x01': raise ValueError('Only little-endian ELF64 is supported')
    header=struct.unpack_from('<16sHHIQQQIHHHHHH',data)
    segments=[struct.unpack_from('<IIQQQQQQ',data,header[5]+n*header[9]) for n in range(header[10])]
    needed=[];address=None;length=None
    for segment in segments:
        if segment[0]!=2: continue
        for pos in range(segment[2],segment[2]+segment[5],16):
            tag,value=struct.unpack_from('<QQ',data,pos)
            if tag==0: break
            if tag==1: needed.append(value)
            elif tag==5: address=value
            elif tag==10: length=value
    if not needed: return []
    if address is None or length is None: raise ValueError('Missing ELF string table')
    for segment in segments:
        if segment[0]==1 and segment[3]<=address and address+length<=segment[3]+segment[5]:
            offset=segment[2]+address-segment[3];strings=data[offset:offset+length]
            result=[]
            for index in needed:
                end=strings.find(b'\0',index)
                if index>=len(strings) or end<0: raise ValueError('Invalid ELF dependency name')
                name=strings[index:end].decode('ascii')
                if '/' in name: raise ValueError('ELF dependency has an embedded path')
                result.append(name)
            return result
    raise ValueError('ELF string table is outside file segments')

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
