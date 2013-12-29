# Intel ME ROM image dumper/extractor
# Copyright (c) 2012 Igor Skochinsky
# Version 0.1 2012-10-10
# Version 0.2 2013-08-15
#
# This software is provided 'as-is', without any express or implied
# warranty. In no event will the authors be held liable for any damages
# arising from the use of this software.
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
#
#    1. The origin of this software must not be misrepresented; you must not
#    claim that you wrote the original software. If you use this software
#    in a product, an acknowledgment in the product documentation would be
#    appreciated but is not required.
#
#    2. Altered source versions must be plainly marked as such, and must not be
#    misrepresented as being the original software.
#
#    3. This notice may not be removed or altered from any source
#    distribution.
#
# Modified version 2013-12-29 Damien Zammit
#

import ctypes
import struct
import sys
import os
import array

uint8_t  = ctypes.c_ubyte
char     = ctypes.c_char
uint32_t = ctypes.c_uint
uint64_t = ctypes.c_uint64
uint16_t = ctypes.c_ushort

def replace_bad(value, deletechars):
    for c in deletechars:
        value = value.replace(c,'_')
    return value

def read_struct(li, struct):
    s = struct()
    slen = ctypes.sizeof(s)
    bytes = li.read(slen)
    fit = min(len(bytes), slen)
    ctypes.memmove(ctypes.addressof(s), bytes, fit)
    return s

def get_struct(str_, off, struct):
    s = struct()
    slen = ctypes.sizeof(s)
    bytes = str_[off:off+slen]
    fit = min(len(bytes), slen)
    ctypes.memmove(ctypes.addressof(s), bytes, fit)
    return s

def DwordAt(f, off):
    return struct.unpack("<I", f[off:off+4])[0]

class MeModuleHeader1(ctypes.LittleEndianStructure):
    _fields_ = [
        ("Tag",            char*4),   # $MME
        ("Guid",           uint8_t*16), #
        ("MajorVersion",   uint16_t), #
        ("MinorVersion",   uint16_t), #
        ("HotfixVersion",  uint16_t), #
        ("BuildVersion",   uint16_t), #
        ("Name",           char*16),  #
        ("Hash",           uint8_t*20), #
        ("Size",           uint32_t), #
        ("Flags",          uint32_t), #
        ("Unk48",          uint32_t), #
        ("Unk4C",          uint32_t), #
    ]

    def __init__(self):
        self.Offset = None

    def comptype(self):
        return COMP_TYPE_NOT_COMPRESSED

    def print_flags(self):
        print "    Disable Hash:   %d" % ((self.Flags>>0)&1)
        print "    Optional:       %d" % ((self.Flags>>1)&1)
        if self.Flags >> 2:
            print "    Unknown B2_31: %d" % ((self.Flags>>2))

    def pprint(self):
        print "Header tag:     %s" % (self.Tag)
        nm = self.Name.rstrip('\0')
        print "Module name:    %s" % (nm)
        print "Guid:           %s" % (" ".join("%02X" % v for v in self.Guid))
        print "Version:        %d.%d.%d.%d" % (self.MajorVersion, self.MinorVersion, self.HotfixVersion, self.BuildVersion)
        print "Hash:           %s" % (" ".join("%02X" % v for v in self.Hash))
        print "Size:           0x%08X" % (self.Size)
        if self.Offset != None:
            print "(Offset):       0x%08X" % (self.Offset)
        print "Flags:          0x%08X" % (self.Flags)
        self.print_flags()
        print "Unk48:          0x%08X" % (self.Unk48)
        print "Unk4C:          0x%08X" % (self.Unk4C)

