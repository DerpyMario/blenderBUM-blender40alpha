import bpy, bmesh
from .utils.PyBinaryReader.binary_reader import *
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, IntProperty, CollectionProperty, FloatProperty
from bpy.types import Operator
from mathutils import Matrix, Vector, Quaternion, Euler
from math import radians, pi, tan
import numpy as np
import os
import tempfile
from .lzs import *
from .bum import *

from time import perf_counter
bl_info = {
    "name" : "BUM/LZS Importer",
    "author" : "Al-Hydra",
    "description" : "Importer for LZS archives and BUM models/animations.",
    "blender" : (4, 5, 0),
    "version" : (1, 0, 0),
    "category" : "Import"
}


class LZS_IMPORTER_OT_IMPORT(Operator, ImportHelper):
    bl_label = "Import .bum .lzs or .lza files"
    bl_idname = "import_scene.lzs"


    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'}) # type: ignore
    filter_glob: StringProperty(default="*.lzs;*.lza;*.bum", options={"HIDDEN"}) # type: ignore
    filename_ext = ".lzs"
    filepath: StringProperty(subtype='FILE_PATH') # type: ignore

    
    def draw(self, context):
        layout = self.layout

    def execute(self, context):
        time = perf_counter()
        loaded_texture_folders = set()
        
        for file in self.files:
            filepath = os.path.join(self.directory, file.name)
            ext = os.path.splitext(filepath)[1].lower()
            
            if ext == '.lzs':
                lzs = lzsReader(filepath)
                importLZS(lzs, os.path.basename(filepath).split('.')[0])
            elif ext == '.lza':
                lza = lzaReader(filepath)
                importLZS(lza, os.path.basename(filepath).split('.')[0])
            elif ext == '.bum':
                # Load textures from the same folder (only once per folder)
                folder = os.path.dirname(filepath)
                if folder not in loaded_texture_folders:
                    loaded_texture_folders.add(folder)
                    for f in os.listdir(folder):
                        if f.lower().endswith(('.png', '.dds', '.bc7', '.astc')):
                            image = bpy.data.images.load(os.path.join(folder, f))
                            image.name = os.path.splitext(f)[0]
                
                # Import BUM file
                with open(filepath, 'rb') as f:
                    br = BinaryReader(f.read())
                    bum = br.read_struct(BUM)
                importBUM(bum, os.path.basename(filepath).split('.')[0])
            else:
                self.report({'WARNING'}, f"Unsupported file type: {ext}")
                continue

        self.report({'INFO'}, f"Imported {len(self.files)} files in {perf_counter() - time:.4f} seconds")

        return {'FINISHED'}



class dropLZSOperator(bpy.types.Operator):
    bl_idname = "wm.drop_lzs_operator"
    bl_label = "Drop LZS Importer"

    filepath: StringProperty(subtype='FILE_PATH')
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        time = perf_counter()
        for file in self.files:
            filepath = os.path.join(self.directory, file.name)
            lzs = lzsReader(filepath)
            importLZS(lzs, os.path.basename(filepath).split('.')[0])
        
        self.report({'INFO'}, f"Imported {len(self.files)} files in {perf_counter() - time:.4f} seconds")
        return {'FINISHED'}


class dropLZAOperator(bpy.types.Operator):
    bl_idname = "wm.drop_lza_operator"
    bl_label = "Drop LZA Importer"

    filepath: StringProperty(subtype='FILE_PATH')
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        time = perf_counter()
        for file in self.files:
            filepath = os.path.join(self.directory, file.name)
            
            #decrypt and import
            lza = lzaReader(filepath)
            importLZS(lza, os.path.basename(filepath).split('.')[0])
        
        self.report({'INFO'}, f"Imported {len(self.files)} files in {perf_counter() - time:.4f} seconds")
        return {'FINISHED'}


class dropBUMOperator(bpy.types.Operator):
    bl_idname = "wm.drop_bum_operator"
    bl_label = "Drop BUM Importer"

    filepath: StringProperty(subtype='FILE_PATH')
    files: CollectionProperty(type=bpy.types.OperatorFileListElement)
    directory: StringProperty(subtype='DIR_PATH')

    def execute(self, context):
        time = perf_counter()
        for file in self.files:
            filepath = os.path.join(self.directory, file.name)
            
            # collect everything in the folder
            folder = os.path.dirname(filepath)
            for f in os.listdir(folder):
                if f.lower().endswith('.png') or f.lower().endswith('.dds') or f.lower().endswith('.bc7') or f.lower().endswith('.astc'):
                    # load texture
                    image = bpy.data.images.load(os.path.join(folder, f))
                    image.name = f.split('.')[0]
            # import bum
            with open(filepath, 'rb') as f:
                br = BinaryReader(f.read())
                bum = br.read_struct(BUM)
            importBUM(bum, os.path.basename(filepath).split('.')[0])
            
        
        self.report({'INFO'}, f"Imported {len(self.files)} files in {perf_counter() - time:.4f} seconds")
        return {'FINISHED'} 


