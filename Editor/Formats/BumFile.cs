using System;
using System.Collections.Generic;
using System.Text;

namespace BumImporter.Formats
{
    // =========================================================================
    // Enumerations
    // =========================================================================

    public enum BumCurveType
    {
        Location,
        Rotation,
        Scale,
        Visibility,
        UvTransform,
        Unknown,
    }

    // =========================================================================
    // Vertex data
    // =========================================================================

    public class BumVertexData
    {
        public float[][] Positions; // [vertexCount][3]
        public float[][] Normals;   // [vertexCount][3]  (nullable)
        public float[][] UV0;       // [vertexCount][2]  (nullable)
        public float[][] UV1;       // [vertexCount][2]  (nullable)
        public byte[][]  Colors;    // [vertexCount][4]  RGBA (nullable)
        public byte[][]  BoneIDs;   // [vertexCount][4 or 8]  (nullable)
        public byte[][]  Weights;   // [vertexCount][4 or 8]  (nullable)
    }

    // =========================================================================
    // Material data
    // =========================================================================

    public class BumLayer
    {
        public string  TextureName;
        public float[] Coordinates = { 0f, 0f, 1f, 1f };
        public uint    MapType;
    }

    public class BumSampler
    {
        public string SamplerName;
        public string TextureName;
    }

    public class BumMaterial
    {
        public string            Name;
        public string            ShaderName;
        public List<BumLayer>    Layers   = new List<BumLayer>();
        public List<BumSampler>  Samplers = new List<BumSampler>();
    }

    public class BumMaterialSettings
    {
        public string            MaterialName;
        public string            Path;
        public List<BumSampler>  Samplers = new List<BumSampler>();
    }

    // =========================================================================
    // Mesh / Part data
    // =========================================================================

    public class BumSubMesh
    {
        public int    MaterialIndex;
        public int    VertexBufferIndex;
        public int[]  BoneIDs;   // global bone indices (v1 BLES)
        public int[][] Faces;    // [triangleCount][3]
    }

    public class BumPart
    {
        public string              Name;
        public List<BumSubMesh>    SubMeshes    = new List<BumSubMesh>();
        public List<BumVertexData> VertexBuffers = new List<BumVertexData>();
        public int                 ParentNodeIndex = -1;
    }

    public class BumMeshData
    {
        public string        Name;
        public int           MaterialIndex;
        public int           ParentBoneIndex = -1;
        public int[]         BoneList;      // local→global bone index table (SBID)
        public BumVertexData Vertices;
        public int[][]       Faces;         // [triangleCount][3]
    }

    // =========================================================================
    // Node / Bone data
    // =========================================================================

    public class BumMeshRef
    {
        public uint Unk;
        public uint MeshIndex;
    }

    public class BumBoneList
    {
        public int   BoneCount;
        public int[] BoneIDs;
    }

    public class BumNode
    {
        public string      Name;
        public int         ParentIndex = -1;
        public float[]     Translation = { 0f, 0f, 0f };
        public float[]     Rotation    = { 0f, 0f, 0f, 1f };
        public float[]     Scale       = { 1f, 1f, 1f };
        public float[]     Pivot       = { 0f, 0f, 0f };
        public float[]     Matrix16;           // bind matrix (SKDB), row-major
        public uint        Flags;
        public BumMeshRef  MeshInfo;
        public BumBoneList BoneList;
    }

    // =========================================================================
    // Animation data
    // =========================================================================

    public class BumKeyframe
    {
        public float   Frame;
        public float[] Values;
    }

    public class BumCurve
    {
        public string       BoneName;
        public string       MaterialName;
        public BumCurveType CurveType;
        public int          Interpolation; // 0=constant 1=linear
        public BumKeyframe[] Keyframes;
    }

    public class BumMotion
    {
        public string         Name;
        public float          Length;
        public List<BumCurve> Curves = new List<BumCurve>();
    }

    // =========================================================================
    // Model
    // =========================================================================

    public class BumModel
    {
        public List<BumNode>             Nodes            = new List<BumNode>();
        public List<BumPart>             Parts            = new List<BumPart>();     // v1
        public List<BumMeshData>         Meshes           = new List<BumMeshData>(); // v2
        public List<BumMaterial>         Materials        = new List<BumMaterial>();
        public List<BumMaterialSettings> MaterialSettings = new List<BumMaterialSettings>();
        public int[]                     DeformBoneList;
    }