class MeModuleFileHeader1(ctypes.LittleEndianStructure):
    _fields_ = [
        ("Tag",            char*4),   # $MOD
        ("Unk04",          uint32_t), #
        ("Unk08",          uint32_t), #
        ("MajorVersion",   uint16_t), #
        ("MinorVersion",   uint16_t), #
        ("HotfixVersion",  uint16_t), #
        ("BuildVersion",   uint16_t), #
        ("Unk14",          uint32_t), #
        ("CompressedSize", uint32_t), #
        ("UncompressedSize", uint32_t), #
        ("LoadAddress",    uint32_t), #
        ("MappedSize",     uint32_t), #
        ("Unk28",          uint32_t), #
        ("Unk2C",          uint32_t), #
        ("Name",           char*16),  #
        ("Guid",           uint8_t*16), #
    ]

    def pprint(self):
        print "Module tag:        %s" % (self.Tag)
        nm = self.Name.rstrip('\0')
        print "Module name:       %s" % (nm)
        print "Guid:              %s" % (" ".join("%02X" % v for v in self.Guid))
        print "Version:           %d.%d.%d.%d" % (self.MajorVersion, self.MinorVersion, self.HotfixVersion, self.BuildVersion)
        print "Unk04:             0x%08X" % (self.Unk04)
        print "Unk08:             0x%08X" % (self.Unk08)
        print "Unk14:             0x%08X" % (self.Unk14)
        print "Compressed size:   0x%08X" % (self.CompressedSize)
        print "Uncompressed size: 0x%08X" % (self.UncompressedSize)
        print "Mapped address:    0x%08X" % (self.LoadAddress)
        print "Mapped size:       0x%08X" % (self.MappedSize)
        print "Unk28:             0x%08X" % (self.Unk28)
        print "Unk2C:             0x%08X" % (self.Unk2C)

MeModulePowerTypes = ["POWER_TYPE_RESERVED", "POWER_TYPE_M0_ONLY", "POWER_TYPE_M3_ONLY", "POWER_TYPE_LIVE"]
MeCompressionTypes = ["COMP_TYPE_NOT_COMPRESSED", "COMP_TYPE_HUFFMAN", "COMP_TYPE_LZMA", "<unknown>"]
COMP_TYPE_NOT_COMPRESSED = 0
COMP_TYPE_HUFFMAN = 1
COMP_TYPE_LZMA = 2
MeModuleTypes      = ["DEFAULT", "PRE_ME_KERNEL", "VENOM_TPM", "APPS_QST_DT", "APPS_AMT", "TEST"]
MeApiTypes         = ["API_TYPE_DATA", "API_TYPE_ROMAPI", "API_TYPE_KERNEL", "<unknown>"]

class HuffmanLUTHeader(ctypes.LittleEndianStructure):
    _fields_ = [
        ("LLUT",           char*4),   # LLUT
        ("Unk04",          uint32_t), #
        ("Unk08",          uint32_t), #
        ("Unk0C",          uint32_t), #
        ("Unk10",          uint32_t), #
        ("DataStart",      uint32_t), # Start of data
        ("Unk18",          uint8_t*24), #
        ("LLUTLen",        uint32_t), #
        ("Unk34",          uint32_t), #
        ("Chipset",        char*8),   # PCH
    ]

