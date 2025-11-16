from .utils.PyBinaryReader.binary_reader import *
from .utils import pyaes

class LZS(BrStruct):
    def __init__(self, window_size=4096, lookahead_size=18):
        self.window_size = window_size
        self.lookahead_size = lookahead_size
        self.files = []
        
    def __br_read__(self, br: BinaryReader):
        # determine compression
        sizeAndType = br.read_uint32()
        decompressed_size = sizeAndType & 0x3FFFFFFF
        compression_type = sizeAndType >> 30
        
        extrabyte = br.read_uint8()
        if compression_type == 0 and extrabyte > 0 and br.size() < decompressed_size:
            # LZSS0 compression
            decompressedData = self.decompress_lzss0(br.buffer()[4:], decompressed_size)
            br = BinaryReader(decompressedData)
        elif compression_type == 3 and br.size() < decompressed_size:
            # LZ4 compression
            decompressedData = self.decompress_lz4(br.buffer()[4:], decompressed_size)
            br = BinaryReader(decompressedData)
        else:
            br.seek(0)
        
        
        self.fileCount = br.read_uint16()
        self.files = br.read_struct(fileEntry, self.fileCount)
    
    def decompress_lzss0(self, data: bytes, decompressed_size: int = None) -> bytes:
        N = self.window_size          # 4096
        F = self.lookahead_size       # 18
        THRESHOLD = 2
        N_MASK = N - 1                # Cache the mask for bitwise AND

        src = memoryview(data)
        src_len = len(src)
        src_pos = 0
        if decompressed_size is None:
            decompressed_size = src_len * 4  # Estimate size if not provided
        dst = bytearray(decompressed_size)

        text_buf = bytearray(N)
        r = N - F

        flags = 0
        out_pos = 0

        while src_pos < src_len and out_pos < decompressed_size:
            flags >>= 1
            if not (flags & 0x100):
                if src_pos >= src_len:
                    break
                flags = src[src_pos] | 0xFF00
                src_pos += 1

            if flags & 1:
                # literal
                if src_pos >= src_len:
                    break
                c = src[src_pos]
                src_pos += 1

                dst[out_pos] = c
                text_buf[r] = c
                r = (r + 1) & N_MASK
                out_pos += 1

            else:
                if src_pos + 1 >= src_len:
                    break
                i = src[src_pos]
                j = src[src_pos + 1]
                src_pos += 2

                offset = i | ((j & 0xF0) << 4)
                length = (j & 0x0F) + THRESHOLD + 1

                # Clamp to decompressed size
                copy_len = min(length, decompressed_size - out_pos)
                
                # Fast path for simple RLE pattern (offset == r means repeating last byte)
                # This is rare but when it happens, it's faster
                if copy_len > 0:
                    # Copy bytes from sliding window
                    for k in range(copy_len):
                        c = text_buf[(offset + k) & N_MASK]
                        dst[out_pos] = c
                        text_buf[r] = c
                        r = (r + 1) & N_MASK
                        out_pos += 1

        return bytes(dst[:out_pos])


    def decompress_lz4(self, data: bytes, dec_length: int) -> bytearray:
        src = 0
        # Pre-allocate to avoid repeated reallocation
        dst = bytearray(dec_length)
        dst_pos = 0
        data_len = len(data)
        
        def extend_len():
            nonlocal src
            total = 0
            while src < data_len:
                b = data[src]
                src += 1
                total += b
                if b != 0xFF:
                    break
            else:
                raise EOFError("Unexpected end while extending length")
            return total
        
        while dst_pos < dec_length:
            if src >= data_len:
                raise EOFError("Unexpected end of input while reading token")
            token = data[src]
            src += 1
            lz4LiteralsToRead = token >> 4
            lz4DecodedBytesToCopy = token & 0x0F
            
            if lz4LiteralsToRead == 0x0F:
                lz4LiteralsToRead += extend_len()
            
            # copy literals
            if lz4LiteralsToRead:
                if src + lz4LiteralsToRead > data_len:
                    raise EOFError("Not enough literal bytes")
                dst[dst_pos:dst_pos+lz4LiteralsToRead] = data[src:src+lz4LiteralsToRead]
                dst_pos += lz4LiteralsToRead
                src += lz4LiteralsToRead
            
            if dst_pos >= dec_length:
                break
            
            if src + 2 > data_len:
                raise EOFError("Not enough bytes for offset")
            lz4LookbackOffset = data[src] | (data[src+1] << 8)
            src += 2
            
            if lz4DecodedBytesToCopy == 0x0F:
                lz4DecodedBytesToCopy += extend_len()
            
            match_length = lz4DecodedBytesToCopy + 4
            starting_position = dst_pos - lz4LookbackOffset
            
            if starting_position < 0:
                raise IndexError(f"Invalid lookback: offset={lz4LookbackOffset}, dst_pos={dst_pos}")
            
            # Handle overlapping copies efficiently
            # When offset < match_length, we're copying data we just wrote (RLE pattern)
            if lz4LookbackOffset == 1:
                # Special case: repeat single byte (common RLE pattern)
                byte_val = dst[starting_position]
                dst[dst_pos:dst_pos+match_length] = bytes([byte_val]) * match_length
                dst_pos += match_length
            elif lz4LookbackOffset < match_length:
                # Overlapping copy: copy pattern repeatedly
                for i in range(match_length):
                    dst[dst_pos] = dst[starting_position + i]
                    dst_pos += 1
            else:
                # Non-overlapping: can copy entire block at once
                dst[dst_pos:dst_pos+match_length] = dst[starting_position:starting_position + match_length]
                dst_pos += match_length
        
        return dst

    def dump_data(self, path: str):
        for file in self.files:
            outpath = f"{path}/{file.name}"
            with open(outpath, 'wb') as outFile:
                outFile.write(file.data)
    
    
    