    // =========================================================================
    // Top-level BUM file
    // =========================================================================

    public class BumFile
    {
        public int             Version    = 100;
        public float           Scale      = 1.0f;
        public List<BumModel>  Models     = new List<BumModel>();
        public List<BumMotion> Animations = new List<BumMotion>();

        /// <summary>Parses a BUM file from raw bytes.</summary>
        public static BumFile Read(byte[] data)
        {
            var br  = new BumBinaryReader(data);
            var bum = new BumFile();

            string magic    = ReadFourCC(br);
            uint   fileSize = br.ReadUInt32();

            if (magic != ".BUM" && magic != "BUM2")
                throw new InvalidOperationException($"Not a valid BUM file (magic='{magic}').");

            if (magic == "BUM2")
            {
                BumBinaryReader verData = ReadChunk(br, out string verType);
                if (verType == "VER\0" || verType == "VER " || verType == "VER")
                    ReadVer(verData, bum);
                else
                    ReadVer(verData, bum); // try anyway – first chunk after BUM2 is always VER
            }

            while (!br.Eof)
            {
                BumBinaryReader chunkBr = ReadChunk(br, out string chunkType);
                switch (chunkType)
                {
                    case "MODL":
                        bum.Models.Add(ReadModl(chunkBr, bum.Version));
                        break;
                    case "ANIM":
                        ReadAnim(chunkBr, bum.Version, bum.Animations);
                        break;
                    case "ANI3":
                        bum.Animations.Add(ReadMotion(chunkBr, bum.Version, isAni3: true));
                        break;
                }
            }

            return bum;
        }

        // =====================================================================
        // Chunk helpers
        // =====================================================================

        private static string ReadFourCC(BumBinaryReader br)
        {
            return Encoding.ASCII.GetString(br.ReadBytes(4));
        }

        private static BumBinaryReader ReadChunk(BumBinaryReader br, out string type)
        {
            type = ReadFourCC(br);
            uint size = br.ReadUInt32();
            int dataSize = (int)(size - 8);
            if (dataSize < 0) dataSize = 0;
            return br.SliceFromCurrent(dataSize);
        }

        // =====================================================================
        // VER
        // =====================================================================

        private static void ReadVer(BumBinaryReader br, BumFile bum)
        {
            bum.Version = (int)br.ReadUInt32();
            br.ReadUInt32(); // unk1
            br.ReadUInt32(); // totalVertexCount
            bum.Scale   = br.ReadFloat();
        }

        // =====================================================================
        // MODL
        // =====================================================================

        private static BumModel ReadModl(BumBinaryReader br, int version)
        {
            var model = new BumModel();

            while (!br.Eof)
            {
                BumBinaryReader c = ReadChunk(br, out string t);
                switch (t)
                {
                    case "BBOX":
                    case "AABB":
                        break; // bounding box – not needed
                    case "NODE":
                        model.Nodes.Add(ReadNode(c, version));
                        break;
                    case "PART":
                        model.Parts.Add(ReadPart(c, version));
                        break;
                    case "MESH":
                        model.Meshes.Add(ReadMesh(c, version));
                        break;
                    case "MATR":
                        model.Materials.Add(ReadMatr(c, version));
                        break;
                    case "MATS":
                        model.MaterialSettings.Add(ReadMats(c, version));
                        break;
                    case "DBPL":
                        model.DeformBoneList = ReadDbpl(c);
                        break;
                }
            }

            // V1: remap mesh bone IDs through parent node bone list
            if (version < 200)
                RemapV1BoneIDs(model);

            return model;
        }

        // =====================================================================
        // NODE
        // =====================================================================