class LZS_FH_import(bpy.types.FileHandler):
    bl_idname = "LZS_FH_import"
    bl_label = "File handler for LZS files"
    bl_import_operator = "wm.drop_lzs_operator"
    bl_file_extensions = ".lzs"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type == 'VIEW_3D')
    
    def draw():
        pass


class LZA_FH_import(bpy.types.FileHandler):
    bl_idname = "LZA_FH_import"
    bl_label = "File handler for LZA files"
    bl_import_operator = "wm.drop_lza_operator"
    bl_file_extensions = ".lza"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type == 'VIEW_3D')
    
    def draw():
        pass


class BUM_FH_import(bpy.types.FileHandler):
    bl_idname = "BUM_FH_import"
    bl_label = "File handler for BUM files"
    bl_import_operator = "wm.drop_bum_operator"
    bl_file_extensions = ".bum"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll_drop(cls, context):
        return (context.area and context.area.type == 'VIEW_3D')
    
    def draw():
        pass


def importLZS(lzsData, name):
    textures = []
    bumfiles = []
    
    for file in lzsData.files:
        if file.type in (4, 30, 31):
            textures.append(file)
            
        elif file.type == 1:
            bumfiles.append(file)
    
    # load all the textures first
    for texFile in textures:
        tempfilePath = os.path.join(tempfile.gettempdir(), texFile.name)
        with open(tempfilePath, 'wb') as imgFile:
            imgFile.write(texFile.data)
        image = bpy.data.images.load(filepath=tempfilePath)
        image.name = texFile.name.split('.')[0]


    for bumfile in bumfiles:
        # Model / Animation
        br = BinaryReader(bumfile.data)
        bum = br.read_struct(BUM)
        importBUM(bum, bumfile.name)

def importBUM(bum: BUM, name):    
    armatureObj = None
    for bumModel in bum.models:
        bumModel: MODL
        
        # create an armature using nodes
        armatureObj = createArmature(bumModel.nodes, name.split('.')[0], bum.version)
        armatureObj.scale *= bum.scale
        
        # combine material settings with materials before creating the materials
        materialsDict = {mat.name: mat for mat in bumModel.materials}
        for matInfo in bumModel.materialSettings:
            matInfo: MATS
            if matInfo.materialName in materialsDict:
                mat = materialsDict[matInfo.materialName]
                mat: MATR
                mat.samplers = matInfo.samplers
                mat.params = matInfo.params
        
        #create materials first
        for i, mat in enumerate(materialsDict.values()):
            material = bpy.data.materials.new(mat.name)
            
            if mat.layers:
                material = createMaterialAlt(material, mat.layers)
            elif mat.samplers:
                material = createMaterial(material, mat.samplers)
            
            else:
                material = createOutlineMaterial(material, mat)
            
            if len(mat.samplers) == 0 and len(mat.layers) == 0:
                #outline
                materialsDict[mat.name] = [material, i, mat, "outline"]
            else:
                materialsDict[mat.name] = [material, i, mat, "normal"]
        
        materialsList = list(materialsDict.values())
                        
        if  bum.version >= 200:
            for bumMesh in bumModel.meshes:
                bumMesh: MESH
                createMeshBUM2(materialsList, bumMesh, armatureObj, deformBoneList=bumModel.deformBoneList)
        
        else:
            for part in bumModel.parts:
                part: PART
                createMeshBUM1(materialsList, part, armatureObj)
    
    
    if not armatureObj:
        armatureObj = bpy.context.object
    
    if bum.version >= 200:
        for anim in bum.animations:
            anim: ANI3
            createActionBUM2(anim, armatureObj)
    else:
        for anim in bum.animations:
            anim: ANIM
            createAction(anim, armatureObj)
            

def createArmature(nodes, name, version=100):
    bpy.ops.object.add(type='ARMATURE', enter_editmode=True)
    armatureObj = bpy.context.object
    armatureObj.name = f"{name}"
    armature = armatureObj.data
    armature.name = f"{name}"
    armature.display_type = 'STICK'
    #display in front
    armatureObj.show_in_front = True
    
    matrixList = []
    
    for i, node in enumerate(nodes):
        bone = armature.edit_bones.new(node.name)
        
        pos = Vector(node.translation)
        pos = Vector((pos[0], -pos[2], pos[1]))
        bone["original_loc"] = pos
        bone["file_loc"] = node.translation  # Store unconverted for debugging
        
        rot = Quaternion(node.rotation)
        rot = Quaternion((rot[3], rot[0], -rot[2], rot[1]))
        bone["original_rot"] = rot
        bone["file_rot"] = node.rotation  # Store unconverted for debugging
        
        scale = Vector(node.scale)
        bone["original_scale"] = scale
        
        matrix = Matrix.LocRotScale(pos, rot, scale)
        
        if node.parentIndex != -1:
            parentMatrix = matrixList[node.parentIndex]
            matrix = parentMatrix @ matrix
            
            parentBone = armature.edit_bones.get(nodes[node.parentIndex].name)
            if parentBone:
                bone.parent = parentBone
        
        bone.matrix = matrix
        matrixList.append(matrix)
        bone["original_matrix"] = matrix

        # Temporarily set tail - will be adjusted in second pass
        bone.tail = bone.head + Vector((0, 0.1, 0))
        
    bpy.ops.object.mode_set(mode='OBJECT')
    
    return armatureObj


