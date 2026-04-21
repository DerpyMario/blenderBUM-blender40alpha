using System;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEditor;
using UnityEditor.AssetImporters;
using BumImporter.Formats;

namespace BumImporter
{
    /// <summary>
    /// Converts a parsed <see cref="BumFile"/> into Unity assets
    /// (Mesh, Material, SkinnedMeshRenderer hierarchy, AnimationClip)
    /// and registers them with the asset import context.
    /// </summary>
    public static class BumModelBuilder
    {
        // =====================================================================
        // Entry point
        // =====================================================================

        public static void Build(
            BumFile                       bum,
            string                        name,
            AssetImportContext            ctx,
            Dictionary<string, Texture2D> textures)
        {
            foreach (BumModel model in bum.Models)
                BuildModel(bum, model, name, ctx, textures);
        }

        // =====================================================================
        // Model
        // =====================================================================

        private static void BuildModel(
            BumFile                       bum,
            BumModel                      model,
            string                        name,
            AssetImportContext            ctx,
            Dictionary<string, Texture2D> textures)
        {
            // Root prefab
            var root = new GameObject(name);
            ctx.SetMainObject(root);

            // Armature container (applies global scale)
            var armatureGO = new GameObject("Armature");
            armatureGO.transform.SetParent(root.transform, false);
            armatureGO.transform.localScale = Vector3.one * bum.Scale;

            // Build bone hierarchy
            Transform[] boneTransforms = BuildBones(model.Nodes, armatureGO.transform, out Matrix4x4[] worldMatrices);

            // Build materials
            List<Material> matList = BuildMaterials(model, textures, ctx);

            // Build meshes
            if (bum.Version >= 200)
            {
                foreach (BumMeshData meshData in model.Meshes)
                    BuildMeshV2(meshData, model, matList, boneTransforms, worldMatrices, root, ctx);
            }
            else
            {
                foreach (BumPart part in model.Parts)
                    BuildMeshV1(part, model, matList, boneTransforms, worldMatrices, root, ctx);
            }

            // Build animations
            foreach (BumMotion motion in bum.Animations)
                BuildAnimation(motion, boneTransforms, model.Nodes, armatureGO, ctx);
        }

        // =====================================================================
        // Bone hierarchy
        // =====================================================================

        private static Transform[] BuildBones(
            List<BumNode>    nodes,
            Transform        armatureRoot,
            out Matrix4x4[]  worldMatrices)
        {
            int count     = nodes.Count;
            var bones     = new Transform[count];
            worldMatrices = new Matrix4x4[count];

            for (int i = 0; i < count; i++)
            {
                BumNode node = nodes[i];
                var boneGO   = new GameObject(string.IsNullOrEmpty(node.Name) ? $"Bone_{i}" : node.Name);
                bones[i]     = boneGO.transform;

                Vector3    pos = ConvertPosition(node.Translation);
                Quaternion rot = ConvertRotation(node.Rotation);
                Vector3    scl = new Vector3(node.Scale[0], node.Scale[1], node.Scale[2]);

                boneGO.transform.localPosition = pos;
                boneGO.transform.localRotation = rot;
                boneGO.transform.localScale    = scl;

                if (node.ParentIndex >= 0 && node.ParentIndex < count)
                    boneGO.transform.SetParent(bones[node.ParentIndex], false);
                else
                    boneGO.transform.SetParent(armatureRoot, false);
            }

            for (int i = 0; i < count; i++)
                worldMatrices[i] = bones[i].localToWorldMatrix;

            return bones;
        }

        // =====================================================================
        // Materials
        // =====================================================================

        private static List<Material> BuildMaterials(
            BumModel                      model,
            Dictionary<string, Texture2D> textures,
            AssetImportContext            ctx)
        {
            var settingsMap = new Dictionary<string, BumMaterialSettings>();
            foreach (BumMaterialSettings ms in model.MaterialSettings)
                settingsMap[ms.MaterialName] = ms;

            var result = new List<Material>();

            foreach (BumMaterial bumMat in model.Materials)
            {
                Material mat = CreateMaterial(bumMat, settingsMap, textures);
                if (!string.IsNullOrEmpty(bumMat.Name))
                    mat.name = bumMat.Name;
                ctx.AddObjectToAsset("Mat_" + mat.name, mat);
                result.Add(mat);
            }

            return result;
        }