        private static BumNode ReadNode(BumBinaryReader br, int version)
        {
            var node = new BumNode();

            while (!br.Eof)
            {
                BumBinaryReader c = ReadChunk(br, out string t);
                switch (t)
                {
                    case "NAME":
                        node.Name = c.ReadCString();
                        break;
                    case "BBOX":
                    case "AABB":
                        break;
                    case "NDAT":
                        node.ParentIndex = c.ReadInt32();
                        c.ReadInt32();            // childCount
                        node.Translation = c.ReadFloats(3);
                        node.Scale       = c.ReadFloats(3);
                        node.Rotation    = c.ReadFloats(4);
                        c.ReadFloats(3);          // pivot
                        break;
                    case "SKDB":
                        node.Matrix16 = c.ReadFloats(16);
                        break;
                    case "NSTA":
                        node.Flags = c.ReadUInt32();
                        break;
                    case "PARE":
                        node.ParentIndex = c.ReadInt32();
                        break;
                    case "TRNS":
                        node.Translation = c.ReadFloats(3);
                        break;
                    case "ROTQ":
                        node.Rotation = c.ReadFloats(4);
                        break;
                    case "SCAL":
                        node.Scale = c.ReadFloats(3);
                        break;
                    case "BLEB":
                        node.BoneList = ReadBleb(c);
                        break;
                    case "BLEO":
                        if (node.BoneList != null)
                            c.Skip(node.BoneList.BoneCount * 64); // boneCount × 4×4 float matrix
                        break;
                    case "VISI":
                        c.ReadUInt32();
                        break;
                    case "PIVO":
                        node.Pivot = c.ReadFloats(3);
                        break;
                    case "DRWP":
                        node.MeshInfo = new BumMeshRef
                        {
                            Unk       = c.ReadUInt32(),
                            MeshIndex = c.ReadUInt32(),
                        };
                        break;
                }
            }

            return node;
        }

        private static BumBoneList ReadBleb(BumBinaryReader br)
        {
            var bl = new BumBoneList();
            bl.BoneCount = (int)br.ReadUInt32();
            bl.BoneIDs   = new int[bl.BoneCount];
            for (int i = 0; i < bl.BoneCount; i++)
                bl.BoneIDs[i] = br.ReadUInt16();
            return bl;
        }

        // =====================================================================
        // PART (v1)
        // =====================================================================

        private static BumPart ReadPart(BumBinaryReader br, int version)
        {
            var part = new BumPart();
            bool isSkinned = false;

            while (!br.Eof)
            {
                BumBinaryReader c = ReadChunk(br, out string t);
                switch (t)
                {
                    case "NAME":
                        part.Name = c.ReadCString();
                        break;
                    case "BBOX":
                        break;
                    case "MESH":
                        var sm = ReadSubMesh(c);
                        if (sm.BoneIDs != null) isSkinned = true;
                        part.SubMeshes.Add(sm);
                        break;
                    case "ARAY":
                        part.VertexBuffers.Add(ReadAray(c, isSkinned));
                        break;
                }
            }

            return part;
        }

        // =====================================================================
        // MESH sub-chunk (v1, inside PART)
        // =====================================================================

        private static BumSubMesh ReadSubMesh(BumBinaryReader br)
        {
            var sm = new BumSubMesh { VertexBufferIndex = 0 };

            while (!br.Eof)
            {
                BumBinaryReader c = ReadChunk(br, out string t);
                switch (t)
                {
                    case "BBOX":
                        break;
                    case "SMAT":
                        sm.MaterialIndex = (int)c.ReadUInt32();
                        break;
                    case "BLES":
                    {
                        int count  = (int)c.ReadUInt32();
                        sm.BoneIDs = new int[count];
                        for (int i = 0; i < count; i++)
                            sm.BoneIDs[i] = (int)c.ReadUInt32();
                        break;
                    }
                    case "DRWA":
                        ReadDrwaV1(c, sm);
                        break;
                }
            }

            return sm;
        }

        private static void ReadDrwaV1(BumBinaryReader br, BumSubMesh sm)
        {
            br.ReadByte();                       // faceFlag
            sm.VertexBufferIndex = br.ReadByte(); // vertexBufferIndex
            int indexCount = br.ReadUInt16();
            sm.Faces = ReadFaceIndices(br, indexCount);
        }

        private static int[][] ReadFaceIndices(BumBinaryReader br, int indexCount)
        {
            int triCount = indexCount / 3;
            int[][] faces = new int[triCount][];
            for (int i = 0; i < triCount; i++)
            {
                faces[i] = new int[3];
                faces[i][0] = br.ReadUInt16();
                faces[i][1] = br.ReadUInt16();
                faces[i][2] = br.ReadUInt16();
            }
            return faces;
        }

        // =====================================================================
        // MESH (v2, top-level in MODL)
        // =====================================================================

