from .utils.PyBinaryReader.binary_reader import *
import numpy as np
from dataclasses import dataclass, field
class BUM(BrStruct):
    def __init__(self):
        self.version = 100
        self.models = []
        self.animations = []
        self.allChunks = []
        self.scale = 1.0
    
    
    def __br_read__(self, br: BinaryReader):
        self.magic = br.read_str(4)
        self.fileSize = br.read_uint32()
        
        if self.magic not in [".BUM", "BUM2"]:
            raise ValueError("Not a valid BUM file")
        
        if self.magic == "BUM2":
            verChunk = br.read_struct(bumChunk)
            verBr = BinaryReader(verChunk.data)
            ver = verBr.read_struct(VER)
            self.version = ver.version
            self.scale = ver.scale
        

        while not br.eof():
            #we'll read the data as a generic chunk first
            chunk = br.read_struct(bumChunk)
            chunkBr = BinaryReader(chunk.data)
            if chunk.type == "MODL":
                modl = chunkBr.read_struct(MODL, None, self.version)
                self.models.append(modl)
            elif chunk.type == "ANIM":
                anim = chunkBr.read_struct(ANIM, None, self.version)
                self.animations.append(anim)
            elif chunk.type == "ANI3":
                # We'll create ANIM class with 1 motion as ANI3 is basically a MOTI chunk
                anim = ANIM()
                anim.motions.append(chunkBr.read_struct(ANI3, None, self.version))  
                self.animations.append(anim)
            else:
                print(f"Unknown chunk type: {chunk.type}")     
            
            self.allChunks.append(chunk)

class bumChunk(BrStruct):
    def __init__(self):
        super().__init__()
    
    
    def __br_read__(self, br):
        self.type = br.read_bytes(4).decode('utf-8')
        self.size = br.read_uint32()
        self.data = br.read_bytes(self.size - 8)


class VER(BrStruct):
    def __init__(self):
        self.version = 200
    
    
    def __br_read__(self, br):
        self.version = br.read_uint32()
        self.unk1 = br.read_uint32()
        self.totalVertexCount = br.read_uint32()
        self.scale = br.read_float32()

class MODL(BrStruct):
    def __init__(self):
        self.bbox = BBOX()
        self.nodes = []
        self.parts = []
        self.meshes = []
        self.materials = []
        self.materialSettings = []
        self.version = 100
        
    def __br_read__(self, br, version=100):
        self.version = version
        
        while not br.eof():
            chunk = br.read_struct(bumChunk)
            chunkBr = BinaryReader(chunk.data)
            
            
            if chunk.type == "BBOX":
                self.bbox = chunkBr.read_struct(BBOX)
            elif chunk.type == "NODE":
                node = chunkBr.read_struct(NODE, None, version)
                self.nodes.append(node)
            elif chunk.type == "PART":
                part = chunkBr.read_struct(PART, None, version)
                self.parts.append(part)
            elif chunk.type == "MESH":
                mesh = chunkBr.read_struct(MESH, None, version)
                self.meshes.append(mesh)
            elif chunk.type == "MATR": # materials
                material = chunkBr.read_struct(MATR, None, version)
                self.materials.append(material)
            elif chunk.type == "MATS": # material settings
                materialSetting = chunkBr.read_struct(MATS, None, version)
                self.materialSettings.append(materialSetting)
            elif chunk.type == "DBPL":   # deform bone list
                self.deformBoneList = chunkBr.read_struct(DBPL)
            elif chunk.type == "AABB":   # axis-aligned bounding box
                self.bbox = chunkBr.read_struct(AABB)
            else:
                print(f"Unknown MODL chunk type: {chunk.type}")
        
        
        for node in self.nodes:
            if not (node.meshInfo and node.boneList):
                continue

            part = self.parts[node.meshInfo.meshIndex]
            part.parent = node

            for i, mesh in enumerate(part.meshes):
                if not mesh.boneList:
                    continue
                
                mesh.boneList.boneIDs = [
                    node.boneList.boneIDs[idx] for idx in mesh.boneList.boneIDs
                ]

                # get the face buffer and remap the vertex weights
                faceBuffer = mesh.faceBuffer
                if hasattr(faceBuffer, 'vertexBuffer') and faceBuffer.vertexBuffer:
                    vertexBuffer = faceBuffer.vertexBuffer
                    
                    faceBufMin = faceBuffer.faces.min()
                    faceBufMax = faceBuffer.faces.max()
                    
                    # get vertices within the range used by the face buffer
                    usedVertices = vertexBuffer.vertices[faceBufMin:faceBufMax+1]
                    
                    targetBoneList = mesh.boneList.boneIDs
                    if len(targetBoneList) < 8:
                        # pad to 8 bones
                        targetBoneList = list(targetBoneList) + [0] * (8 - len(targetBoneList))
                    
                    usedVertices['boneIDs'] = targetBoneList



