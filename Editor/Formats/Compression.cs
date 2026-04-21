using System;

namespace BumImporter.Formats
{
    /// <summary>
    /// LZSS0 and LZ4 decompression, ported from the Python addon.
    /// </summary>
    public static class Compression
    {
        // LZSS0 constants
        private const int N         = 4096;
        private const int F         = 18;
        private const int Threshold = 2;
        private const int N_Mask    = N - 1;

        /// <summary>
        /// Decompresses LZSS0-encoded data.
        /// </summary>
        /// <param name="data">Compressed payload (starting after the 4-byte LZS header).</param>
        /// <param name="decompressedSize">Expected output size in bytes.</param>
        public static byte[] DecompressLzss0(byte[] data, int decompressedSize)
        {
            byte[] dst     = new byte[decompressedSize];
            byte[] textBuf = new byte[N];

            int srcPos = 0;
            int srcLen = data.Length;
            int outPos = 0;
            int r      = N - F;
            int flags  = 0;

            while (srcPos < srcLen && outPos < decompressedSize)
            {
                flags >>= 1;
                if ((flags & 0x100) == 0)
                {
                    if (srcPos >= srcLen) break;
                    flags = data[srcPos++] | 0xFF00;
                }

                if ((flags & 1) != 0)
                {
                    // Literal byte
                    if (srcPos >= srcLen) break;
                    byte c = data[srcPos++];
                    dst[outPos++] = c;
                    textBuf[r]    = c;
                    r             = (r + 1) & N_Mask;
                }
                else
                {
                    // Back-reference
                    if (srcPos + 1 >= srcLen) break;
                    int i = data[srcPos];
                    int j = data[srcPos + 1];
                    srcPos += 2;

                    int offset = i | ((j & 0xF0) << 4);
                    int length = (j & 0x0F) + Threshold + 1;

                    int copyLen = Math.Min(length, decompressedSize - outPos);
                    for (int k = 0; k < copyLen; k++)
                    {
                        byte c = textBuf[(offset + k) & N_Mask];
                        dst[outPos++] = c;
                        textBuf[r]    = c;
                        r             = (r + 1) & N_Mask;
                    }
                }
            }

            return dst;
        }

        /// <summary>
        /// Decompresses LZ4-encoded data (block format, no frame header).
        /// </summary>
        /// <param name="data">Compressed payload (starting after the 4-byte LZS header).</param>
        /// <param name="decompressedSize">Expected output size in bytes.</param>
        public static byte[] DecompressLz4(byte[] data, int decompressedSize)
        {
            byte[] dst     = new byte[decompressedSize];
            int    src     = 0;
            int    dstPos  = 0;
            int    dataLen = data.Length;

            while (dstPos < decompressedSize)
            {
                if (src >= dataLen)
                    throw new InvalidOperationException("LZ4: unexpected end of input while reading token.");

                int token             = data[src++];
                int literalsToRead    = token >> 4;
                int decodedBytesToCopy = token & 0x0F;

                // Extend literals count
                if (literalsToRead == 0x0F)
                {
                    int extra;
                    do
                    {
                        if (src >= dataLen)
                            throw new InvalidOperationException("LZ4: unexpected end while extending literal count.");
                        extra = data[src++];
                        literalsToRead += extra;
                    }
                    while (extra == 0xFF);
                }

                // Copy literals
                if (literalsToRead > 0)
                {
                    if (src + literalsToRead > dataLen)
                        throw new InvalidOperationException("LZ4: not enough literal bytes.");
                    Array.Copy(data, src, dst, dstPos, literalsToRead);
                    dstPos += literalsToRead;
                    src    += literalsToRead;
                }

                if (dstPos >= decompressedSize) break;

                // Read lookback offset (little-endian uint16)
                if (src + 2 > dataLen)
                    throw new InvalidOperationException("LZ4: not enough bytes for offset.");
                int lookback = data[src] | (data[src + 1] << 8);
                src += 2;

                // Extend match length
                if (decodedBytesToCopy == 0x0F)
                {
                    int extra;
                    do
                    {
                        if (src >= dataLen)
                            throw new InvalidOperationException("LZ4: unexpected end while extending match length.");
                        extra = data[src++];
                        decodedBytesToCopy += extra;
                    }
                    while (extra == 0xFF);
                }

                int matchLength   = decodedBytesToCopy + 4;
                int startPosition = dstPos - lookback;
                if (startPosition < 0)
                    throw new InvalidOperationException($"LZ4: invalid lookback offset={lookback}, dstPos={dstPos}.");

                // Handle overlapping copy
                if (lookback == 1)
                {
                    byte b = dst[startPosition];
                    for (int k = 0; k < matchLength; k++)
                        dst[dstPos++] = b;
                }
                else if (lookback < matchLength)
                {
                    for (int k = 0; k < matchLength; k++)
                        dst[dstPos++] = dst[startPosition + k];
                }
                else
                {
                    Array.Copy(dst, startPosition, dst, dstPos, matchLength);
                    dstPos += matchLength;
                }
            }

            return dst;
        }
    }
}
