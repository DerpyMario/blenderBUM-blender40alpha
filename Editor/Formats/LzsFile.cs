using System;
using System.Collections.Generic;
using System.Text;

namespace BumImporter.Formats
{
    public enum LzsEntryType
    {
        Unknown  = 0,
        Model    = 1,
        Texture  = 4,
        Texture2 = 30,
        Texture3 = 31,
    }

    /// <summary>
    /// A single file entry extracted from an LZS/LZA archive.
    /// </summary>
    public class LzsEntry
    {
        public ushort Type;
        public string Name;
        public byte[] Data;

        public bool IsTexture =>
            Type == (ushort)LzsEntryType.Texture  ||
            Type == (ushort)LzsEntryType.Texture2 ||
            Type == (ushort)LzsEntryType.Texture3;

        public bool IsModel => Type == (ushort)LzsEntryType.Model;
    }

    /// <summary>
    /// Parsed LZS (or decrypted LZA) archive.
    /// </summary>
    public class LzsFile
    {
        public List<LzsEntry> Entries { get; } = new List<LzsEntry>();

        /// <summary>Parses an LZS file from raw bytes.</summary>
        public static LzsFile Read(byte[] rawData)
        {
            if (rawData.Length < 6)
                throw new InvalidOperationException("LZS data too short.");

            uint sizeAndType      = BitConverter.ToUInt32(rawData, 0);
            int  decompressedSize = (int)(sizeAndType & 0x3FFFFFFF);
            int  compressionType  = (int)(sizeAndType >> 30);
            byte extraByte        = rawData[4];

            // Payload starts at byte 4
            byte[] payload = new byte[rawData.Length - 4];
            Array.Copy(rawData, 4, payload, 0, payload.Length);

            byte[] workingData;
            if (compressionType == 0 && extraByte > 0 && rawData.Length < decompressedSize)
            {
                workingData = Compression.DecompressLzss0(payload, decompressedSize);
            }
            else if (compressionType == 3 && rawData.Length < decompressedSize)
            {
                workingData = Compression.DecompressLz4(payload, decompressedSize);
            }
            else
            {
                // Not compressed – use raw bytes
                workingData = rawData;
            }

            return ParseEntries(workingData);
        }

        /// <summary>Decrypts an LZA file then parses it as LZS.</summary>
        public static LzsFile ReadLza(byte[] encryptedData)
        {
            byte[] decrypted = Encryption.DecryptArchive(encryptedData);
            return Read(decrypted);
        }

        private static LzsFile ParseEntries(byte[] data)
        {
            var br  = new BumBinaryReader(data);
            var lzs = new LzsFile();

            int fileCount = br.ReadUInt16();

            for (int i = 0; i < fileCount; i++)
            {
                int entryStart = br.Position;

                ushort type   = br.ReadUInt16();  // 2 bytes
                uint   offset = br.ReadUInt32();  // 4 bytes
                uint   size   = br.ReadUInt32();  // 4 bytes
                br.ReadUInt32();                  // index (4 bytes, unused)

                // Name: remaining 50 bytes of the 64-byte entry
                string name = br.ReadFixedString(50);

                // Ensure we consumed exactly 64 bytes for this entry
                br.Seek(entryStart + 64);

                // Read entry data from its absolute offset
                byte[] entryData = new byte[size];
                Array.Copy(data, (int)offset, entryData, 0, (int)size);

                lzs.Entries.Add(new LzsEntry
                {
                    Type = type,
                    Name = name,
                    Data = entryData,
                });
            }

            return lzs;
        }
    }
}