class BBOX(BrStruct):
    def __init__(self):
        self.min = [0.0, 0.0, 0.0]
        self.max = [0.0, 0.0, 0.0]
    
    def __br_read__(self, br):
        self.min = [br.read_float32() for _ in range(3)]
        self.max = [br.read_float32() for _ in range(3)]


class AABB(BrStruct):
    """Axis-aligned bounding box (BUM v2)"""
    def __init__(self):
        self.min = [0.0, 0.0, 0.0]
        self.max = [0.0, 0.0, 0.0]
    
    def __br_read__(self, br):
        self.min = [br.read_float32() for _ in range(3)]
        self.max = [br.read_float32() for _ in range(3)]


class NDATH(BrStruct):
    """Node data header (BUM v2)"""
    def __init__(self):
        self.parent = -1
        self.childCount = 0
        self.position = [0.0, 0.0, 0.0]
        self.scale = [1.0, 1.0, 1.0]
        self.rotation = [0.0, 0.0, 0.0, 1.0]
        self.pivot = [0.0, 0.0, 0.0]
    
    def __br_read__(self, br):
        self.parent = br.read_int32()
        self.childCount = br.read_int32()
        self.position = br.read_float32(3)
        self.scale = br.read_float32(3)
        self.rotation = br.read_float32(4)
        self.pivot = br.read_float32(3)


class SKDBH(BrStruct):
    """Skeleton data header - 4x4 matrix (BUM v2)"""
    def __init__(self):
        self.matrix = np.identity(4).tolist()
    
    def __br_read__(self, br):
        # Read 4x4 matrix as 16 floats
        self.matrix = np.frombuffer(br.read_bytes(64), dtype=np.float32).reshape((4, 4)).tolist()

class NODE(BrStruct):
    def __init__(self):
        self.name = ""
        self.translation = [0.0, 0.0, 0.0]
        self.rotation = [0.0, 0.0, 0.0, 1.0]
        self.scale = [1.0, 1.0, 1.0]
        self.pivot = [0.0, 0.0, 0.0]
        self.matrix = np.identity(4).tolist()
        self.parentIndex = -1
        self.bbox = BBOX()
        self.flags = 0
        self.meshInfo = None
        self.boneList = None
        self.version = 100
    
    def __br_read__(self, br, version=100):
        self.version = version
        
        while not br.eof():
            chunk = br.read_struct(bumChunk)
            chunkBr = BinaryReader(chunk.data)
            
            if chunk.type == "NAME":
                self.name = chunkBr.read_struct(NAME).name
            elif chunk.type == "BBOX":
                self.bbox = chunkBr.read_struct(BBOX)
            elif chunk.type == "AABB":
                self.bbox = chunkBr.read_struct(AABB)
            elif chunk.type == "NDAT":
                nodeData = chunkBr.read_struct(NDATH)
                self.parentIndex = nodeData.parent
                self.translation = nodeData.position
                self.scale = nodeData.scale
                self.rotation = nodeData.rotation
            elif chunk.type == "SKDB":
                self.matrix = chunkBr.read_struct(SKDBH).matrix
            elif chunk.type == "NSTA":
                self.flags = chunkBr.read_struct(NSTA).flags
            elif chunk.type == "PARE":
                self.parentIndex = chunkBr.read_struct(PARE).parentIndex
            elif chunk.type == "TRNS":
                self.translation = chunkBr.read_struct(TRNS).translation
            elif chunk.type == "ROTQ":
                self.rotation = chunkBr.read_struct(ROTQ).rotation
            elif chunk.type == "SCAL":
                self.scale = chunkBr.read_struct(SCAL).scale
            elif chunk.type == "BLEB":
                self.boneList = chunkBr.read_struct(BLEB)
            elif chunk.type == "BLEO":
                self.boneCoordinates = chunkBr.read_struct(BLEO, None, self.boneList.boneCount)
            elif chunk.type == "VISI":
                self.visibility = chunkBr.read_struct(VISI).visibility
            elif chunk.type == "PIVO":
                self.pivot = chunkBr.read_struct(PIVO)
            elif chunk.type == "DRWP":
                self.meshInfo = chunkBr.read_struct(DRWP)
            else:
                print(f"Unknown NODE chunk type: {chunk.type} for node {self.name}")
        
        
        # we'll check for the flags later and add properties accordingly


class NAME(BrStruct):
    def __init__(self):
        self.name = ""
    
    
    def __br_read__(self, br):
        self.name = br.read_str()
    
    def read_name(self, br: BinaryReader):
        startPos = br.pos()
        
        magic = br.read_str(4)
        size = br.read_uint32()
        
        self.name = br.read_str()
        
        #skip the reamining bytes if any
        br.seek(startPos + size)
        
        return self.name

