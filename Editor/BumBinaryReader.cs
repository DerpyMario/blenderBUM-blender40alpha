using System;
using System.Text;

namespace BumImporter
{
    /// <summary>
    /// Little-endian binary reader backed by a byte array.
    /// </summary>
    public class BumBinaryReader
    {
        private readonly byte[] _data;
        private int _pos;

        public BumBinaryReader(byte[] data)
        {
            _data = data ?? throw new ArgumentNullException(nameof(data));
            _pos = 0;
        }

        public int Position
        {
            get => _pos;
            set
            {
                if (value < 0 || value > _data.Length)
                    throw new ArgumentOutOfRangeException(nameof(value));
                _pos = value;
            }
        }

        public int Length => _data.Length;
        public bool Eof => _pos >= _data.Length;

        public void Seek(int position)
        {
            if (position < 0 || position > _data.Length)
                throw new ArgumentOutOfRangeException(nameof(position));
            _pos = position;
        }

        public void Skip(int count)
        {
            _pos += count;
        }

        public byte ReadByte()
        {
            return _data[_pos++];
        }

        public sbyte ReadSByte()
        {
            return (sbyte)_data[_pos++];
        }

        public ushort ReadUInt16()
        {
            ushort v = (ushort)(_data[_pos] | (_data[_pos + 1] << 8));
            _pos += 2;
            return v;
        }

        public short ReadInt16()
        {
            return (short)ReadUInt16();
        }

        public uint ReadUInt32()
        {
            uint v = (uint)(_data[_pos]
                | (_data[_pos + 1] << 8)
                | (_data[_pos + 2] << 16)
                | (_data[_pos + 3] << 24));
            _pos += 4;
            return v;
        }

        public int ReadInt32()
        {
            return (int)ReadUInt32();
        }

        public float ReadFloat()
        {
            float v = BitConverter.ToSingle(_data, _pos);
            _pos += 4;
            return v;
        }

        public byte[] ReadBytes(int count)
        {
            byte[] result = new byte[count];
            Array.Copy(_data, _pos, result, 0, count);
            _pos += count;
            return result;
        }

        public float[] ReadFloats(int count)
        {
            float[] result = new float[count];
            for (int i = 0; i < count; i++)
                result[i] = ReadFloat();
            return result;
        }

        public ushort[] ReadUInt16s(int count)
        {
            ushort[] result = new ushort[count];
            for (int i = 0; i < count; i++)
                result[i] = ReadUInt16();
            return result;
        }

        public uint[] ReadUInt32s(int count)
        {
            uint[] result = new uint[count];
            for (int i = 0; i < count; i++)
                result[i] = ReadUInt32();
            return result;
        }

        /// <summary>Reads a null-terminated UTF-8 string.</summary>
        public string ReadCString()
        {
            int start = _pos;
            while (_pos < _data.Length && _data[_pos] != 0)
                _pos++;
            string s = Encoding.UTF8.GetString(_data, start, _pos - start);
            if (_pos < _data.Length)
                _pos++; // consume null terminator
            return s;
        }

        /// <summary>Reads exactly <paramref name="len"/> bytes and trims at the first null.</summary>
        public string ReadFixedString(int len)
        {
            byte[] buf = ReadBytes(len);
            int nullIdx = Array.IndexOf(buf, (byte)0);
            int count = nullIdx >= 0 ? nullIdx : len;
            return Encoding.UTF8.GetString(buf, 0, count);
        }

        /// <summary>
        /// Decodes an IEEE 754 half-precision float (16-bit) to a 32-bit float.
        /// Handles zero, subnormals, infinity, and NaN.
        /// </summary>
        public float ReadFloat16()
        {
            ushort h = ReadUInt16();
            return HalfToFloat(h);
        }

        public static float HalfToFloat(ushort h)
        {
            int sign = (h >> 15) & 0x1;
            int exp  = (h >> 10) & 0x1F;
            int mant = h & 0x3FF;

            uint bits;
            if (exp == 0)
            {
                if (mant == 0)
                {
                    // ±zero
                    bits = (uint)(sign << 31);
                }
                else
                {
                    // Subnormal: normalize
                    exp = 1;
                    while ((mant & 0x400) == 0)
                    {
                        mant <<= 1;
                        exp--;
                    }
                    mant &= 0x3FF;
                    int exp32 = exp - 15 + 127;
                    bits = (uint)((sign << 31) | (exp32 << 23) | (mant << 13));
                }
            }
            else if (exp == 0x1F)
            {
                // Infinity or NaN
                bits = (uint)((sign << 31) | (0xFF << 23) | (mant << 13));
            }
            else
            {
                int exp32 = exp - 15 + 127;
                bits = (uint)((sign << 31) | (exp32 << 23) | (mant << 13));
            }

            return BitConverter.ToSingle(BitConverter.GetBytes(bits), 0);
        }

        /// <summary>
        /// Returns a new reader over the next <paramref name="size"/> bytes and advances position.
        /// </summary>
        public BumBinaryReader SliceFromCurrent(int size)
        {
            byte[] slice = new byte[size];
            Array.Copy(_data, _pos, slice, 0, size);
            _pos += size;
            return new BumBinaryReader(slice);
        }

        /// <summary>Returns the underlying byte array.</summary>
        public byte[] GetBuffer() => _data;
    }
}
