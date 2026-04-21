using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEditor;
using UnityEditor.AssetImporters;
using BumImporter.Formats;

namespace BumImporter
{
    [ScriptedImporter(1, "bum")]
    public class BumImporter : ScriptedImporter
    {
        public override void OnImportAsset(AssetImportContext ctx)
        {
            try
            {
                byte[]  data    = File.ReadAllBytes(ctx.assetPath);
                BumFile bum     = BumFile.Read(data);
                string  name    = Path.GetFileNameWithoutExtension(ctx.assetPath);

                Dictionary<string, Texture2D> textures = LoadSiblingTextures(ctx.assetPath);

                BumModelBuilder.Build(bum, name, ctx, textures);
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[BumImporter] Failed to import '{ctx.assetPath}': {ex.Message}\n{ex.StackTrace}");
            }
        }

        private static Dictionary<string, Texture2D> LoadSiblingTextures(string assetPath)
        {
            var textures = new Dictionary<string, Texture2D>(StringComparer.OrdinalIgnoreCase);

            string dir = Path.GetDirectoryName(assetPath);
            if (string.IsNullOrEmpty(dir)) return textures;

            foreach (string file in Directory.GetFiles(dir))
            {
                string ext = Path.GetExtension(file).ToLowerInvariant();
                if (ext != ".png" && ext != ".dds") continue;

                string texName = Path.GetFileNameWithoutExtension(file);

                // Try via AssetDatabase first (already-imported textures)
                string assetRelPath = "Assets" + file.Substring(Application.dataPath.Length);
                Texture2D tex = AssetDatabase.LoadAssetAtPath<Texture2D>(assetRelPath);

                if (tex == null)
                {
                    byte[] imgBytes = File.ReadAllBytes(file);
                    tex = new Texture2D(2, 2);
                    if (!tex.LoadImage(imgBytes))
                        tex = null;
                }

                if (tex != null)
                    textures[texName] = tex;
            }

            return textures;
        }
    }
}