def createMeshBUM1(materialsList, part: PART, armatureObj):
    mesh = bpy.data.meshes.new(part.name)
    meshObj = bpy.data.objects.new(part.name, mesh)
    bpy.context.collection.objects.link(meshObj)
    
    bm = bmesh.new()
    startIndices = {}

    normals_list = []
    uvs_list = []
    colors_list = []
    weights_list = []
    boneIDs_list = []

    vert_count = 0

    # build vertices and faces (ensure lookup table right after creating verts)
    for submesh in part.meshes:
        submesh: MESH
        faceBuffer: DRWA = submesh.faceBuffer
        vb: ARAY = faceBuffer.vertexBuffer
        
        try:
            blenderMaterial, _ , bumMat, matType = materialsList[submesh.materialIndex]
        except IndexError:
            blenderMaterial = None
            matInfo = None
            matType = None
        if blenderMaterial and blenderMaterial.name not in meshObj.data.materials:
            meshObj.data.materials.append(blenderMaterial)
            if matType == "outline":
                # apply outline geometry nodes modifier
                createOutline(meshObj, bumMat)
            
            # get material index
        matIndex = meshObj.data.materials.find(blenderMaterial.name) if blenderMaterial else -1

        positions = vb.vertices["position"]
        vertex_count = len(positions)
        startIndex = startIndices.get(faceBuffer.vertexBufferIndex)

        if startIndex is None:
            startIndex = vert_count
            startIndices[faceBuffer.vertexBufferIndex] = startIndex
            vert_count += vertex_count

            verts = [bm.verts.new((pos[0], -pos[2], pos[1])) for pos in positions]
            #verts = [bm.verts.new((pos[0], pos[1], pos[2])) for pos in positions]
            
            bm.verts.ensure_lookup_table()

            # collect attributes for this vertex range
            if "normals" in vb.vertices.dtype.names:
                normals_list.append(vb.vertices["normals"])
            if "uvs" in vb.vertices.dtype.names:
                uvs_list.append(vb.vertices["uvs"])
            if "colors" in vb.vertices.dtype.names:
                colors_list.append(vb.vertices["colors"].astype(np.float32) / 255.0)
            if "weights" in vb.vertices.dtype.names:
                weights_list.append(vb.vertices["weights"].astype(np.float32) / 255.0)
            if "boneIDs" in vb.vertices.dtype.names:
                boneIDs_list.append(vb.vertices["boneIDs"].astype(np.int32))

        for face in faceBuffer.faces:
            try:
                face_verts = [bm.verts[startIndex + idx] for idx in face]
                f = bm.faces.new(face_verts)
                f.smooth = True
                f.material_index = matIndex
            except ValueError:
                # face already exists
                pass

    bm.faces.ensure_lookup_table()
    bm.to_mesh(mesh)
    bm.free()

    # concatenate attribute arrays once
    normals = np.concatenate(normals_list) if normals_list else np.empty((0, 3), np.float32)
    uvs = np.concatenate(uvs_list) if uvs_list else np.empty((0, 2), np.float32)
    colors = np.concatenate(colors_list) if colors_list else np.empty((0, 4), np.float32)
    weights = np.concatenate(weights_list) if weights_list else np.empty((0, 8), np.float32)
    boneIDs = np.concatenate(boneIDs_list) if boneIDs_list else np.empty((0, 8), np.int32)

    # apply normals if we have per-vertex normals
    if len(normals) == len(mesh.vertices):
        normals[:, [1, 2]] = normals[:, [2, 1]] * np.array([-1, 1])  # swap Y and Z, invert new Y
        mesh.normals_split_custom_set_from_vertices(normals)

    # per-loop data (UVs, vertex-colors) using vertex-index mapping
    loops = mesh.loops
    loopCount = len(loops)
    vertexIndices = np.empty(loopCount, dtype=np.int32)
    loops.foreach_get("vertex_index", vertexIndices)

    if len(uvs) == len(mesh.vertices):
        uvLayer = mesh.uv_layers.new(name="UVMap")
        loopUVs = uvs[vertexIndices]
        loopUVs[:, 1] = 1.0 - loopUVs[:, 1]
        uvLayer.data.foreach_set("uv", loopUVs.flatten())

    if len(colors) == len(mesh.vertices):
        colorLayer = mesh.vertex_colors.new(name="Col")
        loopColors = colors[vertexIndices]
        colorLayer.data.foreach_set("color", loopColors.flatten())

    # parent to armature
    modifier = meshObj.modifiers.new(type='ARMATURE', name='ArmatureMod')
    modifier.object = armatureObj

    # prepare bone names and used bone IDs
    boneNames = [b.name for b in armatureObj.data.bones]  # all bone names
    numBones = len(boneNames)

    # sanitize boneIDs array shape
    if boneIDs.size == 0 or weights.size == 0:
        # no skinning info
        return meshObj

    boneIDs = boneIDs.astype(np.int32)
    weights = weights.astype(np.float32)

    # collect unique bone IDs that are within range [0, numBones-1]
    unique_bids = np.unique(boneIDs)
    valid_bids = [int(b) for b in unique_bids if 0 <= int(b) < numBones]

    # create vertex groups for used bones
    vgs = {bid: meshObj.vertex_groups.new(name=boneNames[bid]) for bid in valid_bids}

    # assign weights: loop per-vertex but only iterate non-zero bone slots
    numVerts = len(mesh.vertices)
    # safety check shapes
    if weights.shape[0] != numVerts or boneIDs.shape[0] != numVerts:
        # mismatched attribute size: best-effort clamp to smallest
        n = min(weights.shape[0], boneIDs.shape[0], numVerts)
    else:
        n = numVerts

    for vIdx in range(n):
        w_row = weights[vIdx]
        b_row = boneIDs[vIdx]
        # indices within this vertex where weight > tiny eps
        nonzero_slots = np.nonzero(w_row > 1e-6)[0]
        if nonzero_slots.size == 0:
            continue
        for slot in nonzero_slots:
            bid = int(b_row[slot])
            wt = float(w_row[slot])
            # add single vertex with its weight
            vgs[bid].add([vIdx], wt, 'REPLACE')

    
    # parent to armature
    meshObj.parent = armatureObj
    
    # transform the object by its parent bone
    '''if part.parent:
        parentBone = armatureObj.data.bones.get(part.parent.name)
        if parentBone:
            # get bone matrix in armature space
            boneMatrix = parentBone.matrix_local
            # apply to mesh object
            meshObj.matrix_world = boneMatrix'''
    
    return meshObj