class fileEntry(BrStruct):
    def __init__(self):
        self.name = ""
        self.type = 0
        self.data = b""
    def __br_read__(self, br: BinaryReader):
        self.type = br.read_uint16()
        offset = br.read_uint32()
        size = br.read_uint32()
        index = br.read_uint32()
        self.name = br.read_str()
        
        pos = br.pos()
        br.seek(offset)
        self.data = br.read_bytes(size)
        br.seek(pos)
        
        br.read_bytes(64 - (14 + len(self.name) + 1))  # +1 for null terminator


entryTypes = {
    0: "Unk",
    1: "Model",
    4: "Texture",
}

def lzsReader(path) -> LZS:
    with open(path, 'rb') as f:
        br = BinaryReader(f.read())
        lzs = br.read_struct(LZS)
        return lzs

KEYS = {
    "Archive": {
        "key": bytes.fromhex("1122345567889aaf5eb4cc884ab6dd00"),
        "iv": bytes.fromhex("00010203f0f5e1a2f151c69a390adefb")
    },
    "Pak": {
        "key": b"(V%((kWBL32drZvn",
        "iv": b"eW/x/.rNrji3dCxL"
    }
}

def decrypt_data(encrypted: bytes, key_type: str) -> bytes:
    key = KEYS[key_type]["key"]
    iv = KEYS[key_type]["iv"]

    # Trim last 32 bytes if needed (C# code does this for Pak files)
    if key_type == "Pak":
        encrypted = encrypted[:-32]

    decrypter = pyaes.Decrypter(pyaes.AESModeOfOperationCBC(key, iv=iv))
    decrypted = decrypter.feed(encrypted)
    decrypted += decrypter.feed()  # flush and remove PKCS7 padding
    return decrypted


def lzaReader(path: str) -> LZS:
    with open(path, 'rb') as f:
        enc_data = f.read()
        dec_data = decrypt_data(enc_data, "Archive")
        
    br = BinaryReader(dec_data)
    lzs = br.read_struct(LZS)
    return lzs


if __name__ == "__main__":
    from time import perf_counter
    start_time = perf_counter()
    
    lzs = lzsReader(r"G:\Dev\LZSTool\fr04_model.lzs")
    
    #for file in lzs.files:
    #    print(f"File: {file.name}, Type: {file.type}, Size: {len(file.data)}")
    

    #lza_path = r"G:\Dev\LZSTool\un01002_top.lza"
    
    '''KEY_ARCHIVE = bytes.fromhex("1122345567889aaf5eb4cc884ab6dd00")
    IV_ARCHIVE  = bytes.fromhex("00010203f0f5e1a2f151c69a390adefb")
    
    with open(lza_path, 'rb') as f:
        enc_data = f.read()
        dec_data = decrypt_data(enc_data, "Archive")
        
    br = BinaryReader(dec_data)
    lzs = br.read_struct(LZS)'''
    
    print(f"Decryption, decompression and reading took {perf_counter() - start_time:.4f} seconds")
    
    for file in lzs.files:
        print(f"File: {file.name}, Type: {file.type}, Size: {len(file.data)}")