class NSTA(BrStruct):
    def __init__(self):
        self.flags = 0
    
    
    def __br_read__(self, br):
        self.flags = br.read_uint32()


class PARE(BrStruct):
    def __init__(self):
        self.parentIndex = -1
    
    
    def __br_read__(self, br):
        self.parentIndex = br.read_int32()


class TRNS(BrStruct):
    def __init__(self):
        self.translation = [0.0, 0.0, 0.0]
    
    
    def __br_read__(self, br):
        self.translation = br.read_float32(3)

class ROTQ(BrStruct):
    def __init__(self):
        self.rotation = [0.0, 0.0, 0.0, 1.0]
    
    
    def __br_read__(self, br):
        self.rotation = br.read_float32(4)


class SCAL(BrStruct):
    def __init__(self):
        self.scale = [1.0, 1.0, 1.0]
    
    
    def __br_read__(self, br):
        self.scale = br.read_float32(3)


class VISI(BrStruct):
    def __init__(self):
        self.visibility = 0
    
    def __br_read__(self, br):
        self.visibility = br.read_uint32()


class PIVO(BrStruct):
    """Pivot point"""
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
    
    def __br_read__(self, br):
        self.x = br.read_float32()
        self.y = br.read_float32()
        self.z = br.read_float32()

class BLEB(BrStruct):
    def __init__(self):
        self.boneCount = 0
        self.boneIDs = []
    
    
    def __br_read__(self, br):
        self.boneCount = br.read_uint32()
        self.boneIDs = br.read_uint16(self.boneCount)
        

class BLES(BrStruct):
    def __init__(self):
        self.boneCount = 0
        self.boneIDs = []
    
    
    def __br_read__(self, br):
        self.boneCount = br.read_uint32()
        self.boneIDs = br.read_uint32(self.boneCount)


class BLEO(BrStruct):
    def __init__(self):
        self.boneCount = 0
        self.matrixList = []
    
    
    def __br_read__(self, br, boneCount):
        for _ in range(boneCount):
            matrix = br.read_float32(16)
            self.matrixList.append(matrix)


class DRWP(BrStruct):
    def __init__(self):
        self.unk1 = 0
        self.meshIndex = 0
    
    
    def __br_read__(self, br):
        self.unk1 = br.read_uint32()
        self.meshIndex = br.read_uint32()


class PART(BrStruct):
    def __init__(self):
        self.name = ""
        self.bbox = BBOX()
        self.meshes = []
        self.vertexBuffers = []
        self.isSkinned = False
        self.parent = None
        self.version = 100
    
    
    def __br_read__(self, br, version=100):
        self.version = version
        
        while not br.eof():
            chunk = br.read_struct(bumChunk)
            chunkBr = BinaryReader(chunk.data)
            if chunk.type == "NAME":
                self.name = chunkBr.read_struct(NAME).name
            elif chunk.type == "BBOX":
                self.bbox = chunkBr.read_struct(BBOX)
            elif chunk.type == "MESH":
                mesh = chunkBr.read_struct(MESH, None, version)
                if mesh.isSkinned:
                    self.isSkinned = True
                
                self.meshes.append(mesh)
            elif chunk.type == "ARAY":
                self.vertexBuffers.append(chunkBr.read_struct(ARAY, None, self.isSkinned))
            else:
                print(f"Unknown PART chunk type: {chunk.type}")
        
        # combine vertex buffers with meshes
        for mesh in self.meshes:
            if hasattr(mesh, 'faceBuffer') and mesh.faceBuffer:
                mesh.faceBuffer.vertexBuffer = self.vertexBuffers[mesh.faceBuffer.vertexBufferIndex]
            