def createMeshBUM2(materialsList, bumMesh: MESH, armatureObj, deformBoneList=None,):
    mesh = bpy.data.meshes.new(bumMesh.name)
    meshObj = bpy.data.objects.new(bumMesh.name, mesh)
    bpy.context.collection.objects.link(meshObj)
    
    bm = bmesh.new()

    # build vertices and faces (ensure lookup table right after creating verts)
    faceBuffer: DRWA = bumMesh.faceBuffer
    vb: VERT = faceBuffer.vertexBuffer
    
    try:
        blenderMaterial, _ , matInfo, matType = materialsList[bumMesh.materialIndex]
    except IndexError:
        blenderMaterial = None
        matInfo = None
        matType = None
    if blenderMaterial and blenderMaterial.name not in meshObj.data.materials:
        meshObj.data.materials.append(blenderMaterial)
        '''if matType == "outline":
            # apply outline geometry nodes modifier
            createOutline(meshObj, matInfo)'''
        
    # get material index
    matIndex = meshObj.data.materials.find(blenderMaterial.name) if blenderMaterial else -1

    positions = vb.vertices["position"]

    verts = [bm.verts.new((pos[0], -pos[2], pos[1])) for pos in positions]
    bm.verts.ensure_lookup_table()


    for face in faceBuffer.faces:
        try:
            face_verts = [bm.verts[idx] for idx in face]
            f = bm.faces.new(face_verts)
            f.smooth = True
            f.material_index = matIndex
        except ValueError:
            # face already exists
            pass

    bm.faces.ensure_lookup_table()
    bm.to_mesh(mesh)
    bm.free()

    # concatenate attribute arrays once
    normals = vb.vertices["normals"] if "normals" in vb.vertices.dtype.names else np.empty((0, 3), np.float32)
    uv1 = vb.vertices["UV0"] if "UV0" in vb.vertices.dtype.names else np.empty((0, 2), np.float32)
    uv2 = vb.vertices["UV1"] if "UV1" in vb.vertices.dtype.names else np.empty((0, 2), np.float32)
    colors = vb.vertices["colors"].astype(np.float32) / 255.0 if "colors" in vb.vertices.dtype.names else np.empty((0, 4), np.float32)
    weights = vb.vertices["weights"].astype(np.float32) / 255.0 if "weights" in vb.vertices.dtype.names else np.empty((0, 8), np.float32)
    boneIDs = vb.vertices["boneIDs"].astype(np.int32) if "boneIDs" in vb.vertices.dtype.names else np.empty((0, 8), np.int32)

    # apply normals if we have per-vertex normals
    if len(normals) == len(mesh.vertices):
        normals[:, [1, 2]] = normals[:, [2, 1]] * np.array([-1, 1])  # swap Y and Z, invert new Y
        mesh.normals_split_custom_set_from_vertices(normals)

    # per-loop data (UVs, vertex-colors) using vertex-index mapping
    loops = mesh.loops
    loopCount = len(loops)
    vertexIndices = np.empty(loopCount, dtype=np.int32)
    loops.foreach_get("vertex_index", vertexIndices)

    if len(uv1) == len(mesh.vertices):
        uvLayer = mesh.uv_layers.new(name="UVMap")
        loopUVs = uv1[vertexIndices]
        loopUVs[:, 1] = 1.0 - loopUVs[:, 1]
        uvLayer.data.foreach_set("uv", loopUVs.flatten())

    if len(uv2) == len(mesh.vertices):
        uvLayer2 = mesh.uv_layers.new(name="UVMap2")
        loopUVs2 = uv2[vertexIndices]
        loopUVs2[:, 1] = 1.0 - loopUVs2[:, 1]
        uvLayer2.data.foreach_set("uv", loopUVs2.flatten())

    if len(colors) == len(mesh.vertices):
        colorLayer = mesh.vertex_colors.new(name="Col")
        loopColors = colors[vertexIndices]
        colorLayer.data.foreach_set("color", loopColors.flatten())

    # parent to armature
    modifier = meshObj.modifiers.new(type='ARMATURE', name='ArmatureMod')
    modifier.object = armatureObj

    # prepare bone names and used bone IDs
    boneNames = [b.name for b in armatureObj.data.bones]  # all bone names

    # sanitize boneIDs array shape
    if boneIDs.size == 0 or weights.size == 0:
        # no skinning info
        return meshObj

    boneIDs = boneIDs.astype(np.int32)
    weights = weights.astype(np.float32)

    # create vertex groups for used bones
    unique_bids = [deformBoneList.indices[i] for i in bumMesh.boneList.boneIDs] if deformBoneList else bumMesh.boneList.boneIDs
    
    vgs = {i: meshObj.vertex_groups.new(name=boneNames[bid]) for i, bid in zip(bumMesh.boneList.boneIDs, unique_bids)}
    # assign weights: loop per-vertex but only iterate non-zero bone slots
    numVerts = len(mesh.vertices)
    # safety check shapes
    if weights.shape[0] != numVerts or boneIDs.shape[0] != numVerts:
        # mismatched attribute size: best-effort clamp to smallest
        n = min(weights.shape[0], boneIDs.shape[0], numVerts)
    else:
        n = numVerts

    for vIdx in range(n):
        w_row = weights[vIdx]
        b_row = boneIDs[vIdx]
        # indices within this vertex where weight > tiny eps
        nonzero_slots = np.nonzero(w_row > 1e-6)[0]
        if nonzero_slots.size == 0:
            continue
        for slot in nonzero_slots:
            bid = int(b_row[slot])
            wt = float(w_row[slot])
            # add single vertex with its weight
            vgs[bid].add([vIdx], wt, 'REPLACE')

    
    # parent to armature
    meshObj.parent = armatureObj
    
    return meshObj