        private static BumMeshData ReadMesh(BumBinaryReader br, int version)
        {
            var mesh = new BumMeshData();
            int[] sbidBoneIDs = null;

            while (!br.Eof)
            {
                BumBinaryReader c = ReadChunk(br, out string t);
                switch (t)
                {
                    case "NAME":
                        mesh.Name = c.ReadCString();
                        break;
                    case "MESP":
                        mesh.ParentBoneIndex = (int)c.ReadUInt32();
                        mesh.MaterialIndex   = (int)c.ReadUInt32();
                        break;
                    case "SMAT":
                        mesh.MaterialIndex = (int)c.ReadUInt32();
                        break;
                    case "SBID":
                    {
                        int count  = c.ReadUInt16();
                        sbidBoneIDs = new int[count];
                        for (int i = 0; i < count; i++)
                            sbidBoneIDs[i] = c.ReadUInt16();
                        break;
                    }
                    case "VERT":
                        mesh.Vertices = ReadVert(c, version);
                        break;
                    case "DRWA":
                        mesh.Faces = ReadDrwaV2(c);
                        break;
                    case "AABB":
                        break;
                }
            }

            mesh.BoneList = sbidBoneIDs;
            return mesh;
        }

        private static int[][] ReadDrwaV2(BumBinaryReader br)
        {
            br.ReadUInt32(); // faceFlag
            int indexCount = (int)br.ReadUInt32();
            return ReadFaceIndices(br, indexCount);
        }

        // =====================================================================
        // ARAY (v1 vertex buffer)
        // =====================================================================

        private static BumVertexData ReadAray(BumBinaryReader br, bool hasWeights)
        {
            byte vf  = br.ReadByte();
            byte vf2 = br.ReadByte();
            int  vc  = br.ReadUInt16();

            bool hasPos     = (vf  & 1)    != 0;
            bool hasNormals = (vf  & 2)    != 0;
            bool hasUV      = (vf  & 8)    != 0;
            bool hasColors  = (vf  & 4)    != 0;
            bool uvFloat32  = (vf2 & 0x20) != 0;

            var vd = new BumVertexData();
            if (hasPos)     vd.Positions = new float[vc][];
            if (hasNormals) vd.Normals   = new float[vc][];
            if (hasUV)      vd.UV0       = new float[vc][];
            if (hasColors)  vd.Colors    = new byte[vc][];
            if (hasWeights)
            {
                vd.Weights = new byte[vc][];
                vd.BoneIDs = new byte[vc][];
            }

            for (int i = 0; i < vc; i++)
            {
                if (hasPos)
                    vd.Positions[i] = new[] { br.ReadFloat(), br.ReadFloat(), br.ReadFloat() };
                if (hasNormals)
                    vd.Normals[i]   = new[] { br.ReadFloat(), br.ReadFloat(), br.ReadFloat() };
                if (hasUV)
                    vd.UV0[i]       = uvFloat32
                        ? new[] { br.ReadFloat(),   br.ReadFloat() }
                        : new[] { br.ReadFloat16(), br.ReadFloat16() };
                if (hasColors)
                    vd.Colors[i]  = br.ReadBytes(4);
                if (hasWeights)
                {
                    vd.Weights[i] = br.ReadBytes(8);
                    vd.BoneIDs[i] = new byte[8]; // zeroed; remapped in RemapV1BoneIDs
                }
            }

            return vd;
        }

        // =====================================================================
        // VERT (v2 vertex buffer)
        // =====================================================================