        private static Material CreateMaterial(
            BumMaterial                              bumMat,
            Dictionary<string, BumMaterialSettings> settingsMap,
            Dictionary<string, Texture2D>           textures)
        {
            var mat = new Material(Shader.Find("Standard") ?? Shader.Find("Sprites/Default"));

            Texture2D albedo = null;

            // From SAMP samplers
            foreach (BumSampler s in bumMat.Samplers)
            {
                if (textures.TryGetValue(StripExtension(s.TextureName), out Texture2D tx))
                {
                    albedo = tx;
                    break;
                }
            }

            // From LAYE layers
            if (albedo == null && bumMat.Layers.Count > 0)
                textures.TryGetValue(StripExtension(bumMat.Layers[0].TextureName), out albedo);

            // From merged settings
            if (albedo == null && settingsMap.TryGetValue(bumMat.Name ?? string.Empty, out BumMaterialSettings ms))
            {
                foreach (BumSampler s in ms.Samplers)
                {
                    if (textures.TryGetValue(StripExtension(s.TextureName), out Texture2D tx))
                    {
                        albedo = tx;
                        break;
                    }
                }
            }

            if (albedo != null)
                mat.SetTexture("_MainTex", albedo);

            return mat;
        }

        private static string StripExtension(string name)
        {
            if (string.IsNullOrEmpty(name)) return name ?? string.Empty;
            int dot = name.LastIndexOf('.');
            return dot >= 0 ? name.Substring(0, dot) : name;
        }

        // =====================================================================
        // V2 Mesh
        // =====================================================================

        private static void BuildMeshV2(
            BumMeshData    meshData,
            BumModel       model,
            List<Material> materials,
            Transform[]    boneTransforms,
            Matrix4x4[]    worldMatrices,
            GameObject     root,
            AssetImportContext ctx)
        {
            if (meshData.Vertices == null || meshData.Faces == null) return;

            BumVertexData vd = meshData.Vertices;
            if ((vd.Positions?.Length ?? 0) == 0) return;

            bool isSkinned = vd.BoneIDs != null && vd.Weights != null && meshData.BoneList != null;

            Mesh mesh = BuildUnityMesh(vd, meshData.Faces, meshData.Name ?? "Mesh");

            if (isSkinned)
            {
                int[] globalBoneIDs = ResolveV2BoneIDs(meshData.BoneList, model.DeformBoneList);
                mesh.bindposes   = ComputeBindPoses(boneTransforms, worldMatrices);
                mesh.boneWeights = BuildBoneWeightsV2(vd, globalBoneIDs);
            }

            ctx.AddObjectToAsset("Mesh_" + (meshData.Name ?? "Mesh"), mesh);

            string goName = string.IsNullOrEmpty(meshData.Name) ? "Mesh" : meshData.Name;
            var go        = new GameObject(goName);
            go.transform.SetParent(root.transform, false);

            if (isSkinned)
            {
                var smr        = go.AddComponent<SkinnedMeshRenderer>();
                smr.sharedMesh = mesh;
                smr.bones      = boneTransforms;
                if (meshData.MaterialIndex >= 0 && meshData.MaterialIndex < materials.Count)
                    smr.sharedMaterial = materials[meshData.MaterialIndex];
                if (meshData.ParentBoneIndex >= 0 && meshData.ParentBoneIndex < boneTransforms.Length)
                    smr.rootBone = boneTransforms[meshData.ParentBoneIndex];
            }
            else
            {
                go.AddComponent<MeshFilter>().sharedMesh = mesh;
                var mr = go.AddComponent<MeshRenderer>();
                if (meshData.MaterialIndex >= 0 && meshData.MaterialIndex < materials.Count)
                    mr.sharedMaterial = materials[meshData.MaterialIndex];
            }
        }

        // =====================================================================
        // V1 Mesh
        // =====================================================================