def createBBOX(min, max):
    # Create a cube mesh representing the bounding box
    bpy.ops.mesh.primitive_cube_add(size=1, location=((min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2))
    bboxObj = bpy.context.object
    bboxObj.scale = ((max[0] - min[0]) / 2, (max[1] - min[1]) / 2, (max[2] - min[2]) / 2)
    return bboxObj


def createMaterial(mat, samplers):
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Clear existing nodes
    for node in nodes:
        nodes.remove(node)

    # --- Create nodes ---
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)

    principled = nodes.new("ShaderNodeBsdfDiffuse")
    principled.location = (0, 0)

    # --- Link nodes ---
    links.new(principled.outputs["BSDF"], output.inputs["Surface"])

    # Process samplers
    for sampler in samplers:
        if sampler.samplerName.startswith("Diffuse"):
            tex_node = nodes.new("ShaderNodeTexImage")
            tex_node.location = (-400, 0)
            # Load image
            image = bpy.data.images.get(sampler.textureName)
            if image:
                tex_node.image = image
                
            links.new(tex_node.outputs["Color"], principled.inputs[0])
        
    return mat


def createMaterialAlt(mat, layers):
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Clear existing nodes
    for node in nodes:
        nodes.remove(node)

    # --- Create nodes ---
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)

    diffuse = nodes.new("ShaderNodeBsdfDiffuse")
    diffuse.location = (0, 0)

    # --- Link nodes ---
    links.new(diffuse.outputs["BSDF"], output.inputs["Surface"])

    layer = layers[0]
    tex_node = nodes.new("ShaderNodeTexImage")
    tex_node.location = (-400, 0)
    
    for image in bpy.data.images:
        print(image.name)
    
    image = bpy.data.images.get(layer.textureName)
    

    if image:
        tex_node.image = image
        
    links.new(tex_node.outputs["Color"], diffuse.inputs[0])
        
    return mat