        private static BumVertexData ReadVert(BumBinaryReader br, int version)
        {
            int    vc         = (int)br.ReadUInt32();
            ushort vertexSize = br.ReadUInt16();
            ushort vf         = br.ReadUInt16();

            bool hasPos      = (vf & 1)   != 0;
            bool hasBoneIDs  = (vf & 64)  != 0;
            bool hasWeights  = (vf & 128) != 0;
            bool hasNormals  = (vf & 2)   != 0;
            bool hasUV0      = (vf & 4)   != 0;
            bool hasUV1      = (vf & 256) != 0;
            bool hasColor    = (vf & 8)   != 0;
            bool hasTangents = (vf & 16)  != 0;
            bool hasBinormals= (vf & 32)  != 0;

            var vd = new BumVertexData();
            if (hasPos)     vd.Positions = new float[vc][];
            if (hasNormals) vd.Normals   = new float[vc][];
            if (hasUV0)     vd.UV0       = new float[vc][];
            if (hasUV1)     vd.UV1       = new float[vc][];
            if (hasColor)   vd.Colors    = new byte[vc][];
            if (hasBoneIDs) vd.BoneIDs   = new byte[vc][];
            if (hasWeights) vd.Weights   = new byte[vc][];

            for (int i = 0; i < vc; i++)
            {
                int vStart = br.Position;

                if (version > 201)
                {
                    // v2.02+ layout: pos, boneIDs, weights, normals, UV0, UV1, color, tangents, binormals
                    if (hasPos)       vd.Positions[i] = new[] { br.ReadFloat(), br.ReadFloat(), br.ReadFloat() };
                    if (hasBoneIDs)   vd.BoneIDs[i]   = br.ReadBytes(4);
                    if (hasWeights)   vd.Weights[i]   = br.ReadBytes(4);
                    if (hasNormals)   vd.Normals[i]   = new[] { br.ReadFloat(), br.ReadFloat(), br.ReadFloat() };
                    if (hasUV0)       vd.UV0[i]       = new[] { br.ReadFloat(), br.ReadFloat() };
                    if (hasUV1)       vd.UV1[i]       = new[] { br.ReadFloat(), br.ReadFloat() };
                    if (hasColor)     vd.Colors[i]    = br.ReadBytes(4);
                    if (hasTangents)  br.Skip(12); // float[3] – not stored
                    if (hasBinormals) br.Skip(12); // float[3] – not stored
                }
                else
                {
                    // v2.00/v2.01 layout: pos, normals, UV0, color, boneIDs+weights, UV1
                    if (hasPos)     vd.Positions[i] = new[] { br.ReadFloat(), br.ReadFloat(), br.ReadFloat() };
                    if (hasNormals) vd.Normals[i]   = new[] { br.ReadFloat(), br.ReadFloat(), br.ReadFloat() };
                    if (hasUV0)     vd.UV0[i]       = new[] { br.ReadFloat(), br.ReadFloat() };
                    if (hasColor)   vd.Colors[i]    = br.ReadBytes(4);
                    if (hasBoneIDs) // flag 64 covers boneIDs+weights together in this version
                    {
                        vd.BoneIDs[i] = br.ReadBytes(4);
                        vd.Weights[i] = br.ReadBytes(4);
                    }
                    if (hasUV1)     vd.UV1[i]       = new[] { br.ReadFloat(), br.ReadFloat() };
                }

                // Advance by vertexSize to consume any unknown/alignment bytes
                int consumed  = br.Position - vStart;
                int remaining = vertexSize - consumed;
                if (remaining > 0) br.Skip(remaining);
            }

            return vd;
        }

        // =====================================================================
        // MATR
        // =====================================================================

        private static BumMaterial ReadMatr(BumBinaryReader br, int version)
        {
            var mat = new BumMaterial();

            while (!br.Eof)
            {
                BumBinaryReader c = ReadChunk(br, out string t);
                switch (t)
                {
                    case "NAME":
                        mat.Name = c.ReadCString();
                        break;
                    case "SNAM":
                        mat.ShaderName = c.ReadCString();
                        break;
                    case "LAYE":
                        mat.Layers.Add(ReadLaye(c));
                        break;
                    case "EMIS":
                        break; // 4 floats – not needed
                    case "SAMP":
                        mat.Samplers.Add(ReadSampChunk(c, version));
                        break;
                }
            }

            return mat;
        }

        private static BumLayer ReadLaye(BumBinaryReader br)
        {
            var layer = new BumLayer();

            while (!br.Eof)
            {
                BumBinaryReader c = ReadChunk(br, out string t);
                switch (t)
                {
                    case "STEX":
                        layer.TextureName = c.ReadCString();
                        break;
                    case "TEXC":
                        layer.Coordinates = c.ReadFloats(4);
                        break;
                    case "MAPT":
                        layer.MapType = c.ReadUInt32();
                        break;
                }
            }

            return layer;
        }

        private static BumSampler ReadSampChunk(BumBinaryReader br, int version)
        {
            var sampler = new BumSampler();

            if (version >= 200)
            {
                while (!br.Eof)
                {
                    BumBinaryReader c = ReadChunk(br, out string t);
                    switch (t)
                    {
                        case "NAME":
                            sampler.SamplerName = c.ReadCString();
                            break;
                        case "TXFM":
                            sampler.TextureName = c.ReadCString();
                            break;
                        case "SAPR":
                            break; // sampler flags – not needed
                    }
                }
            }
            else
            {
                // v1: NAME (samplerName), NAME (textureName), uint32 settingCount, ...
                BumBinaryReader c1 = ReadChunk(br, out _);
                sampler.SamplerName = c1.ReadCString();
                BumBinaryReader c2 = ReadChunk(br, out _);
                sampler.TextureName = c2.ReadCString();

                int settingCount = (int)br.ReadUInt32();
                for (int i = 0; i < settingCount; i++)
                {
                    ReadChunk(br, out _); // settingName
                    ReadChunk(br, out _); // settingValue
                }
            }

            return sampler;
        }

