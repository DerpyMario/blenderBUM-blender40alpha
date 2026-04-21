using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEditor;
using UnityEditor.AssetImporters;
using BumImporter.Formats;

namespace BumImporter
{
    [ScriptedImporter(1, new[] { "lzs", "lza" })]
    public class LzsImporter : ScriptedImporter
    {
        public override void OnImportAsset(AssetImportContext ctx)
        {
            try
            {
                byte[]  rawData = File.ReadAllBytes(ctx.assetPath);
                string  ext     = Path.GetExtension(ctx.assetPath).ToLowerInvariant();
                string  name    = Path.GetFileNameWithoutExtension(ctx.assetPath);

                LzsFile lzs = ext == ".lza"
                    ? LzsFile.ReadLza(rawData)
                    : LzsFile.Read(rawData);

                // Extract textures from the archive first
                Dictionary<string, Texture2D> textures = ExtractTextures(lzs, ctx);

                // Then import each model entry
                foreach (LzsEntry entry in lzs.Entries)
                {
                    if (!entry.IsModel) continue;

                    try
                    {
                        string modelName = Path.GetFileNameWithoutExtension(entry.Name);
                        if (string.IsNullOrEmpty(modelName)) modelName = name;

                        BumFile bum = BumFile.Read(entry.Data);
                        BumModelBuilder.Build(bum, modelName, ctx, textures);
                    }
                    catch (Exception ex)
                    {
                        Debug.LogWarning($"[LzsImporter] Failed to import model '{entry.Name}' from '{ctx.assetPath}': {ex.Message}");
                    }
                }
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[LzsImporter] Failed to import '{ctx.assetPath}': {ex.Message}\n{ex.StackTrace}");
            }
        }

        private static Dictionary<string, Texture2D> ExtractTextures(LzsFile lzs, AssetImportContext ctx)
        {
            var textures = new Dictionary<string, Texture2D>(StringComparer.OrdinalIgnoreCase);

            foreach (LzsEntry entry in lzs.Entries)
            {
                if (!entry.IsTexture) continue;

                string texName = Path.GetFileNameWithoutExtension(entry.Name);
                string ext     = Path.GetExtension(entry.Name).ToLowerInvariant();

                Texture2D tex = null;

                // LoadImage handles PNG and JPEG; DDS and other compressed formats
                // are not natively supported by Texture2D.LoadImage, but we attempt it
                // for all types since it works for common web-format images.
                tex = new Texture2D(2, 2);
                if (!tex.LoadImage(entry.Data))
                {
                    UnityEngine.Object.DestroyImmediate(tex);
                    tex = null;
                }

                if (tex != null)
                {
                    tex.name = texName;
                    ctx.AddObjectToAsset("Tex_" + texName, tex);
                    textures[texName] = tex;
                }
            }

            return textures;
        }
    }
}