class MESH(BrStruct):
    def __init__(self):
        self.name = ""
        self.bbox = BBOX()
        self.materialIndex = 0
        self.boneList = None
        self.faceBuffer = None
        self.isSkinned = False
        self.version = 100
        self.meshParent = None
        self.vertexBuffer = None
    
    
    def __br_read__(self, br, version=100):
        self.version = version
        
        if version >= 200:
            # BUM v2 format - read children blocks
            while not br.eof():
                chunk = br.read_struct(bumChunk)
                chunkBr = BinaryReader(chunk.data)
                
                if chunk.type == "NAME":
                    self.name = chunkBr.read_struct(NAME).name
                elif chunk.type == "MESP":
                    mesp: MESP = chunkBr.read_struct(MESP)
                    self.meshParent = mesp.parentBoneIndex
                    self.materialIndex = mesp.materialIndex
                elif chunk.type == "SMAT":
                    material = chunkBr.read_struct(SMAT)
                    self.materialIndex = material.materialIndex
                elif chunk.type == "SBID":
                    self.boneList = chunkBr.read_struct(SBID)
                    self.isSkinned = True
                elif chunk.type == "VERT":
                    self.vertexBuffer = chunkBr.read_struct(VERT, None, version)
                elif chunk.type == "DRWA":
                    self.faceBuffer = chunkBr.read_struct(DRWA, None, version)
                elif chunk.type == "AABB":
                    self.bbox = chunkBr.read_struct(AABB)
                else:
                    print(f"Unknown MESH chunk type (v2): {chunk.type}")
            
            # For v2, link vertex buffer to face buffer
            if self.faceBuffer and self.vertexBuffer:
                self.faceBuffer.vertexBuffer = self.vertexBuffer
        else:
            # BUM v1 format
            while not br.eof():
                chunk = br.read_struct(bumChunk)
                chunkBr = BinaryReader(chunk.data)
                if chunk.type == "BBOX":
                    self.bbox = chunkBr.read_struct(BBOX)
                elif chunk.type == "SMAT":
                    material = chunkBr.read_struct(SMAT)
                    self.materialIndex = material.materialIndex
                elif chunk.type == "BLES":
                    self.boneList = chunkBr.read_struct(BLES)
                    self.isSkinned = True
                elif chunk.type == "DRWA":
                    faceBuffer = chunkBr.read_struct(DRWA, None, version)
                    self.faceBuffer = faceBuffer
                else:
                    print(f"Unknown MESH chunk type (v1): {chunk.type}")
                


class SMAT(BrStruct):
    def __init__(self):
        self.materialIndex = 0
    
    
    def __br_read__(self, br):
        self.materialIndex = br.read_uint32()


class MESP(BrStruct):
    """Mesh parent (BUM v2)"""
    def __init__(self):
        self.parentBoneIndex = 0
        self.meshIndex = 0
    
    def __br_read__(self, br):
        self.parentBoneIndex = br.read_uint32()
        self.materialIndex = br.read_uint32()


class SBID(BrStruct):
    """Bone ID list (BUM v2)"""
    def __init__(self):
        self.count = 0
        self.indices = []
    
    def __br_read__(self, br):
        self.count = br.read_uint16()
        self.boneIDs = br.read_uint16(self.count)


class DBPL(BrStruct):
    """Deform bone list"""
    def __init__(self):
        self.count = 0
        self.indices = []
    
    def __br_read__(self, br):
        self.count = br.read_uint16()
        self.indices = br.read_uint16(self.count)


class DRWA(BrStruct):
    def __init__(self):
        self.faceFlag = 0
        self.vertBufferIndex = 0
        self.faceCount = 0
        self.indices = []
        self.unk = 0
        self.count = 0
    
    
    def __br_read__(self, br, version=100):
        if version >= 200:
            # BUM v2 format
            self.faceFlag = br.read_uint32()
            self.indexCount = br.read_uint32()
            self.faces = np.frombuffer(br.read_bytes(self.indexCount * 2), dtype=np.uint16).reshape((-1, 3))
        else:
            # BUM v1 format
            self.faceFlag = br.read_uint8()
            self.vertexBufferIndex = br.read_uint8()
            self.indexCount = br.read_uint16()
            self.faces = np.frombuffer(br.read_bytes(self.indexCount * 2), dtype=np.uint16).reshape((-1, 3))


class ARAY(BrStruct):
    def __init__(self):
        self.vertexFlags = 0
        self.vertexFlags2 = 0
        self.vertexCount = 0
        self.vertices = []
    
    
    def __br_read__(self, br, hasWeights):
        self.vertexFlags = br.read_uint8()
        self.vertexFlags2 = br.read_uint8()
        self.vertexCount = br.read_uint16()
        
        vertexDtype = []
        if self.vertexFlags & 1:
            vertexDtype.append(('position', 'f4', 3))
        if self.vertexFlags & 2:
            vertexDtype.append(('normals', 'f4', 3))
        if self.vertexFlags & 8:
            if self.vertexFlags2 & 0x20:
                vertexDtype.append(('uvs', 'f4', 2))
            else:
                vertexDtype.append(('uvs', 'f2', 2))
        if self.vertexFlags & 4:
            vertexDtype.append(('colors', 'u1', 4))
        if hasWeights:
            vertexDtype.append(('weights', 'u1', 8))
        
        self.vertices = np.frombuffer(br.read_bytes(self.vertexCount * np.dtype(vertexDtype).itemsize), dtype=vertexDtype)
        
        if hasWeights:
            # Add boneIDs field (not read from file, just initialized as zeros)
            boneIDs = np.zeros((self.vertexCount, 8), dtype=np.uint8)
            
            # Create new dtype with boneIDs field added
            new_dtype = np.dtype(vertexDtype + [('boneIDs', 'u1', 8)])
            
            # Create new array with the expanded dtype
            new_vertices = np.zeros(self.vertexCount, dtype=new_dtype)
            
            # Copy existing data
            for field in self.vertices.dtype.names:
                new_vertices[field] = self.vertices[field]
            
            # Initialize boneIDs (already zeros, but explicit)
            new_vertices['boneIDs'] = boneIDs
            
            self.vertices = new_vertices