        // =====================================================================
        // MATS
        // =====================================================================

        private static BumMaterialSettings ReadMats(BumBinaryReader br, int version)
        {
            var ms = new BumMaterialSettings();

            int paramCount   = br.ReadUInt16();
            int samplerCount = br.ReadUInt16();

            ms.MaterialName = ReadNameChunk(br);
            ms.Path         = ReadNameChunk(br);

            for (int i = 0; i < paramCount; i++)
                SkipSfprBlock(br);

            for (int i = 0; i < samplerCount; i++)
                ms.Samplers.Add(ReadSampBlock(br, version));

            if (!br.Eof)
                br.Skip(4); // SRST: int16 source, int16 destination

            return ms;
        }

        private static string ReadNameChunk(BumBinaryReader br)
        {
            int start = br.Position;
            br.Skip(4);              // "NAME"
            uint size = br.ReadUInt32();
            string name = br.ReadCString();
            br.Seek(start + (int)size);
            return name;
        }

        private static void SkipSfprBlock(BumBinaryReader br)
        {
            int start = br.Position;
            br.Skip(4);              // 4-byte magic
            uint size = br.ReadUInt32();
            br.Seek(start + (int)size);
        }

        private static BumSampler ReadSampBlock(BumBinaryReader br, int version)
        {
            int startPos = br.Position;
            br.Skip(4);              // 4-byte magic
            uint size = br.ReadUInt32();

            BumBinaryReader c1 = ReadChunk(br, out _);
            string samplerName = c1.ReadCString();

            BumBinaryReader c2 = ReadChunk(br, out _);
            string textureName = c2.ReadCString();

            if (version < 200)
            {
                int settingCount = (int)br.ReadUInt32();
                for (int i = 0; i < settingCount; i++)
                {
                    ReadNameChunk(br);
                    ReadNameChunk(br);
                }
            }

            br.Seek(startPos + (int)size);
            return new BumSampler { SamplerName = samplerName, TextureName = textureName };
        }

        // =====================================================================
        // DBPL
        // =====================================================================

        private static int[] ReadDbpl(BumBinaryReader br)
        {
            int count   = br.ReadUInt16();
            int[] result = new int[count];
            for (int i = 0; i < count; i++)
                result[i] = br.ReadUInt16();
            return result;
        }

        // =====================================================================
        // V1 bone ID remapping
        // =====================================================================

        private static void RemapV1BoneIDs(BumModel model)
        {
            foreach (BumNode node in model.Nodes)
            {
                if (node.MeshInfo == null || node.BoneList == null) continue;

                int partIdx = (int)node.MeshInfo.MeshIndex;
                if (partIdx < 0 || partIdx >= model.Parts.Count) continue;

                BumPart part = model.Parts[partIdx];
                part.ParentNodeIndex = model.Nodes.IndexOf(node);

                foreach (BumSubMesh sm in part.SubMeshes)
                {
                    if (sm.BoneIDs == null || sm.Faces == null) continue;

                    int[] remapped = new int[sm.BoneIDs.Length];
                    for (int i = 0; i < sm.BoneIDs.Length; i++)
                    {
                        int localIdx = sm.BoneIDs[i];
                        remapped[i] = localIdx < node.BoneList.BoneCount
                            ? node.BoneList.BoneIDs[localIdx]
                            : localIdx;
                    }
                    sm.BoneIDs = remapped;

                    // Assign remapped bone IDs to all vertices in the vertex buffer
                    int vbIdx = sm.VertexBufferIndex;
                    if (vbIdx < 0 || vbIdx >= part.VertexBuffers.Count) continue;
                    BumVertexData vb = part.VertexBuffers[vbIdx];
                    if (vb.BoneIDs == null) continue;

                    int[] targetBones = remapped;
                    while (targetBones.Length < 8)
                    {
                        var padded = new int[targetBones.Length + 1];
                        Array.Copy(targetBones, padded, targetBones.Length);
                        targetBones = padded;
                    }

                    // Find vertex range used by this submesh
                    int minIdx = int.MaxValue, maxIdx = int.MinValue;
                    foreach (int[] tri in sm.Faces)
                    {
                        foreach (int idx in tri)
                        {
                            if (idx < minIdx) minIdx = idx;
                            if (idx > maxIdx) maxIdx = idx;
                        }
                    }

                    for (int vi = minIdx; vi <= maxIdx && vi < vb.BoneIDs.Length; vi++)
                    {
                        var bids = new byte[8];
                        for (int b = 0; b < 8; b++)
                            bids[b] = (byte)(b < targetBones.Length ? targetBones[b] : 0);
                        vb.BoneIDs[vi] = bids;
                    }
                }
            }
        }