def createOutline(obj, matInfo=None):
    
    node_group = bpy.data.node_groups.get("bumOutlineNode")
    
    if not node_group:
        # Create new geometry node group
        node_group = bpy.data.node_groups.new("bumOutlineNode", 'GeometryNodeTree')

        interface = node_group.interface
        # Create input and output nodes
        group_input = node_group.nodes.new("NodeGroupInput")
        group_input.location = (-800, 0)
        group_output = node_group.nodes.new("NodeGroupOutput")
        group_output.location = (600, 0)

        # Define group inputs
        interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
        interface.new_socket(name="LineWidth", in_out='INPUT', socket_type='NodeSocketFloat')
        interface.new_socket(name="LineDepthOffset", in_out='INPUT', socket_type='NodeSocketFloat')

        # Define group outputs
        interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')


        # --- Create Nodes ---
        normal = node_group.nodes.new("GeometryNodeInputNormal")
        normal.location = (-600, -200)

        multiply = node_group.nodes.new("ShaderNodeVectorMath")
        multiply.location = (-400, -200)
        multiply.operation = 'MULTIPLY'

        combine_xyz = node_group.nodes.new("ShaderNodeCombineXYZ")
        combine_xyz.location = (-400, -400)
        combine_xyz.inputs[0].default_value = 0.0
        combine_xyz.inputs[1].default_value = 0.0
        combine_xyz.inputs[2].default_value = 0.0

        position = node_group.nodes.new("GeometryNodeInputPosition")
        position.location = (-600, 100)

        add = node_group.nodes.new("ShaderNodeVectorMath")
        add.location = (-200, 0)
        add.operation = 'ADD'

        merge = node_group.nodes.new("GeometryNodeMergeByDistance")
        merge.location = (-200, 300)
        merge.inputs[2].default_value = 0.0001  # distance

        set_pos = node_group.nodes.new("GeometryNodeSetPosition")
        set_pos.location = (200, 0)

        # --- Create Links ---
        links = node_group.links

        # Group Input geometry to Merge by Distance
        links.new(group_input.outputs["Geometry"], merge.inputs["Geometry"])
        # Merge to Set Position geometry input
        links.new(merge.outputs["Geometry"], set_pos.inputs["Geometry"])

        # Position to Add
        links.new(position.outputs["Position"], add.inputs[0])
        # Multiply to Add
        links.new(multiply.outputs["Vector"], add.inputs[1])

        # Add to Set Position Position
        links.new(add.outputs["Vector"], set_pos.inputs["Position"])

        # Normal to Multiply
        links.new(normal.outputs["Normal"], multiply.inputs[0])
        # Group Input LineWidth to Multiply second input
        links.new(group_input.outputs["LineWidth"], multiply.inputs[1])

        # Combine XYZ z input from LineDepthOffset
        links.new(group_input.outputs["LineDepthOffset"], combine_xyz.inputs["Z"])
        
        # Combine XYZ to offset in set position
        links.new(combine_xyz.outputs["Vector"], set_pos.inputs["Offset"])

        # Group Output
        links.new(set_pos.outputs["Geometry"], group_output.inputs["Geometry"])
        

    # apply to object
    if obj and obj.type == 'MESH':
        mod = obj.modifiers.new("", "NODES")
        mod.node_group = node_group
        if matInfo:
            # set default values from matInfo
            for param in matInfo.params:
                if param.name == "LineWidth":
                    mod["Socket_1"] = param.values[0]
                elif param.name == "LineDepthOffset":
                    mod["Socket_2"] = param.values[0]


def createOutlineMaterial(mat, bumMat):
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Clear existing nodes
    for node in nodes:
        nodes.remove(node)

    # --- Create nodes ---
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (400, 0)

    mix_shader = nodes.new("ShaderNodeMixShader")
    mix_shader.location = (200, 0)

    transparent = nodes.new("ShaderNodeBsdfTransparent")
    transparent.location = (-200, 100)

    geometry = nodes.new("ShaderNodeNewGeometry")
    geometry.location = (-400, 0)

    # Create LineColor input using RGB node
    line_color = nodes.new("ShaderNodeRGB")
    line_color.label = "LineColor"
    line_color.location = (-600, -200)
    line_color.outputs[0].default_value = (0.0, 0.0, 0.0, 1.0)  # default: black

    for param in bumMat.params:
        if param.name == "LineColor":
            line_color.outputs[0].default_value = [param.values[0], param.values[1], param.values[2], 1.0]
            break

    # --- Add Gamma node ---
    gamma_node = nodes.new("ShaderNodeGamma")
    gamma_node.location = (-400, -200)
    gamma_node.inputs["Gamma"].default_value = 2.2

    # --- Link nodes ---
    links.new(geometry.outputs["Backfacing"], mix_shader.inputs["Fac"])
    links.new(transparent.outputs["BSDF"], mix_shader.inputs[1])
    links.new(line_color.outputs["Color"], gamma_node.inputs["Color"])
    links.new(gamma_node.outputs["Color"], mix_shader.inputs[2])
    links.new(mix_shader.outputs["Shader"], output.inputs["Surface"])

    mat.blend_method = 'BLEND'
    
    return mat