class VERT(BrStruct):
    """Vertex buffer (BUM v2)"""
    def __init__(self):
        self.vertexCount = 0
        self.vertexSize = 0
        self.vertexFlags = 0
        self.vertices = []
    
    def __br_read__(self, br, version=200):
        self.vertexCount = br.read_uint32()
        self.vertexSize = br.read_uint16()
        self.vertexFlags = br.read_uint16()
        
        vertexDtype = []
        
        if version > 201:
            # BUM v2.02+ format
            if self.vertexFlags & 1:
                vertexDtype.append(('position', 'f4', 3))
            if self.vertexFlags & 64:
                vertexDtype.append(('boneIDs', 'u1', 4))
            if self.vertexFlags & 128:
                vertexDtype.append(('weights', 'u1', 4))
            if self.vertexFlags & 2:
                vertexDtype.append(('normals', 'f4', 3))
            if self.vertexFlags & 4:
                vertexDtype.append(('UV0', 'f4', 2))
            if self.vertexFlags & 256:
                vertexDtype.append(('UV1', 'f4', 2))
            if self.vertexFlags & 8:
                vertexDtype.append(('color', 'u1', 4))
            if self.vertexFlags & 16:
                vertexDtype.append(('tangents', 'f4', 3))
            if self.vertexFlags & 32:
                vertexDtype.append(('binormals', 'f4', 3))
        else:
            # BUM v2.00/2.01 format
            if self.vertexFlags & 1:
                vertexDtype.append(('position', 'f4', 3))
            if self.vertexFlags & 2:
                vertexDtype.append(('normals', 'f4', 3))
            if self.vertexFlags & 4:
                vertexDtype.append(('UV0', 'f4', 2))
            if self.vertexFlags & 8:
                vertexDtype.append(('color', 'u1', 4))
            if self.vertexFlags & 64:
                vertexDtype.append(('boneIDs', 'u1', 4))
                vertexDtype.append(('weights', 'u1', 4))
            if self.vertexFlags & 256:
                vertexDtype.append(('UV1', 'f4', 2))
        
        self.vertices = np.frombuffer(br.read_bytes(self.vertexCount * np.dtype(vertexDtype).itemsize), dtype=vertexDtype)


class MATR(BrStruct):
    def __init__(self):
        self.name = ""
        self.shaderName = ""
        self.layers = []
        self.samplers = []
    
    
    def __br_read__(self, br, version=100):
        
        while not br.eof():
            chunk = br.read_struct(bumChunk)
            chunkBr = BinaryReader(chunk.data)
            if chunk.type == "NAME":
                self.name = chunkBr.read_struct(NAME).name
            elif chunk.type == "LAYE":
                layer = chunkBr.read_struct(LAYE)
                self.layers.append(layer)
            elif chunk.type == "EMIS": # emissive?
                self.emissive = chunkBr.read_struct(EMIS)
            elif chunk.type == "SAMP":
                sampler = chunkBr.read_struct(SAMP, None, version)
                self.samplers.append(sampler)
            elif chunk.type == "SNAM": # shader name
                self.shaderName = chunkBr.read_struct(SNAM).name
            else:
                print(f"Unknown MATR chunk type: {chunk.type}")


class LAYE(BrStruct):
    def __init__(self):
        self.textureName = ""
        self.textureCoordinates = [0.0, 0.0, 1.0, 1.0]
        self.mapType = 0
    
    
    def __br_read__(self, br):
        
        while not br.eof():
            chunk = br.read_struct(bumChunk)
            chunkBr = BinaryReader(chunk.data)
            if chunk.type == "STEX":
                self.textureName = chunkBr.read_struct(STEX).textureName
            elif chunk.type == "TEXC": # texture coordinates?
                self.textureCoordinates = chunkBr.read_struct(TEXC).coordinates
            elif chunk.type == "MAPT": # map type?
                self.mapType = chunkBr.read_struct(MAPT).mapType
            else:
                print(f"Unknown LAYE chunk type: {chunk.type}")


class STEX(BrStruct):
    def __init__(self):
        self.textureName = ""
    
    
    def __br_read__(self, br):
        self.textureName = br.read_str()