class MeModuleHeader2(ctypes.LittleEndianStructure):
    _fields_ = [
        ("Tag",            char*4),   # $MME
        ("Name",           char*16),  #
        ("Hash",           uint8_t*32), #
        ("LoadBaseA4",     uint32_t), #
        ("Offset",         uint32_t), # From the manifest
        ("SizeUncompr",    uint32_t), #
        ("Size",           uint32_t), #
        ("OffsetLLUTSt",   uint32_t), #
        ("OffsetLLUTSt2",  uint32_t), #
        ("LoadBaseA5",     uint32_t), #
        ("Flags",          uint32_t), #
        ("Unk54",          uint32_t), #
        ("Unk58",          uint32_t), #
        ("Unk5C",          uint32_t), #
    ]

    def comptype(self):
        return (self.Flags>>4)&7

    def print_flags(self):
        print "    Unknown B0:     %d" % ((self.Flags>>0)&1)
        powtype = (self.Flags>>1)&3
        print "    Power Type:     %s (%d)" % (MeModulePowerTypes[powtype], powtype)
        print "    Unknown B3:     %d" % ((self.Flags>>3)&1)
        comptype = (self.Flags>>4)&7
        print "    Compression:    %s (%d)" % (MeCompressionTypes[comptype], comptype)
        modstage = (self.Flags>>7)&0xF
        if modstage < len(MeModuleTypes):
            smtype = MeModuleTypes[modstage]
        else:
            smtype = "STAGE %X" % modstage
        print "    Stage:          %s (%d)" % (smtype, modstage)
        apitype = (self.Flags>>11)&7
        print "    API Type:       %s (%d)" % (MeApiTypes[apitype], apitype)

        print "    Unknown B14:    %d" % ((self.Flags>>14)&1)
        print "    Unknown B15:    %d" % ((self.Flags>>15)&1)
        print "    Privileged:     %d" % ((self.Flags>>16)&1)
        print "    Unknown B17_19: %d" % ((self.Flags>>17)&7)
        print "    Unknown B20_21: %d" % ((self.Flags>>20)&3)
        if self.Flags >> 22:
            print "    Unknown B22_31: %d" % ((self.Flags>>22))

    def pprint(self):
        print "Header tag:     %s" % (self.Tag)
        nm = self.Name.rstrip('\0')
        print "Module name:    %s" % (nm)
        print "Hash:           %s" % (" ".join("%02X" % v for v in self.Hash))
        print "LoadBaseA4:     0x%08X" % (self.LoadBaseA4)
        print "Offset:         0x%08X" % (self.Offset)
        print "SizeUncompr:    0x%08X" % (self.SizeUncompr)
        print "Size:           0x%08X" % (self.Size)
        print "OffsetLLUTSt:   0x%08X" % (self.OffsetLLUTSt)
        print "OffsetLLUTSt2:  0x%08X" % (self.OffsetLLUTSt2)
        print "LoadBaseA5:     0x%08X" % (self.LoadBaseA5)
        print "Flags:          0x%08X" % (self.Flags)
        self.print_flags()
        print "Unk54:          0x%08X" % (self.Unk54)
        print "Unk58:          0x%08X" % (self.Unk58)
        print "Unk5C:          0x%08X" % (self.Unk5C)


def extract_code_mods(nm, f, soff):
    try:
       os.mkdir(nm)
    except:
       pass
    os.chdir(nm)
    print " extracting CODE partition %s" % (nm)
    manif = get_struct(f, soff, MeManifestHeader)
    manif.parse_mods(f, soff)
    manif.pprint()
    manif.extract(f, soff)
    os.chdir("..")