def createAction(anim: ANIM, armatureObj):
    motion: MOTI = anim.motions[0]
    action = bpy.data.actions.new(name=motion.name)
    
    #create anim data
    armatureObj.animation_data_create()
    armatureObj.animation_data.action = action
    
    #set frame range
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = int(motion.length)
    
    #set frame rate
    bpy.context.scene.render.fps = 30
    
    #check for blender version
    if bpy.app.version >= (4, 4, 0):
    
        #check if an action slot exists for this armature
        slot = armatureObj.animation_data.action.slots.get(f"OB{armatureObj.name}")

        if not slot:
            slot = armatureObj.animation_data.action.slots.new(id_type='OBJECT', name=armatureObj.name)
        
        armatureObj.animation_data.action_slot = slot
    
    fcurves = action.fcurves
    
    
    for curve in motion.curves:
        curve: Curve
        bone = armatureObj.data.bones.get(curve.name)
        if not bone:
            continue # for now skip missing bones, we may add frames as is later
        
        
        boneMatrix = bone.matrix_local
        
        if bone.parent:
            parentBone = armatureObj.data.bones.get(bone.parent.name)
            parentMatrix = Matrix(parentBone["original_matrix"]) if parentBone.get("original_matrix") else parentBone.matrix_local
            boneMatrix = parentMatrix.inverted() @ boneMatrix
        
        loc, rot, scale = boneMatrix.decompose()
        
        dataPath = f'pose.bones["{curve.name}"].{curve.type}'
        dataTypes = {"vector4": 4, "vector3": 3, "vector2": 2, "quaternion": 4, "integer": 1}
        
        valueCount = dataTypes.get(curve.dataType, 0)
        
        
        if curve.type == 'location':
            # convert to local location
            curve.frames["values"][:, [1, 2]] = curve.frames["values"][:, [2, 1]] * np.array([-1, 1])# * bumScale # swap Y and Z, invert new Y
            curve.frames["values"] -= np.array([loc.x, loc.y, loc.z])
            
            
        elif curve.type.startswith('rotation'):
            # convert to local rotation we'll just assume quaternion
            bindRotInv = np.array([[rot.w, -rot.x, -rot.y, -rot.z]], dtype=np.float32)
            
            rotFrames = curve.frames["values"][:, [3, 0, 2, 1]]
            rotFrames = quat_mul_np(bindRotInv, rotFrames)
            rotFrames[:, 2] *= -1  # invert Y
            curve.frames["values"] = rotFrames
            
            
        elif curve.type == 'scale':
            curve.frames["values"] /= np.array([scale.x, scale.y, scale.z])
            
        else:
            continue
        
        frames = curve.frames["frame"]
        
        for i in range(valueCount):
            fcurve = fcurves.new(data_path=dataPath, index=i)
            keyframePoints = fcurve.keyframe_points
            
            values = curve.frames["values"][:, i]
            # combine a flattened array of (frame, value) pairs
            keyframe_data = np.empty((len(frames), 2), dtype=np.float32)
            keyframe_data[:, 0] = frames
            keyframe_data[:, 1] = values
            keyframePoints.add(len(frames))
            keyframePoints.foreach_set("co", keyframe_data.flatten())
        
        if curve.interpolation == 2:  # linear
            for fcurve in action.fcurves:
                for keyframePoint in fcurve.keyframe_points:
                    keyframePoint.interpolation = 'LINEAR'