        // =====================================================================
        // ANIM
        // =====================================================================

        private static void ReadAnim(BumBinaryReader br, int version, List<BumMotion> animations)
        {
            while (!br.Eof)
            {
                BumBinaryReader c = ReadChunk(br, out string t);
                if (t == "MOTI")
                    animations.Add(ReadMotion(c, version, isAni3: false));
            }
        }

        // =====================================================================
        // MOTI / ANI3 → BumMotion
        // =====================================================================

        private static BumMotion ReadMotion(BumBinaryReader br, int version, bool isAni3)
        {
            var motion     = new BumMotion();
            string[] bones = null;
            int curveCount = 0;

            while (!br.Eof)
            {
                BumBinaryReader c = ReadChunk(br, out string t);
                switch (t)
                {
                    case "NAME":
                        motion.Name = c.ReadCString();
                        break;
                    case "FCTN":
                        bones = ReadFctn(c, version);
                        break;
                    case "MPRA":
                        ReadMpra(c, version, out motion.Length, out curveCount);
                        break;
                    case "MFAT":
                        break; // offsets – not needed for sequential parsing
                    case "MFCD":
                        if (isAni3 || version >= 200)
                        {
                            var curve = ReadMfcd2(c, bones ?? Array.Empty<string>());
                            if (curve != null) motion.Curves.Add(curve);
                        }
                        else
                        {
                            ReadMfcd1(c, bones ?? Array.Empty<string>(), motion.Curves);
                        }
                        break;
                }
            }

            return motion;
        }

        private static string[] ReadFctn(BumBinaryReader br, int version)
        {
            int count  = br.ReadUInt16();
            var result = new string[count];
            for (int i = 0; i < count; i++)
            {
                int nameLen = br.ReadByte();
                result[i]   = version >= 200
                    ? Encoding.UTF8.GetString(br.ReadBytes(nameLen - 1))
                    : br.ReadFixedString(nameLen);
            }
            return result;
        }

        private static void ReadMpra(BumBinaryReader br, int version, out float length, out int curveCount)
        {
            br.ReadUInt32(); // unk
            if (version >= 200)
            {
                length     = br.ReadUInt32();
                br.ReadUInt16(); // maxIndex
                curveCount = br.ReadUInt16();
            }
            else
            {
                length     = br.ReadFloat();
                curveCount = (int)br.ReadUInt32();
            }
        }

        // =====================================================================
        // MFCD v1 – one chunk covers all bones
        // =====================================================================

        private static void ReadMfcd1(BumBinaryReader br, string[] bones, List<BumCurve> curves)
        {
            foreach (string boneName in bones)
            {
                var curve = new BumCurve { BoneName = boneName };
                br.ReadUInt16(); // unk1
                int curveIndex      = br.ReadByte();
                curve.Interpolation = br.ReadByte();
                int frameCount      = br.ReadUInt16();

                switch (curveIndex)
                {
                    case 1:
                        curve.CurveType = BumCurveType.Location;
                        curve.Keyframes = ReadHalfFrames3(br, frameCount);
                        break;
                    case 2:
                        curve.CurveType = BumCurveType.Rotation;
                        curve.Keyframes = ReadHalfFrames4(br, frameCount);
                        break;
                    case 3:
                        curve.CurveType = BumCurveType.Scale;
                        curve.Keyframes = ReadHalfFrames3(br, frameCount);
                        break;
                    case 4:
                        curve.CurveType = BumCurveType.Visibility;
                        curve.Keyframes = ReadUInt16Frames(br, frameCount);
                        break;
                    case 5:
                        curve.CurveType = BumCurveType.UvTransform;
                        curve.Keyframes = ReadHalfFrames4(br, frameCount);
                        break;
                    default:
                        curve.CurveType = BumCurveType.Unknown;
                        break;
                }

                curves.Add(curve);
            }
        }