class MeManifestHeader(ctypes.LittleEndianStructure):
    _fields_ = [
        ("ModuleType",     uint16_t), # 00
        ("ModuleSubType",  uint16_t), # 02
        ("HeaderLen",      uint32_t), # 04 in dwords
        ("HeaderVersion",  uint32_t), # 08
        ("Flags",          uint32_t), # 0C 0x80000000 = Debug
        ("ModuleVendor",   uint32_t), # 10
        ("Date",           uint32_t), # 14 BCD yyyy.mm.dd
        ("Size",           uint32_t), # 18 in dwords
        ("Tag",            char*4),   # 1C $MAN or $MN2
        ("NumModules",     uint32_t), # 20
        ("MajorVersion",   uint16_t), # 24
        ("MinorVersion",   uint16_t), # 26
        ("HotfixVersion",  uint16_t), # 28
        ("BuildVersion",   uint16_t), # 2A
        ("Unknown1",       uint32_t*19), # 2C
        ("KeySize",        uint32_t), # 78
        ("ScratchSize",    uint32_t), # 7C
        ("RsaPubKey",      uint32_t*64), # 80
        ("RsaPubExp",      uint32_t),    # 180
        ("RsaSig",         uint32_t*64), # 184
        ("PartitionName",  char*12),    # 284
        # 290
    ]

    def parse_mods(self, f, offset):
        self.modules = []
        self.updparts = []
        orig_off = offset
        offset += self.HeaderLen*4
        offset += 12
        if self.Tag == '$MN2':
            htype = MeModuleHeader2
            hdrlen = ctypes.sizeof(htype)
            udc_fmt = "<4s32s16sII"
            udc_len = 0x3C
        elif self.Tag == '$MAN':
            htype = MeModuleHeader1
            hdrlen = ctypes.sizeof(htype)
            udc_fmt = "<4s20s16sII"
            udc_len = 0x30
        else:
            raise Exception("Don't know how to parse modules for manifest tag %s!" % self.Tag)

	modmap = {}
        for i in range(self.NumModules):
            mod = get_struct(f, offset, htype)
            if not [mod.Tag in '$MME', '$MDL']:
                raise Exception("Bad module tag (%s) at offset %08X!" % (mod.Tag, offset))
            nm = mod.Name.rstrip('\0')
            modmap[nm] = mod
            self.modules.append(mod)
            if mod.comptype() == COMP_TYPE_HUFFMAN:
                llut = get_struct(f, orig_off + mod.Offset, HuffmanLUTHeader)
		lluttag = "LLUT"
		if llut.LLUT != lluttag.rstrip('\0'):
			raise Exception("Bad Huffman LLUT header")
		mod.huff_start = llut.DataStart + mod.OffsetLLUTSt2
		mod.huff_end = mod.huff_start + mod.Size
            offset += hdrlen

        self.partition_end = None
        hdr_end = orig_off + self.Size*4
        while offset < hdr_end:
            print "tags %08X" % offset
            hdr = f[offset:offset+8]
            if hdr == '\xFF' * 8:
                offset += hdrlen
                continue
            if len(hdr) < 8 or hdr[0] != '$':
                break
            tag, elen = hdr[:4], struct.unpack("<I", hdr[4:])[0]
            if elen == 0:
                break
            print "Tag: %s, data length: %08X (0x%08X bytes)" % (tag, elen, elen*4)
            if tag == '$UDC':
                subtag, hash, subname, suboff, size = struct.unpack(udc_fmt, f[offset+8:offset+8+udc_len])
                suboff += offset
                print "Update code part: %s, %s, offset %08X, size %08X" % (subtag, subname.rstrip('\0'), suboff, size)
                self.updparts.append((subtag, suboff, size))
            elif elen == 3:
                val = struct.unpack("<I", f[offset+8:offset+12])[0]
                print "%s: %08X" % (tag[1:], val)
            elif elen == 4:
                vals = struct.unpack("<II", f[offset+8:offset+16])
                print "%s: %08X %08X" % (tag[1:], vals[0], vals[1])
            else:
                vals = array.array("I", f[offset+8:offset+elen*4])
                print "%s: %s" % (tag[1:], " ".join("%08X" % v for v in vals))
                if tag == '$MCP':
                    self.partition_end = vals[0] + vals[1]
            offset += elen*4

        offset = hdr_end
        while True:
            print "mods %08X" % offset
            if f[offset:offset+4] != '$MOD':
                break
            mfhdr = get_struct(f, offset, MeModuleFileHeader1)
            mfhdr.pprint()
            nm = mfhdr.Name.rstrip('\0')
            mod = modmap[nm]
            mod.Offset = offset - orig_off
            mod.UncompressedSize = mfhdr.UncompressedSize
            offset += mod.Size
        
        # check for huffman LUT
        #offset = self.huff_start
        #if f[offset+1:offset+4] == 'LUT':
        #    cnt, unk8, unkc, complen = struct.unpack("<IIII", f[offset+4:offset+20])
        #    self.huff_end = offset + 0x40 + 4*cnt + complen
        #else:
        #    self.huff_start = 0xFFFFFFFF
        #    self.huff_end = 0xFFFFFFFF

    def extract(self, f, offset):
        nhuffs = 0
        for mod in self.modules:
            llut = get_struct(f, mod.Offset, HuffmanLUTHeader)
        for imod in range(len(self.modules)):
            mod = self.modules[imod]
            nm = mod.Name.rstrip('\0')
            islast = (imod == len(self.modules)-1)
            if mod.comptype() == COMP_TYPE_HUFFMAN:
                print "Huffman module: %r %08X/%08X" % (nm, mod.huff_start, mod.Size),
                nhuffs += 1
            elif mod.comptype() == COMP_TYPE_LZMA:
	        print "Module: %r %08X/%08X" % (nm, mod.Offset, mod.Size),
            if mod.Offset in [0xFFFFFFFF, 0] or (mod.Size in [0xFFFFFFFF, 0] and mod.comptype() != COMP_TYPE_HUFFMAN):
                print " (skipping)"
            else:
                if mod.comptype() == COMP_TYPE_LZMA:
                    soff = offset + mod.Offset
                    size = mod.Size
                    ext = "lzma"
                elif mod.comptype() == COMP_TYPE_HUFFMAN:
                    soff = llut.DataStart + mod.OffsetLLUTSt2
		    size = mod.Size
		    ext = "huff"
                else:
                    ext = "bin"
                    soff = offset + mod.Offset
                if self.Tag == '$MAN':
                    ext = "mod"
                    moff = soff+0x50
                    if f[moff:moff+5] == '\x5D\x00\x00\x80\x00':
                        lzf = open("%s_mod.lzma" % nm, "wb")
                        lzf.write(f[moff:moff+5])
                        lzf.write(struct.pack("<Q", mod.UncompressedSize))
                        lzf.write(f[moff+5:moff+mod.Size-0x50])
                fname = "%s_mod.%s" % (nm, ext)
                print " => %s" % (fname)
                open(fname, "wb").write(f[soff:soff+size])
        for subtag, soff, subsize in self.updparts:
            fname = "%s_udc.bin" % subtag
            print "Update part: %r %08X/%08X" % (subtag, soff, subsize),
            print " => %s" % (fname)
            open(fname, "wb").write(f[soff:soff+subsize])
            extract_code_mods(subtag, f, soff)

    def pprint(self):
        print "Module Type: %d, Subtype: %d" % (self.ModuleType, self.ModuleSubType)
        print "Header Length:       0x%02X (0x%X bytes)" % (self.HeaderLen, self.HeaderLen*4)
        print "Header Version:      %d.%d" % (self.HeaderVersion>>16, self.HeaderVersion&0xFFFF)
        print "Flags:               0x%08X" % (self.Flags),
        print " [%s signed] [%s flag]" % (["production","debug"][(self.Flags>>31)&1], ["production","pre-production"][(self.Flags>>30)&1])
        print "Module Vendor:       0x%04X" % (self.ModuleVendor)
        print "Date:                %08X" % (self.Date)
        print "Total Manifest Size: 0x%02X (0x%X bytes)" % (self.Size, self.Size*4)
        print "Tag:                 %s" % (self.Tag)
        print "Number of modules:   %d" % (self.NumModules)
        print "Version:             %d.%d.%d.%d" % (self.MajorVersion, self.MinorVersion, self.HotfixVersion, self.BuildVersion)
        print "Unknown data 1:      %s" % ([n for n in self.Unknown1])
        print "Key size:            0x%02X (0x%X bytes)" % (self.KeySize, self.KeySize*4)
        print "Scratch size:        0x%02X (0x%X bytes)" % (self.ScratchSize, self.ScratchSize*4)
        print "RSA Public Key:      [skipped]"
        print "RSA Public Exponent: %d" % (self.RsaPubExp)
        print "RSA Signature:       [skipped]"
        pname = self.PartitionName.rstrip('\0')
        if not pname:
            pname = "(none)"
        print "Partition name:      %s" % (pname)
        print "---Modules---"
        for mod in self.modules:
            mod.pprint()
            print
        print "------End-------"