def createActionBUM2(anim: ANI3, armatureObj, bumScale=1.0):

    motion: MOTI = anim.motions[0]
    action = bpy.data.actions.new(name=motion.name)
    
    #create anim data
    armatureObj.animation_data_create()
    armatureObj.animation_data.action = action
    
    #set frame range
    bpy.context.scene.frame_start = 0
    bpy.context.scene.frame_end = int(motion.length)
    
    #set frame rate
    bpy.context.scene.render.fps = 30
    
    #check for blender version
    if bpy.app.version >= (4, 4, 0):
    
        #check if an action slot exists for this armature
        slot = armatureObj.animation_data.action.slots.get(f"OB{armatureObj.name}")

        if not slot:
            slot = armatureObj.animation_data.action.slots.new(id_type='OBJECT', name=armatureObj.name)
        
        armatureObj.animation_data.action_slot = slot
    
    fcurves = action.fcurves
    
    
    for curve in motion.curves:
        curve: Curve
        bone = armatureObj.data.bones.get(curve.name)
        if not bone:
            continue
        
        # Get bind pose matrix (in armature space)
        bindMatrix = Matrix(bone["original_matrix"])
        blenderMatrix = bone.matrix_local
        
        # Get parent's bind matrix to make the bone transform parent-relative
        if bone.parent:
            parentBindMatrix = Matrix(bone.parent["original_matrix"])
            parentBlenderMatrix = bone.parent.matrix_local
            # Local bind = parent_bind^-1 * bind
            bindMatrix = parentBindMatrix.inverted() @ bindMatrix
            blenderMatrix = parentBlenderMatrix.inverted() @ blenderMatrix

        
        # Decompose to get bind pose components
        bindLoc, bindRot, bindScale = bindMatrix.decompose()
        
        dataPath = f'pose.bones["{curve.name}"].{curve.type}'
        dataTypes = {"vector4": 4, "vector3": 3, "vector2": 2, "quaternion": 4, "integer": 1}
        
        valueCount = dataTypes.get(curve.dataType, 0)
        
        if curve.type == 'location':
            # XZY to XYZ
            curve.frames["values"][:, [1, 2]] = curve.frames["values"][:, [2, 1]] * np.array([-1, 1])

            # delta from bind pose
            curve.frames["values"] -= np.array([bindLoc.x, bindLoc.y, bindLoc.z])
            curve.frames["values"][:, 2] *= -1  # invert Y
        
        elif curve.type.startswith('rotation'):
            # Animation data is (X,Y,Z,W), convert to (W,X,Y,Z)
            rotFrames = curve.frames["values"][:, [3, 0, 2, 1]]
            # Apply coordinate conversion: negate Y component
            rotFrames[:, 2] *= -1
            
            # Apply inverse bind rotation to get animation delta
            bindRotInv = np.array([[bindRot.w, -bindRot.x, -bindRot.y, -bindRot.z]], dtype=np.float32)
            rotFrames = quat_mul_np(bindRotInv, rotFrames)
            
            curve.frames["values"] = rotFrames
        
        elif curve.type == 'scale':
            # Divide by bind pose scale to get animation delta
            curve.frames["values"] /= np.array([bindScale.x, bindScale.y, bindScale.z])

        else:
            continue
        
        frames = curve.frames["frame"]
        
        for i in range(valueCount):
            fcurve = fcurves.new(data_path=dataPath, index=i)
            keyframePoints = fcurve.keyframe_points
            
            values = curve.frames["values"][:, i]
            # combine a flattened array of (frame, value) pairs
            keyframe_data = np.empty((len(frames), 2), dtype=np.float32)
            keyframe_data[:, 0] = frames
            keyframe_data[:, 1] = values
            keyframePoints.add(len(frames))
            keyframePoints.foreach_set("co", keyframe_data.flatten())
        
        if curve.interpolation == 1:  # linear
            for fcurve in action.fcurves:
                for keyframePoint in fcurve.keyframe_points:
                    keyframePoint.interpolation = 'LINEAR'


def quat_mul_np(q1, q2):
    # q1, q2 shape: (N,4)
    w1, x1, y1, z1 = q1.T
    w2, x2, y2, z2 = q2.T
    return np.column_stack((
        w1*w2 - x1*x2 - y1*y2 - z1*z2,
        w1*x2 + x1*w2 + y1*z2 - z1*y2,
        w1*y2 - x1*z2 + y1*w2 + z1*x2,
        w1*z2 + x1*y2 - y1*x2 + z1*w2
    ))



def menu_func_import(self, context):
    self.layout.operator(LZS_IMPORTER_OT_IMPORT.bl_idname,
                        text='LZS Container Importer (.lzs)',
                        icon='IMPORT')

def register():
    bpy.utils.register_class(LZS_IMPORTER_OT_IMPORT)
    bpy.utils.register_class(dropLZSOperator)
    bpy.utils.register_class(LZS_FH_import)
    bpy.utils.register_class(dropLZAOperator)
    bpy.utils.register_class(LZA_FH_import)
    bpy.utils.register_class(dropBUMOperator)
    bpy.utils.register_class(BUM_FH_import)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    
def unregister():
    bpy.utils.unregister_class(LZS_IMPORTER_OT_IMPORT)
    bpy.utils.unregister_class(dropLZSOperator)
    bpy.utils.unregister_class(LZS_FH_import)
    bpy.utils.unregister_class(dropLZAOperator)
    bpy.utils.unregister_class(LZA_FH_import)
    bpy.utils.unregister_class(dropBUMOperator)
    bpy.utils.unregister_class(BUM_FH_import)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)