class TEXC(BrStruct):
    def __init__(self):
        self.coordinates = [0,0,1,1]
    
    
    def __br_read__(self, br):
        self.coordinates = br.read_float32(4)


class MAPT(BrStruct):
    def __init__(self):
        self.mapType = 0
    
    
    def __br_read__(self, br):
        self.mapType = br.read_uint32()


class EMIS(BrStruct):
    def __init__(self):
        self.emissiveColor = [0.0, 0.0, 0.0, 1.0]
    
    
    def __br_read__(self, br):
        self.emissiveColor = br.read_float32(4)


class MATS(BrStruct):
    def __init__(self):
        self.materialName = ""
        self.path = ""
        self.version = 100
    
    
    def __br_read__(self, br, version=100):
        self.version = version
        self.paramCount = br.read_uint16()
        self.samplerCount = br.read_uint16()
                
        self.materialName = NAME().read_name(br)
        self.path = NAME().read_name(br)
        
        self.params = []
        for i in range(self.paramCount):
            param = SFPR()
            param.read(br)
            self.params.append(param)
            
        self.samplers = []
        for i in range(self.samplerCount):
            sampler = SAMP()
            sampler.read(br, version)
            self.samplers.append(sampler)
        
        sourceDest = br.read_struct(SRST)
        self.source = sourceDest.source
        self.destination = sourceDest.destination


class SFPR(BrStruct):
    def __init__(self):
        self.valueCount = 0
        self.values = []
        self.name = ""
    
    
    def __br_read__(self, br):
        self.valueCount = br.read_uint32()
        self.values = br.read_float32(self.valueCount)
        self.name = br.read_str()
    
    def read(self, br: BinaryReader):
        startPos = br.pos()
        
        magic = br.read_str(4)
        size = br.read_uint32()
        
        self.valueCount = br.read_uint32()
        self.values = br.read_float32(self.valueCount)
        self.name = br.read_str()
        
        #skip the reamining bytes if any
        br.seek(startPos + size)
        
class SAMP(BrStruct):
    def __init__(self):
        self.samplerName = ""
        self.textureName = ""
        self.settings = []
        self.version = 100
    
    
    def __br_read__(self, br, version=100):
        if version >= 200:
            while not br.eof():
                chunk = br.read_struct(bumChunk)
                chunkBr = BinaryReader(chunk.data)
                
                if chunk.type == "NAME":
                    self.samplerName = chunkBr.read_struct(NAME).name
                elif chunk.type == "SAPR":
                    self.samplerFlags = chunkBr.read_struct(SAPR)
                elif chunk.type == "TXFM":
                    self.textureName = chunkBr.read_struct(TXFM).textureName
                else:
                    print(f"Unknown SAMP chunk type: {chunk.type}")
        else:
            self.samplerName = br.read_struct(NAME).name
            self.textureName = br.read_struct(NAME).name
            self.settingCount = br.read_uint32()
            
            self.settings = []
            for _ in range(self.settingCount):
                settingName = br.read_struct(NAME).name
                settingValue = br.read_struct(NAME).name
                self.settings.append((settingName, settingValue))

    
    def read(self, br: BinaryReader, version=100):
        self.version = version
        startPos = br.pos()
        magic = br.read_str(4)
        size = br.read_uint32()
        
        # Read sampler name and texture name
        chunk1 = br.read_struct(bumChunk)
        chunkBr1 = BinaryReader(chunk1.data)
        self.samplerName = chunkBr1.read_str()
        
        chunk2 = br.read_struct(bumChunk)
        chunkBr2 = BinaryReader(chunk2.data)
        self.textureName = chunkBr2.read_str()
        
        # Only read settingCount for v1
        if version < 200:
            self.settingCount = br.read_uint32()
            self.settings = []
            for _ in range(self.settingCount):
                settingName = NAME().read_name(br)
                settingValue = NAME().read_name(br)
                self.settings.append((settingName, settingValue))
        else:
            # v2 reads children blocks instead
            self.settings = []
            while br.pos() < startPos + size:
                chunk = br.read_struct(bumChunk)
                chunkBr = BinaryReader(chunk.data)
                
                if chunk.type == "SNAM":
                    self.shaderName = chunkBr.read_struct(SNAM)
                elif chunk.type == "SAPR":
                    self.samplerFlags = chunkBr.read_struct(SAPR)
                elif chunk.type == "TXFM":
                    self.textureFile = chunkBr.read_struct(TXFM)
                else:
                    # Could be other setting types
                    pass
        
        br.seek(startPos + size)


class SRST(BrStruct):
    def __init__(self):
        self.source = 0
        self.destination = 0
    
    
    def __br_read__(self, br):
        self.source = br.read_int16()
        self.destination = br.read_int16()


class SNAM(BrStruct):
    """Shader name"""
    def __init__(self):
        self.name = ""
    
    def __br_read__(self, br):
        self.name = br.read_str()