        private static void BuildMeshV1(
            BumPart        part,
            BumModel       model,
            List<Material> materials,
            Transform[]    boneTransforms,
            Matrix4x4[]    worldMatrices,
            GameObject     root,
            AssetImportContext ctx)
        {
            if (part.VertexBuffers.Count == 0) return;

            var allPositions = new List<Vector3>();
            var allNormals   = new List<Vector3>();
            var allUV0       = new List<Vector2>();
            var allColors    = new List<Color32>();
            var allWeights   = new List<BoneWeight>();
            bool hasSkin     = false;
            bool hasNormals  = false;
            bool hasUV       = false;
            bool hasColors   = false;

            var vbBaseIndex = new Dictionary<int, int>();

            foreach (BumSubMesh sm in part.SubMeshes)
            {
                int vbIdx = sm.VertexBufferIndex;
                if (vbBaseIndex.ContainsKey(vbIdx)) continue;
                if (vbIdx < 0 || vbIdx >= part.VertexBuffers.Count) continue;

                BumVertexData vd = part.VertexBuffers[vbIdx];
                vbBaseIndex[vbIdx] = allPositions.Count;

                int vc = vd.Positions?.Length ?? 0;
                for (int i = 0; i < vc; i++)
                {
                    allPositions.Add(vd.Positions != null ? ConvertPosition(vd.Positions[i]) : Vector3.zero);

                    if (vd.Normals != null) { hasNormals = true;  allNormals.Add(ConvertNormal(vd.Normals[i])); }
                    else allNormals.Add(Vector3.up);

                    if (vd.UV0 != null) { hasUV = true; allUV0.Add(new Vector2(vd.UV0[i][0], 1f - vd.UV0[i][1])); }
                    else allUV0.Add(Vector2.zero);

                    if (vd.Colors != null) { hasColors = true; allColors.Add(new Color32(vd.Colors[i][0], vd.Colors[i][1], vd.Colors[i][2], vd.Colors[i][3])); }
                    else allColors.Add(Color.white);

                    if (vd.Weights != null && vd.BoneIDs != null)
                    {
                        hasSkin = true;
                        allWeights.Add(BuildBoneWeightV1(vd.Weights[i], vd.BoneIDs[i]));
                    }
                    else allWeights.Add(new BoneWeight());
                }
            }

            if (allPositions.Count == 0) return;

            int subMeshCount = part.SubMeshes.Count;
            var subMeshTris  = new List<int[]>();
            for (int s = 0; s < subMeshCount; s++)
            {
                BumSubMesh sm = part.SubMeshes[s];
                int baseIdx   = vbBaseIndex.ContainsKey(sm.VertexBufferIndex) ? vbBaseIndex[sm.VertexBufferIndex] : 0;
                var tris      = new List<int>();
                if (sm.Faces != null)
                {
                    foreach (int[] face in sm.Faces)
                    {
                        tris.Add(baseIdx + face[0]);
                        tris.Add(baseIdx + face[2]); // swap [1] and [2] for handedness
                        tris.Add(baseIdx + face[1]);
                    }
                }
                subMeshTris.Add(tris.ToArray());
            }

            string meshName = string.IsNullOrEmpty(part.Name) ? "Mesh" : part.Name;
            var mesh        = new Mesh { name = meshName };
            if (allPositions.Count > 65535) mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;

            mesh.SetVertices(allPositions);
            if (hasNormals) mesh.SetNormals(allNormals);
            if (hasUV)      mesh.SetUVs(0, allUV0);
            if (hasColors)  mesh.SetColors(allColors);

            mesh.subMeshCount = subMeshCount;
            for (int s = 0; s < subMeshCount; s++)
                mesh.SetTriangles(subMeshTris[s], s);

            mesh.RecalculateBounds();
            if (!hasNormals) mesh.RecalculateNormals();

            if (hasSkin)
            {
                mesh.bindposes   = ComputeBindPoses(boneTransforms, worldMatrices);
                mesh.boneWeights = allWeights.ToArray();
            }

            ctx.AddObjectToAsset("Mesh_" + part.Name, mesh);

            var go = new GameObject(meshName);
            go.transform.SetParent(root.transform, false);

            if (hasSkin)
            {
                var smr        = go.AddComponent<SkinnedMeshRenderer>();
                smr.sharedMesh = mesh;
                smr.bones      = boneTransforms;
                smr.materials  = BuildMaterialArray(part.SubMeshes, materials);
            }
            else
            {
                go.AddComponent<MeshFilter>().sharedMesh = mesh;
                go.AddComponent<MeshRenderer>().materials = BuildMaterialArray(part.SubMeshes, materials);
            }
        }