PartTypes = ["Code", "BlockIo", "Nvram", "Generic", "Effs", "Rom"]

PT_CODE    = 0
PT_BLOCKIO = 1
PT_NVRAM   = 2
PT_GENERIC = 3
PT_EFFS    = 4
PT_ROM     = 5

class MeFptEntry(ctypes.LittleEndianStructure):
    _fields_ = [
        ("Name",            char*4),   # 00 partition name
        ("Owner",           char*4),   # 04 partition owner?
        ("Offset",          uint32_t), # 08 from the start of FPT, or 0
        ("Size",            uint32_t), # 0C
        ("TokensOnStart",   uint32_t), # 10
        ("MaxTokens",       uint32_t), # 14
        ("ScratchSectors",  uint32_t), # 18
        ("Flags",           uint32_t), # 1C
    ]
    #def __init__(self, f, offset):
        #self.sig1, self.Owner,  self.Offset, self.Size  = struct.unpack("<4s4sII", f[offset:offset+0x10])
        #self.TokensOnStart, self.MaxTokens, self.ScratchSectors, self.Flags = struct.unpack("<IIII", f[offset+0x10:offset+0x20])

    def ptype(self):
        return self.Flags & 0x7F

    def print_flags(self):
        pt = self.ptype()
        if pt < len(PartTypes):
            stype = "%d (%s)" % (pt, PartTypes[pt])
        else:
            stype = "%d" % pt
        print "    Type:         %s" % stype
        print "    DirectAccess: %d" % ((self.Flags>>7)&1)
        print "    Read:         %d" % ((self.Flags>>8)&1)
        print "    Write:        %d" % ((self.Flags>>9)&1)
        print "    Execute:      %d" % ((self.Flags>>10)&1)
        print "    Logical:      %d" % ((self.Flags>>11)&1)
        print "    WOPDisable:   %d" % ((self.Flags>>12)&1)
        print "    ExclBlockUse: %d" % ((self.Flags>>13)&1)


    def pprint(self):
        print "Partition:      %r" % self.Name
        print "Owner:          %s" % [repr(self.Owner), "(none)"][self.Owner == '\xFF\xFF\xFF\xFF']
        print "Offset/size:    %08X/%08X" % (self.Offset, self.Size)
        print "TokensOnStart:  %08X" % (self.TokensOnStart)
        print "MaxTokens:      %08X" % (self.MaxTokens)
        print "ScratchSectors: %08X" % (self.ScratchSectors)
        print "Flags:              %04X" % self.Flags
        self.print_flags()