class SAPR(BrStruct):
    """Sampler flags/properties"""
    def __init__(self):
        self.flag1 = 0
        self.flag2 = 0
        self.flag3 = 0
        self.flag4 = 0
        self.unk = 0
    
    def __br_read__(self, br):
        self.flag1 = br.read_uint8()
        self.flag2 = br.read_uint8()
        self.flag3 = br.read_uint8()
        self.flag4 = br.read_uint8()
        self.unk = br.read_uint32()


class TXFM(BrStruct):
    """Texture filename"""
    def __init__(self):
        self.textureName = ""
    
    def __br_read__(self, br):
        self.textureName = br.read_str()

class ANIM(BrStruct):
    def __init__(self):
        super().__init__()
        self.version = 100
        self.motions = []
    
    
    def __br_read__(self, br, version=100):
        self.version = version
        self.motions = []
        while not br.eof():
            chunk = br.read_struct(bumChunk)
            chunkBr = BinaryReader(chunk.data)
            if chunk.type == "MOTI":
                motion = chunkBr.read_struct(MOTI, None, self.version)
                self.motions.append(motion)
            else:
                print(f"Unknown ANIM chunk type: {chunk.type}")
                
                
class MOTI(BrStruct):
    def __init__(self):
        self.name = ""
        self.boneList = None
        self.motionInfo = None
        self.curves = []
        self.length = 0.0
        self.curveCount = 0
        self.version = 100
    
    
    def __br_read__(self, br, version=100):
        self.version = version
        self.boneList = None
        self.motionInfo = None
        self.curveOffsets = []
        self.curves = []
        
        while not br.eof():
            chunk = br.read_struct(bumChunk)
            chunkBr = BinaryReader(chunk.data)
            if chunk.type == "NAME":
                self.name = chunkBr.read_struct(NAME).name
            elif chunk.type == "FCTN":
                self.boneList = chunkBr.read_struct(FCTN, None, version)
            elif chunk.type == "MPRA":
                self.motionInfo = chunkBr.read_struct(MPRA, None, version)
                self.length = self.motionInfo.animLength
                self.curveCount = self.motionInfo.curveCount
            elif chunk.type == "MFAT":
                self.curveOffsets = chunkBr.read_struct(MFAT, None, self.motionInfo.curveCount)
            elif chunk.type == "MFCD":
                self.curves = chunkBr.read_struct(MFCD, None, self.boneList.bones, self.version).curves
            else:
                print(f"Unknown MOTI chunk type: {chunk.type}")


class ANI3(BrStruct):
    def __init__(self):
        self.name = ""
        self.boneList = None
        self.motionInfo = None
        self.curves = []
        self.length = 0.0
        self.curveCount = 0
        self.version = 100
    
    
    def __br_read__(self, br, version=100):
        self.version = version
        self.boneList = None
        self.motionInfo = None
        self.curveOffsets = []
        self.curves = []
        
        while not br.eof():
            chunk = br.read_struct(bumChunk)
            chunkBr = BinaryReader(chunk.data)
            if chunk.type == "NAME":
                self.name = chunkBr.read_struct(NAME).name
            elif chunk.type == "FCTN":
                self.boneList = chunkBr.read_struct(FCTN, None, version)
            elif chunk.type == "MPRA":
                self.motionInfo = chunkBr.read_struct(MPRA, None, version)
                self.length = self.motionInfo.animLength
                self.curveCount = self.motionInfo.curveCount
            elif chunk.type == "MFAT":
                self.curveOffsets = chunkBr.read_struct(MFAT, None, self.motionInfo.curveCount)
            elif chunk.type == "MFCD":
                curve = chunkBr.read_struct(MFCD2,None, self.boneList.bones, self.version).curve
                self.curves.append(curve)
            else:
                print(f"Unknown MOTI chunk type: {chunk.type}")


class MPRA(BrStruct):
    def __init__(self):
        self.unk = 0
        self.animLength = 0.0
        self.curveCount = 0
    
    
    def __br_read__(self, br, version=100):
        self.unk = br.read_uint32()
        
        if version >= 200:
            self.animLength = br.read_uint32()
            self.maxIndex = br.read_uint16()
            self.curveCount = br.read_uint16()
        
        else:
            self.animLength = br.read_float32()
            self.curveCount = br.read_uint32()

class FCTN(BrStruct):
    def __init__(self):
        self.boneCount = 0
        self.bones = []
    
    
    def __br_read__(self, br, version=100):
        self.boneCount = br.read_uint16()
        self.bones = []
        
        if version >= 200:
            for _ in range(self.boneCount):
                nameLength = br.read_uint8()
                self.name = br.read_str(nameLength-1)
                self.bones.append(self.name)
        
        else:
            for _ in range(self.boneCount):
                nameLength = br.read_uint8()
                name = br.read_str(nameLength)
                self.bones.append(name)
            