        private static Material[] BuildMaterialArray(List<BumSubMesh> subMeshes, List<Material> materials)
        {
            var result = new Material[subMeshes.Count];
            for (int i = 0; i < subMeshes.Count; i++)
            {
                int mi = subMeshes[i].MaterialIndex;
                result[i] = (mi >= 0 && mi < materials.Count) ? materials[mi] : null;
            }
            return result;
        }

        // =====================================================================
        // Shared mesh builder from BumVertexData
        // =====================================================================

        private static Mesh BuildUnityMesh(BumVertexData vd, int[][] faces, string meshName)
        {
            int vc   = vd.Positions?.Length ?? 0;
            var mesh = new Mesh { name = meshName };
            if (vc > 65535) mesh.indexFormat = UnityEngine.Rendering.IndexFormat.UInt32;

            var positions = new Vector3[vc];
            for (int i = 0; i < vc; i++)
                positions[i] = vd.Positions != null ? ConvertPosition(vd.Positions[i]) : Vector3.zero;
            mesh.vertices = positions;

            if (vd.Normals != null)
            {
                var normals = new Vector3[vc];
                for (int i = 0; i < vc; i++) normals[i] = ConvertNormal(vd.Normals[i]);
                mesh.normals = normals;
            }

            if (vd.UV0 != null)
            {
                var uv0 = new Vector2[vc];
                for (int i = 0; i < vc; i++) uv0[i] = new Vector2(vd.UV0[i][0], 1f - vd.UV0[i][1]);
                mesh.uv = uv0;
            }

            if (vd.UV1 != null)
            {
                var uv1 = new Vector2[vc];
                for (int i = 0; i < vc; i++) uv1[i] = new Vector2(vd.UV1[i][0], 1f - vd.UV1[i][1]);
                mesh.uv2 = uv1;
            }

            if (vd.Colors != null)
            {
                var colors = new Color32[vc];
                for (int i = 0; i < vc; i++)
                    colors[i] = new Color32(vd.Colors[i][0], vd.Colors[i][1], vd.Colors[i][2], vd.Colors[i][3]);
                mesh.colors32 = colors;
            }

            // Triangles: swap indices [1] and [2] to flip winding for left-handed coords
            var tris = new int[faces.Length * 3];
            for (int i = 0; i < faces.Length; i++)
            {
                tris[i * 3 + 0] = faces[i][0];
                tris[i * 3 + 1] = faces[i][2];
                tris[i * 3 + 2] = faces[i][1];
            }
            mesh.triangles = tris;

            mesh.RecalculateBounds();
            if (vd.Normals == null) mesh.RecalculateNormals();

            return mesh;
        }

        // =====================================================================
        // Skinning helpers
        // =====================================================================

        private static Matrix4x4[] ComputeBindPoses(Transform[] bones, Matrix4x4[] worldMatrices)
        {
            var bindPoses = new Matrix4x4[bones.Length];
            for (int i = 0; i < bones.Length; i++)
                bindPoses[i] = worldMatrices[i].inverse;
            return bindPoses;
        }

        private static int[] ResolveV2BoneIDs(int[] sbidBoneIDs, int[] deformBoneList)
        {
            if (sbidBoneIDs == null) return Array.Empty<int>();
            var result = new int[sbidBoneIDs.Length];
            for (int i = 0; i < sbidBoneIDs.Length; i++)
            {
                int sbid = sbidBoneIDs[i];
                result[i] = deformBoneList != null && sbid < deformBoneList.Length
                    ? deformBoneList[sbid]
                    : sbid;
            }
            return result;
        }