class MeFptTable:
    def __init__(self, f, offset):
        hdr = f[offset:offset+0x30]
        if hdr[0x10:0x14] == '$FPT':
            base = offset + 0x10
        elif hdr[0:4] == '$FPT':
            base = offset
        else:
            raise Exception("FPT format not recognized")
        num_entries = DwordAt(f, base+4)
        self.BCDVer, self.FPTEntryType, self.HeaderLen, self.Checksum = struct.unpack("<BBBB", f[base+8:base+12])
        self.FlashCycleLifetime, self.FlashCycleLimit, self.UMASize   = struct.unpack("<HHI", f[base+12:base+20])
        self.Flags = struct.unpack("<I", f[base+20:base+24])[0]
        offset = base + 0x20
        self.parts = []
        for i in range(num_entries):
            part = get_struct(f, offset, MeFptEntry) #MeFptEntry(f, offset)
            offset += 0x20
            self.parts.append(part)

    def extract(self, f, offset):
        for ipart in range(len(self.parts)):
            part = self.parts[ipart]
            print "Partition:      %r %08X/%08X" % (part.Name, part.Offset, part.Size),
            islast = (ipart == len(self.parts)-1)
            if part.Offset in [0xFFFFFFFF, 0] or (part.Size in [0xFFFFFFFF, 0] and not islast):
                print " (skipping)"
            else:
                nm = part.Name.rstrip('\0')
                soff  = offset + part.Offset
                fname = "%s_part.bin" % (part.Name)
                fname = replace_bad(fname, map(chr, range(128, 256) + range(0, 32)))
                print " => %s" % (fname)
                open(fname, "wb").write(f[soff:soff+part.Size])
                if part.ptype() == PT_CODE:
                    extract_code_mods(nm, f, soff)

    def pprint(self):
        print "===ME Flash Partition Table==="
        print "NumEntries: %d" % len(self.parts)
        print "Version:    %d.%d" % (self.BCDVer >> 4, self.BCDVer & 0xF)
        print "EntryType:  %02X"  % (self.FPTEntryType)
        print "HeaderLen:  %02X"  % (self.HeaderLen)
        print "Checksum:   %02X"  % (self.Checksum)
        print "FlashCycleLifetime: %d" % (self.FlashCycleLifetime)
        print "FlashCycleLimit:    %d" % (self.FlashCycleLimit)
        print "UMASize:    %d" % self.UMASize
        print "Flags:      %08X" % self.Flags
        print "    EFFS present:   %d" % (self.Flags&1)
        print "    ME Layout Type: %d" % ((self.Flags>>1)&0xFF)
        print "---Partitions---"
        for part in self.parts:
            part.pprint()
            print
        print "------End-------"


