using System;
using System.Security.Cryptography;

namespace BumImporter.Formats
{
    /// <summary>
    /// AES-CBC decryption for LZA archives.
    /// </summary>
    public static class Encryption
    {
        // Archive key/IV (hex strings from Python source)
        private static readonly byte[] ArchiveKey = HexToBytes("1122345567889aaf5eb4cc884ab6dd00");
        private static readonly byte[] ArchiveIV  = HexToBytes("00010203f0f5e1a2f151c69a390adefb");

        /// <summary>
        /// Decrypts an LZA file's AES-CBC payload and returns the decrypted bytes.
        /// </summary>
        public static byte[] DecryptArchive(byte[] encrypted)
        {
            using (Aes aes = Aes.Create())
            {
                aes.Key     = ArchiveKey;
                aes.IV      = ArchiveIV;
                aes.Mode    = CipherMode.CBC;
                aes.Padding = PaddingMode.PKCS7;

                using (ICryptoTransform decryptor = aes.CreateDecryptor())
                {
                    return decryptor.TransformFinalBlock(encrypted, 0, encrypted.Length);
                }
            }
        }

        private static byte[] HexToBytes(string hex)
        {
            if (hex.Length % 2 != 0)
                throw new ArgumentException("Hex string must have an even number of characters.");
            byte[] result = new byte[hex.Length / 2];
            for (int i = 0; i < result.Length; i++)
                result[i] = Convert.ToByte(hex.Substring(i * 2, 2), 16);
            return result;
        }
    }
}