        private static BoneWeight[] BuildBoneWeightsV2(BumVertexData vd, int[] globalBoneIDs)
        {
            int vc = vd.Positions.Length;
            var bw = new BoneWeight[vc];
            for (int vi = 0; vi < vc; vi++)
                bw[vi] = SelectTopFourWeights(vd.BoneIDs[vi], vd.Weights[vi], globalBoneIDs);
            return bw;
        }

        private static BoneWeight BuildBoneWeightV1(byte[] weights, byte[] boneIDs)
        {
            return SelectTopFourWeights(boneIDs, weights, null);
        }

        private static BoneWeight SelectTopFourWeights(byte[] boneIDBytes, byte[] weightBytes, int[] globalBoneIDs)
        {
            int count = Math.Min(boneIDBytes?.Length ?? 0, weightBytes?.Length ?? 0);
            var pairs = new List<(int boneIdx, float weight)>(count);

            for (int i = 0; i < count; i++)
            {
                float w = weightBytes[i] / 255f;
                if (w <= 0f) continue;
                int globalIdx = boneIDBytes[i];
                if (globalBoneIDs != null && globalIdx < globalBoneIDs.Length)
                    globalIdx = globalBoneIDs[globalIdx];
                pairs.Add((globalIdx, w));
            }

            pairs.Sort((a, b) => b.weight.CompareTo(a.weight));
            while (pairs.Count > 4) pairs.RemoveAt(pairs.Count - 1);

            float sum = 0f;
            foreach (var p in pairs) sum += p.weight;
            if (sum > 0f)
                for (int i = 0; i < pairs.Count; i++)
                    pairs[i] = (pairs[i].boneIdx, pairs[i].weight / sum);

            BoneWeight bw = new BoneWeight();
            if (pairs.Count > 0) { bw.boneIndex0 = pairs[0].boneIdx; bw.weight0 = pairs[0].weight; }
            if (pairs.Count > 1) { bw.boneIndex1 = pairs[1].boneIdx; bw.weight1 = pairs[1].weight; }
            if (pairs.Count > 2) { bw.boneIndex2 = pairs[2].boneIdx; bw.weight2 = pairs[2].weight; }
            if (pairs.Count > 3) { bw.boneIndex3 = pairs[3].boneIdx; bw.weight3 = pairs[3].weight; }
            return bw;
        }

        // =====================================================================
        // Animation
        // =====================================================================

        private static void BuildAnimation(
            BumMotion      motion,
            Transform[]    boneTransforms,
            List<BumNode>  nodes,
            GameObject     armatureGO,
            AssetImportContext ctx)
        {
            var clip = new AnimationClip { name = motion.Name ?? "Anim" };
            clip.frameRate = 30f;

            // Build bone-name → relative path mapping
            var pathMap = new Dictionary<string, string>(StringComparer.Ordinal);
            for (int i = 0; i < nodes.Count; i++)
            {
                BumNode node = nodes[i];
                if (string.IsNullOrEmpty(node.Name)) continue;
                pathMap[node.Name] = BuildBonePath(i, nodes);
            }

            foreach (BumCurve curve in motion.Curves)
            {
                if (string.IsNullOrEmpty(curve.BoneName)) continue;
                if (curve.Keyframes == null || curve.Keyframes.Length == 0) continue;
                if (!pathMap.TryGetValue(curve.BoneName, out string path)) continue;

                switch (curve.CurveType)
                {
                    case BumCurveType.Location:
                        AddLocationCurves(clip, path, curve);
                        break;
                    case BumCurveType.Rotation:
                        AddRotationCurves(clip, path, curve);
                        break;
                    case BumCurveType.Scale:
                        AddScaleCurves(clip, path, curve);
                        break;
                }
            }

            clip.EnsureQuaternionContinuity();
            ctx.AddObjectToAsset("Anim_" + (motion.Name ?? "Anim"), clip);
        }

        private static string BuildBonePath(int nodeIndex, List<BumNode> nodes)
        {
            var chain = new List<string>();
            int cur   = nodeIndex;
            while (cur >= 0 && cur < nodes.Count)
            {
                chain.Add(nodes[cur].Name ?? $"Bone_{cur}");
                cur = nodes[cur].ParentIndex;
            }
            chain.Reverse();
            return string.Join("/", chain);
        }