region_names = ["Descriptor", "BIOS", "ME", "GbE", "PDR", "Region 5", "Region 6", "Region 7" ]
region_fnames =["Flash Descriptor", "BIOS Region", "ME Region", "GbE Region", "PDR Region", "Region 5", "Region 6", "Region 7" ]

def print_flreg(val, name):
    print "%s region:" % name
    lim  = ((val >> 4) & 0xFFF000)
    base = (val << 12) & 0xFFF000
    if lim == 0 and base == 0xFFF000:
        print "  [unused]"
        return None
    lim |= 0xFFF
    print "  %08X - %08X (0x%08X bytes)" % (base, lim, lim - base + 1)
    return (base, lim)

def parse_descr(f, offset, extract):
    mapoff = offset
    if f[offset+0x10:offset+0x14] == "\x5A\xA5\xF0\x0F":
      mapoff = offset + 0x10
    elif f[offset:offset+0x4] != "\x5A\xA5\xF0\x0F":
      return -1
    print "Flash Descriptor found at %08X" % offset
    FLMAP0, FLMAP1, FLMAP2 = struct.unpack("<III", f[mapoff+4:mapoff+0x10])
    nr   = (FLMAP0 >> 24) & 0x7
    frba = (FLMAP0 >> 12) & 0xFF0
    nc   = (FLMAP0 >>  8) & 0x3
    fcba = (FLMAP0 <<  4) & 0xFF0
    print "Number of regions: %d (besides Descriptor)" % nr
    print "Number of components: %d" % (nc+1)
    print "FRBA: 0x%08X" % frba
    print "FCBA: 0x%08X" % fcba
    me_offset = -1
    for i in range(nr+1):
        FLREG = struct.unpack("<I", f[offset + frba + i*4:offset + frba + i*4 + 4])[0]
        r = print_flreg(FLREG, region_names[i])
        if r:
            base, lim = r
            if i == 2:
                me_offset = offset + base
            if extract:
                fname = "%s.bin" % region_fnames[i]
                print " => %s" % (fname)
                open(fname, "wb").write(f[offset + base:offset + base + lim + 1])
    return me_offset