class MFAT(BrStruct):
    def __init__(self):
        self.offsets = []
    
    
    def __br_read__(self, br, curveCount):
        self.offsets = br.read_uint32(curveCount)
        
class MFCD(BrStruct):
    def __init__(self):
        self.curves = []
        self.version = 100
    
    
    def __br_read__(self, br, bones, version=100):
        self.version = version
        
        for i, bone in enumerate(bones):
            curve = Curve()
            curve.name = bone
            self.curves.append(curve)
            
            unk1 = br.read_uint16()
            curveIndex = br.read_uint8()
            curve.interpolation = br.read_uint8()
            curve.frameCount = br.read_uint16()
            
            if curveIndex == 1: #location
                curve.type = "location"
                curve.dataType = "vector3"
                curve.frames = np.frombuffer(br.read_bytes(curve.frameCount * 8), dtype=[('frame', 'f2'), ("values", 'f2', 3)])
                    
            elif curveIndex == 2: #rotation
                curve.type = "rotation_quaternion"
                curve.dataType = "quaternion"
                curve.frames = np.frombuffer(br.read_bytes(curve.frameCount * 10), dtype=[('frame', 'f2'), ("values", 'f2', 4)])
                    
            elif curveIndex == 3: #scale
                curve.type = "scale"
                curve.dataType = "vector3"
                curve.frames = np.frombuffer(br.read_bytes(curve.frameCount * 8), dtype=[('frame', 'f2'), ("values", 'f2', 3)])
                    
            elif curveIndex == 4: #visibility
                curve.type = "visibility"
                curve.dataType = "integer"
                curve.frames = np.frombuffer(br.read_bytes(curve.frameCount * 4), dtype=[('frame', 'f2'), ("value", 'u2')])
            
            elif curveIndex == 5: #uv
                curve.type = "uv_transform"
                curve.dataType = "vector4"
                curve.frames = np.frombuffer(br.read_bytes(curve.frameCount * 10), dtype=[('frame', 'f2'), ("value", 'f2', 4)])
                    
            else:
                print(f"UNKNOWN CURVE ({curveIndex}), index {i}, bone {bone}")


class MFCD2(BrStruct):
    def __init__(self):
        self.curve = Curve()
        self.version = 100
    
    
    def __br_read__(self, br, bones, version=100):
        self.version = version
        
        curveIndexMap = {
            0: "location",
            1: "scale",
            2: "rotation_quaternion",
            3: "visibility",
            4: "Red",
            5: "Green",
            6: "Blue",}
        
        curveTypeMap = {
            2: "vector2",
            4: "vector3",
            5: "quaternion",
        }
        
        curve = Curve()
        
        curve.curveIndex = br.read_uint8()
        curve.interpolation = br.read_uint8()
        curve.curveType = br.read_uint16()
        curve.frameCount = br.read_uint32()
        curve.boneIndex = br.read_uint16()
        curve.materialIndex = br.read_uint16()
        
        # Set curve name based on bone/material
        if curve.boneIndex < len(bones):
            curve.name = bones[curve.boneIndex]
        
        if curve.materialIndex < len(bones):
            curve.materialName = bones[curve.materialIndex]
        
        # Read frame data based on curveType
        if curve.curveType == 2:  # 2D Vector
            curve.frames = np.frombuffer(
                br.read_bytes(curve.frameCount * 12), dtype=[('frame', 'u2'), ('unk', 'u2'), ("values", 'f4', 2)])
        
        elif curve.curveType == 4:  # 3D Vector (euler)
            curve.frames = np.frombuffer(
                br.read_bytes(curve.frameCount * 16), dtype=[('frame', 'u2'), ('unk', 'u2'), ("values", 'f4', 3)])
        
        elif curve.curveType == 5:  # Quaternion
            curve.frames = np.frombuffer(
                br.read_bytes(curve.frameCount * 20), dtype=[('frame', 'u2'), ('unk', 'u2'), ("values", 'f4', 4)])
            
        curve.type = curveIndexMap.get(curve.curveIndex, "unknown")
        curve.dataType = curveTypeMap.get(curve.curveType, "unknown")
        self.curve = curve

# this should serve as a unified curve class for both versions
@dataclass
class Curve:
    name: str = ""
    materialName: str = ""
    type: str = "" # e.g., "position", "rotation", "scale", "visibility", etc.
    dataType: str = "" # e.g., "vector3", "quaternion", "float", etc.
    frameCount: int = 0
    interpolation: int = 0 # 0 = constant, 1 = linear
    frames: list = field(default=None)