        private static void AddLocationCurves(AnimationClip clip, string path, BumCurve curve)
        {
            var cx = new AnimationCurve();
            var cy = new AnimationCurve();
            var cz = new AnimationCurve();

            foreach (BumKeyframe kf in curve.Keyframes)
            {
                if (kf.Values.Length < 3) continue;
                float t = kf.Frame / clip.frameRate;
                // Source: right-handed Y-up → Unity: (-x, y, z)
                cx.AddKey(t, -kf.Values[0]);
                cy.AddKey(t,  kf.Values[1]);
                cz.AddKey(t,  kf.Values[2]);
            }

            SetTangents(cx, curve.Interpolation);
            SetTangents(cy, curve.Interpolation);
            SetTangents(cz, curve.Interpolation);

            clip.SetCurve(path, typeof(Transform), "localPosition.x", cx);
            clip.SetCurve(path, typeof(Transform), "localPosition.y", cy);
            clip.SetCurve(path, typeof(Transform), "localPosition.z", cz);
        }

        private static void AddRotationCurves(AnimationClip clip, string path, BumCurve curve)
        {
            var cx = new AnimationCurve();
            var cy = new AnimationCurve();
            var cz = new AnimationCurve();
            var cw = new AnimationCurve();

            foreach (BumKeyframe kf in curve.Keyframes)
            {
                if (kf.Values.Length < 4) continue;
                float t = kf.Frame / clip.frameRate;
                // Source: (x,y,z,w) right-handed → Unity: (x,-y,-z,w)
                cx.AddKey(t,  kf.Values[0]);
                cy.AddKey(t, -kf.Values[1]);
                cz.AddKey(t, -kf.Values[2]);
                cw.AddKey(t,  kf.Values[3]);
            }

            SetTangents(cx, curve.Interpolation);
            SetTangents(cy, curve.Interpolation);
            SetTangents(cz, curve.Interpolation);
            SetTangents(cw, curve.Interpolation);

            clip.SetCurve(path, typeof(Transform), "localRotation.x", cx);
            clip.SetCurve(path, typeof(Transform), "localRotation.y", cy);
            clip.SetCurve(path, typeof(Transform), "localRotation.z", cz);
            clip.SetCurve(path, typeof(Transform), "localRotation.w", cw);
        }

        private static void AddScaleCurves(AnimationClip clip, string path, BumCurve curve)
        {
            var cx = new AnimationCurve();
            var cy = new AnimationCurve();
            var cz = new AnimationCurve();

            foreach (BumKeyframe kf in curve.Keyframes)
            {
                if (kf.Values.Length < 3) continue;
                float t = kf.Frame / clip.frameRate;
                cx.AddKey(t, kf.Values[0]);
                cy.AddKey(t, kf.Values[1]);
                cz.AddKey(t, kf.Values[2]);
            }

            SetTangents(cx, curve.Interpolation);
            SetTangents(cy, curve.Interpolation);
            SetTangents(cz, curve.Interpolation);

            clip.SetCurve(path, typeof(Transform), "localScale.x", cx);
            clip.SetCurve(path, typeof(Transform), "localScale.y", cy);
            clip.SetCurve(path, typeof(Transform), "localScale.z", cz);
        }

        private static void SetTangents(AnimationCurve c, int interpolation)
        {
            if (interpolation == 0) // constant
            {
                for (int i = 0; i < c.length; i++)
                    AnimationUtility.SetKeyframeMode(c, i, AnimationUtility.KeyframeMode.Constant);
            }
            // linear / auto: leave Unity's default (cubic spline)
        }

        // =====================================================================
        // Coordinate conversion helpers
        // =====================================================================

        // Source: right-handed Y-up → Unity: left-handed Y-up (flip X)
        private static Vector3 ConvertPosition(float[] v) => new Vector3(-v[0], v[1], v[2]);
        private static Vector3 ConvertNormal(float[] v)   => new Vector3(-v[0], v[1], v[2]);

        // Source quaternion (x,y,z,w) right-handed → Unity: (x,-y,-z,w)
        private static Quaternion ConvertRotation(float[] q) => new Quaternion(q[0], -q[1], -q[2], q[3]);
    }
}