        private static BumKeyframe[] ReadHalfFrames3(BumBinaryReader br, int frameCount)
        {
            var kfs = new BumKeyframe[frameCount];
            for (int i = 0; i < frameCount; i++)
                kfs[i] = new BumKeyframe
                {
                    Frame  = br.ReadFloat16(),
                    Values = new[] { br.ReadFloat16(), br.ReadFloat16(), br.ReadFloat16() },
                };
            return kfs;
        }

        private static BumKeyframe[] ReadHalfFrames4(BumBinaryReader br, int frameCount)
        {
            var kfs = new BumKeyframe[frameCount];
            for (int i = 0; i < frameCount; i++)
                kfs[i] = new BumKeyframe
                {
                    Frame  = br.ReadFloat16(),
                    Values = new[] { br.ReadFloat16(), br.ReadFloat16(), br.ReadFloat16(), br.ReadFloat16() },
                };
            return kfs;
        }

        private static BumKeyframe[] ReadUInt16Frames(BumBinaryReader br, int frameCount)
        {
            var kfs = new BumKeyframe[frameCount];
            for (int i = 0; i < frameCount; i++)
                kfs[i] = new BumKeyframe
                {
                    Frame  = br.ReadUInt16(),
                    Values = new[] { (float)br.ReadUInt16() },
                };
            return kfs;
        }

        // =====================================================================
        // MFCD2 v2 / ANI3 – one chunk = one curve
        // =====================================================================

        private static BumCurve ReadMfcd2(BumBinaryReader br, string[] bones)
        {
            var curve = new BumCurve();

            int curveIndex      = br.ReadByte();
            curve.Interpolation = br.ReadByte();
            int curveType       = br.ReadUInt16();
            int frameCount      = (int)br.ReadUInt32();
            int boneIndex       = br.ReadUInt16();
            int materialIndex   = br.ReadUInt16();

            curve.BoneName     = boneIndex   < bones.Length ? bones[boneIndex]   : string.Empty;
            curve.MaterialName = materialIndex < bones.Length ? bones[materialIndex] : string.Empty;

            switch (curveIndex)
            {
                case 0: curve.CurveType = BumCurveType.Location;  break;
                case 1: curve.CurveType = BumCurveType.Scale;     break;
                case 2: curve.CurveType = BumCurveType.Rotation;  break;
                case 3: curve.CurveType = BumCurveType.Visibility;break;
                default: curve.CurveType = BumCurveType.Unknown;  break;
            }

            switch (curveType)
            {
                case 2: // vector2 – 12 bytes per frame
                    curve.Keyframes = new BumKeyframe[frameCount];
                    for (int i = 0; i < frameCount; i++)
                    {
                        ushort frame = br.ReadUInt16();
                        br.ReadUInt16(); // unk
                        curve.Keyframes[i] = new BumKeyframe { Frame = frame, Values = new[] { br.ReadFloat(), br.ReadFloat() } };
                    }
                    break;
                case 4: // vector3 – 16 bytes per frame
                    curve.Keyframes = new BumKeyframe[frameCount];
                    for (int i = 0; i < frameCount; i++)
                    {
                        ushort frame = br.ReadUInt16();
                        br.ReadUInt16(); // unk
                        curve.Keyframes[i] = new BumKeyframe { Frame = frame, Values = new[] { br.ReadFloat(), br.ReadFloat(), br.ReadFloat() } };
                    }
                    break;
                case 5: // quaternion – 20 bytes per frame
                    curve.Keyframes = new BumKeyframe[frameCount];
                    for (int i = 0; i < frameCount; i++)
                    {
                        ushort frame = br.ReadUInt16();
                        br.ReadUInt16(); // unk
                        curve.Keyframes[i] = new BumKeyframe { Frame = frame, Values = new[] { br.ReadFloat(), br.ReadFloat(), br.ReadFloat(), br.ReadFloat() } };
                    }
                    break;
                default:
                    curve.Keyframes = Array.Empty<BumKeyframe>();
                    break;
            }

            return curve;
        }
    }
}