class AcManifestHeader(ctypes.LittleEndianStructure):
    _fields_ = [
        ("ModuleType",     uint16_t), # 00
        ("ModuleSubType",  uint16_t), # 02
        ("HeaderLen",      uint32_t), # 04 in dwords
        ("HeaderVersion",  uint32_t), # 08
        ("ChipsetID",      uint16_t), # 0C
        ("Flags",          uint16_t), # 0E 0x80000000 = Debug
        ("ModuleVendor",   uint32_t), # 10
        ("Date",           uint32_t), # 14 BCD yyyy.mm.dd
        ("Size",           uint32_t), # 18 in dwords
        ("Reserved1",      uint32_t), # 1C
        ("CodeControl",    uint32_t), # 20
        ("ErrorEntryPoint",uint32_t), # 24
        ("GDTLimit",       uint32_t), # 28
        ("GDTBasePtr",     uint32_t), # 2C
        ("SegSel",         uint32_t), # 30
        ("EntryPoint",     uint32_t), # 34
        ("Reserved2",      uint32_t*16), # 38
        ("KeySize",        uint32_t), # 78
        ("ScratchSize",    uint32_t), # 7C
        ("RsaPubKey",      uint32_t*64), # 80
        ("RsaPubExp",      uint32_t),    # 180
        ("RsaSig",         uint32_t*64), # 184
        # 284
    ]

    def pprint(self):
        print "Module Type: %d, Subtype: %d" % (self.ModuleType, self.ModuleSubType)
        print "Header Length:       0x%02X (0x%X bytes)" % (self.HeaderLen, self.HeaderLen*4)
        print "Header Version:      %d.%d" % (self.HeaderVersion>>16, self.HeaderVersion&0xFFFF)
        print "ChipsetID:           0x%04X" % (self.ChipsetID)
        print "Flags:               0x%04X" % (self.Flags),
        print " [%s signed] [%s flag]" % (["production","debug"][(self.Flags>>15)&1], ["production","pre-production"][(self.Flags>>14)&1])
        print "Module Vendor:       0x%04X" % (self.ModuleVendor)
        print "Date:                %08X" % (self.Date)
        print "Total Module Size:   0x%02X (0x%X bytes)" % (self.Size, self.Size*4)
        print "Reserved1:           0x%08X" % (self.Reserved1)
        print "CodeControl:         0x%08X" % (self.CodeControl)
        print "ErrorEntryPoint:     0x%08X" % (self.ErrorEntryPoint)
        print "GDTLimit:            0x%08X" % (self.GDTLimit)
        print "GDTBasePtr:          0x%08X" % (self.GDTBasePtr)
        print "SegSel:              0x%04X" % (self.SegSel)
        print "EntryPoint:          0x%08X" % (self.EntryPoint)
        print "Key size:            0x%02X (0x%X bytes)" % (self.KeySize, self.KeySize*4)
        print "Scratch size:        0x%02X (0x%X bytes)" % (self.ScratchSize, self.ScratchSize*4)
        print "RSA Public Key:      [skipped]"
        print "RSA Public Exponent: %d" % (self.RsaPubExp)
        print "RSA Signature:       [skipped]"
        print "------End-------"

print "Intel ME dumper/extractor v0.1"
if len(sys.argv) < 2:
    print "Usage: dump_me.py MeImage.bin [-x] [offset]"
    print "   -x: extract ME partitions and code modules"
else:
    fname = sys.argv[1]
    extract = False
    offset = 0
    for opt in sys.argv[2:]:
        if opt == "-x":
            extract = True
        else:
            offset = int(opt, 16)
    f = open(fname, "rb").read()
    off2 = parse_descr(f, offset, extract)
    if off2 != -1:
        offset = off2
        try:
           os.mkdir("ME Region")
        except:
           pass
        os.chdir("ME Region")
    if f[offset:offset+8] == "\x04\x00\x00\x00\xA1\x00\x00\x00":
        while True:
            manif = get_struct(f, offset, MeManifestHeader)
            manif.parse_mods(f, offset)
            manif.pprint()
            if extract:
                manif.extract(f, offset)
            if manif.partition_end:
                offset += manif.partition_end
                print "Next partition: +%08X (%08X)" % (manif.partition_end, offset)
            else:
                break
            if f[offset:offset+8] != "\x04\x00\x00\x00\xA1\x00\x00\x00":
                break
    elif f[offset:offset+8] == "\x02\x00\x00\x00\xA1\x00\x00\x00":
        manif = get_struct(f, offset, AcManifestHeader)
        manif.pprint()
    else:
        fpt = MeFptTable(f, offset)
        fpt.pprint()
        if extract:
            fpt.extract(f, offset)
    if off2 != -1:
        os.chdir("..")
