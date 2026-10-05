using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>Exports a non-destructive, current-pose snapshot for the bundled Blender importer.</summary>
public static class BlenderModelExporter
{
    public enum Part { Exclude, Clothing, Body }
    public sealed class Selection
    {
        public Renderer Renderer;
        public int Submesh;
        public Part Part;
        public string Label;
    }

    [Serializable] public sealed class Snapshot
    {
        public int version = 1;
        public string name;
        public string pose = "Current pose becomes the armature rest pose";
        public List<BoneData> bones = new List<BoneData>();
        public List<MeshData> meshes = new List<MeshData>();
        public List<MaterialData> materials = new List<MaterialData>();
        public List<string> warnings = new List<string>();
    }
    [Serializable] public sealed class BoneData { public string id, name, parent; public float[] matrix; }
    [Serializable] public sealed class Vec { public float x, y, z, w; }
    [Serializable] public sealed class Influence { public int vertex; public string bone; public float weight; }
    [Serializable] public sealed class Faces { public string part; public int material; public int[] triangles; }
    [Serializable] public sealed class Shape { public string name; public float weight; public Vec[] deltas; }
    [Serializable] public sealed class MeshData
    {
        public string name;
        public Vec[] vertices, normals, colors;
        public List<UvData> uvs = new List<UvData>();
        public List<Influence> weights = new List<Influence>();
        public List<Faces> faces = new List<Faces>();
        public List<Shape> shapes = new List<Shape>();
    }
    [Serializable] public sealed class UvData { public int channel; public Vec[] values; }
    [Serializable] public sealed class Property { public string name, type, texture; public float[] value, scale, offset; public bool srgb; }
    [Serializable] public sealed class MaterialData { public string name, shader; public string[] keywords; public int renderQueue; public List<Property> properties = new List<Property>(); }

    public static List<Selection> GetSelections(UmaContainerCharacter container)
    {
        var result = new List<Selection>();
        foreach (var renderer in container.GetComponentsInChildren<Renderer>())
        {
            var mesh = GetMesh(renderer);
            if (!mesh || !renderer.enabled) continue;
            var mats = renderer.sharedMaterials;
            for (int i = 0; i < mesh.subMeshCount; i++)
            {
                var mat = mats.Length == 0 ? null : mats[Math.Min(i, mats.Length - 1)];
                string text = (renderer.name + " " + (mat ? mat.name : "")).ToLowerInvariant();
                // Deliberately do not guess that every bdy material is clothing: many contain skin too.
                bool body = new[] { "m_face", "m_mouth", "m_eye", "m_mayu", "m_hair", "m_tail" }.Contains(renderer.name.ToLowerInvariant())
                    || text.Contains("skin") || text.Contains("nude") || text.Contains("naked");
                bool clothes = text.Contains("cloth") || text.Contains("dress") || text.Contains("skirt") || text.Contains("costume");
                result.Add(new Selection { Renderer = renderer, Submesh = i,
                    Part = body ? Part.Body : clothes ? Part.Clothing : Part.Exclude,
                    Label = renderer.name + " / " + i + " / " + (mat ? mat.name : "no material") });
            }
        }
        return result;
    }

    static Mesh GetMesh(Renderer renderer)
    {
        if (renderer is SkinnedMeshRenderer skin) return skin.sharedMesh;
        var filter = renderer is MeshRenderer ? renderer.GetComponent<MeshFilter>() : null;
        return filter ? filter.sharedMesh : null;
    }
    static Vec V(Vector3 v) { return new Vec { x = v.x, y = v.y, z = v.z }; }
    static Vec V4(Vector4 v) { return new Vec { x = v.x, y = v.y, z = v.z, w = v.w }; }
    static float[] Matrix(Matrix4x4 m)
    {
        var a = new float[16];
        for (int r = 0; r < 4; r++) for (int c = 0; c < 4; c++) a[r * 4 + c] = m[r, c];
        return a;
    }

    public static string Export(UmaContainerCharacter container, List<Selection> selections, string parentDirectory)
    {
        if (!container) throw new ArgumentException("Load a character first.");
        var selected = selections.Where(s => s.Part != Part.Exclude && s.Renderer).ToList();
        if (selected.Count == 0) throw new ArgumentException("Assign at least one submesh to Clothing or Body.");
        string directory = Path.Combine(parentDirectory, "UmaBlender_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + "_" + Guid.NewGuid().ToString("N").Substring(0, 6));
        Directory.CreateDirectory(Path.Combine(directory, "textures"));
        var snapshot = new Snapshot { name = container.name };
        snapshot.warnings.Add("Body contains only existing source surfaces. Missing skin under clothing is not reconstructed. Mixed skin/clothing within one material requires editing in Blender.");
        var rootInverse = container.transform.worldToLocalMatrix;
        var bones = new List<Transform>();
        Action<Transform> addBone = null;
        addBone = bone =>
        {
            if (!bone || bone == container.transform || bones.Contains(bone)) return;
            if (!bone.IsChildOf(container.transform)) throw new InvalidOperationException("Bone outside character: " + bone.name);
            addBone(bone.parent);
            bones.Add(bone);
        };
        foreach (var renderer in selected.Select(s => s.Renderer).Distinct())
        {
            addBone(renderer.transform);
            if (renderer is SkinnedMeshRenderer skin) foreach (var bone in skin.bones) addBone(bone);
        }
        var ids = bones.Select((b, i) => new { b, id = "b" + i }).ToDictionary(x => x.b, x => x.id);
        foreach (var bone in bones)
            snapshot.bones.Add(new BoneData { id = ids[bone], name = bone.name,
                parent = bone.parent && ids.ContainsKey(bone.parent) ? ids[bone.parent] : null,
                matrix = Matrix(rootInverse * bone.localToWorldMatrix) });
        var materialIds = new Dictionary<Material, int>();
        var texturePaths = new Dictionary<Texture, string>();
        foreach (var renderer in selected.Select(s => s.Renderer).Distinct())
        {
            var source = GetMesh(renderer);
            Mesh readable = source;
            var data = new MeshData { name = renderer.name };
            var transform = rootInverse * renderer.transform.localToWorldMatrix;
            var skin = renderer as SkinnedMeshRenderer;
            var baked = skin ? new Mesh() : null;
            try
            {
                if (!source.isReadable) readable = CopyGpuGeometry(source);
                if (skin) skin.BakeMesh(baked, false);
                var mesh = skin ? baked : readable;
                data.vertices = mesh.vertices.Select(v => V(transform.MultiplyPoint3x4(v))).ToArray();
                var normalMatrix = transform.inverse.transpose;
                data.normals = mesh.normals.Select(n => V(normalMatrix.MultiplyVector(n).normalized)).ToArray();
                data.colors = readable.colors.Select(c => new Vec { x = c.r, y = c.g, z = c.b, w = c.a }).ToArray();
                for (int channel = 0; channel < 8; channel++)
                {
                    var uv = new List<Vector4>(); readable.GetUVs(channel, uv);
                    if (uv.Count > 0) data.uvs.Add(new UvData { channel = channel, values = uv.Select(V4).ToArray() });
                }
                var vertexMatrices = new Matrix4x4[source.vertexCount];
                if (skin)
                {
                    // These arrays are mesh-owned views (Allocator.None), not disposable allocations.
                    var counts = source.GetBonesPerVertex();
                    var weights = source.GetAllBoneWeights();
                    {
                        var bindposes = source.bindposes;
                        var skinBones = skin.bones;
                        int cursor = 0;
                        for (int v = 0; v < source.vertexCount; v++)
                        {
                            int influenceCount = counts.Length == 0 ? 0 : counts[v];
                            for (int w = 0; w < influenceCount; w++)
                            {
                                var weight = weights[cursor++];
                                if (weight.weight <= 0) continue;
                                int index = weight.boneIndex;
                                if (index >= skinBones.Length || index >= bindposes.Length || !skinBones[index])
                                    throw new InvalidOperationException("Invalid bone binding in " + renderer.name);
                                data.weights.Add(new Influence { vertex = v, bone = ids[skinBones[index]], weight = weight.weight });
                                var m = rootInverse * skinBones[index].localToWorldMatrix * bindposes[index];
                                for (int k = 0; k < 16; k++) vertexMatrices[v][k] += m[k] * weight.weight;
                            }
                            if (influenceCount == 0)
                            {
                                vertexMatrices[v] = transform;
                                data.weights.Add(new Influence { vertex = v, bone = ids[renderer.transform], weight = 1 });
                            }
                        }
                    }
                }
                else
                    for (int v = 0; v < source.vertexCount; v++)
                    {
                        vertexMatrices[v] = transform;
                        data.weights.Add(new Influence { vertex = v, bone = ids[renderer.transform], weight = 1 });
                    }
                // Preserve source shape keys without altering renderer weights or sharedMesh.
                for (int shape = 0; shape < source.blendShapeCount; shape++)
                {
                    int frame = source.GetBlendShapeFrameCount(shape) - 1;
                    float frameWeight = source.GetBlendShapeFrameWeight(shape, frame);
                    if (Mathf.Abs(frameWeight) < 0.00001f) continue;
                    var deltas = new Vector3[source.vertexCount];
                    source.GetBlendShapeFrameVertices(shape, frame, deltas, null, null);
                    data.shapes.Add(new Shape { name = source.GetBlendShapeName(shape),
                        weight = skin ? skin.GetBlendShapeWeight(shape) / frameWeight : 0,
                        deltas = deltas.Select((d, v) => V(vertexMatrices[v].MultiplyVector(d))).ToArray() });
                    if (source.GetBlendShapeFrameCount(shape) > 1)
                        snapshot.warnings.Add(renderer.name + ": multi-frame shape " + source.GetBlendShapeName(shape) + " uses its final frame.");
                }
                var mats = renderer.sharedMaterials;
                foreach (var choice in selected.Where(s => s.Renderer == renderer))
                {
                    if (readable.GetTopology(choice.Submesh) != MeshTopology.Triangles)
                        throw new InvalidOperationException("Only triangle meshes are supported: " + choice.Label);
                    Material mat = mats.Length == 0 ? null : mats[Math.Min(choice.Submesh, mats.Length - 1)];
                    int matIndex = -1;
                    if (mat && !materialIds.TryGetValue(mat, out matIndex))
                    {
                        matIndex = snapshot.materials.Count; materialIds.Add(mat, matIndex);
                        snapshot.materials.Add(ReadMaterial(mat, directory, texturePaths, snapshot.warnings));
                    }
                    data.faces.Add(new Faces { part = choice.Part.ToString().ToLowerInvariant(), material = matIndex, triangles = readable.GetTriangles(choice.Submesh) });
                }
                snapshot.meshes.Add(data);
            }
            finally
            {
                if (baked) UnityEngine.Object.Destroy(baked);
                if (readable != source) UnityEngine.Object.Destroy(readable);
            }
        }
        string script = Path.Combine(Application.streamingAssetsPath, "Blender", "uma_blender_import.py");
        if (!File.Exists(script)) throw new FileNotFoundException("Bundled Blender importer is missing.", script);
        File.Copy(script, Path.Combine(directory, "uma_blender_import.py"));
        File.WriteAllText(Path.Combine(directory, "model.uma.json"), JsonUtility.ToJson(snapshot, true));
        File.WriteAllText(Path.Combine(directory, "README.txt"),
            "Run: blender --background --factory-startup --python uma_blender_import.py -- model.uma.json --split\n" +
            "Produces clothing.blend and body.blend with packed textures and armature.\n" + string.Join("\n", snapshot.warnings));
        return directory;
    }

    // Geometry readback retains every vertex stream and exact submesh descriptors.
    // Skin weights/bindposes and morph data are read from the original mesh separately.
    public static Mesh CopyGpuGeometry(Mesh source)
    {
        var copy = new Mesh { name = source.name + "_export_copy", indexFormat = source.indexFormat };
        try
        {
            copy.SetVertexBufferParams(source.vertexCount, source.GetVertexAttributes());
            for (int stream = 0; stream < source.vertexBufferCount; stream++)
                using (var buffer = source.GetVertexBuffer(stream))
                {
                    var bytes = new byte[buffer.count * buffer.stride];
                    buffer.GetData(bytes);
                    copy.SetVertexBufferData(bytes, 0, 0, bytes.Length, stream);
                }
            using (var buffer = source.GetIndexBuffer())
            {
                var bytes = new byte[buffer.count * buffer.stride];
                buffer.GetData(bytes);
                copy.SetIndexBufferParams(buffer.count, source.indexFormat);
                copy.SetIndexBufferData(bytes, 0, 0, bytes.Length);
            }
            copy.subMeshCount = source.subMeshCount;
            for (int i = 0; i < source.subMeshCount; i++)
                copy.SetSubMesh(i, source.GetSubMesh(i), MeshUpdateFlags.DontRecalculateBounds);
            copy.bounds = source.bounds;
            return copy;
        }
        catch { UnityEngine.Object.Destroy(copy); throw; }
    }

    static MaterialData ReadMaterial(Material mat, string directory, Dictionary<Texture, string> textures, List<string> warnings)
    {
        var data = new MaterialData { name = mat.name, shader = mat.shader.name, keywords = mat.shaderKeywords, renderQueue = mat.renderQueue };
        var shader = mat.shader;
        for (int i = 0; i < shader.GetPropertyCount(); i++)
        {
            string name = shader.GetPropertyName(i);
            var type = shader.GetPropertyType(i);
            var p = new Property { name = name, type = type.ToString() };
            switch (type)
            {
                case ShaderPropertyType.Color:
                    var c = mat.GetColor(name); p.value = new[] { c.r, c.g, c.b, c.a }; break;
                case ShaderPropertyType.Vector:
                    var v = mat.GetVector(name); p.value = new[] { v.x, v.y, v.z, v.w }; break;
                case ShaderPropertyType.Float: case ShaderPropertyType.Range:
                    p.value = new[] { mat.GetFloat(name) }; break;
                case ShaderPropertyType.Int:
                    p.value = new[] { (float)mat.GetInteger(name) }; break;
                case ShaderPropertyType.Texture:
                    var tex = mat.GetTexture(name);
                    var scale = mat.GetTextureScale(name); var offset = mat.GetTextureOffset(name);
                    p.scale = new[] { scale.x, scale.y }; p.offset = new[] { offset.x, offset.y };
                    if (tex && (tex is Texture2D || tex is RenderTexture))
                    {
                        p.srgb = tex.isDataSRGB;
                        if (!textures.TryGetValue(tex, out p.texture))
                        {
                            p.texture = "textures/tex_" + textures.Count.ToString("D4") + ".png";
                            textures.Add(tex, p.texture);
                            SaveTexture(tex, Path.Combine(directory, p.texture));
                        }
                    }
                    else if (tex) warnings.Add("Unsupported texture type for " + mat.name + "/" + name);
                    break;
            }
            data.properties.Add(p);
        }
        return data;
    }

    static void SaveTexture(Texture source, string path)
    {
        var previous = RenderTexture.active;
        bool previousSrgbWrite = GL.sRGBWrite;
        var rt = RenderTexture.GetTemporary(source.width, source.height, 0, RenderTextureFormat.ARGB32,
            source.isDataSRGB ? RenderTextureReadWrite.sRGB : RenderTextureReadWrite.Linear);
        Texture2D readable = null;
        try
        {
            GL.sRGBWrite = source.isDataSRGB && QualitySettings.activeColorSpace == ColorSpace.Linear;
            Graphics.Blit(source, rt); RenderTexture.active = rt;
            readable = new Texture2D(source.width, source.height, TextureFormat.RGBA32, false, !source.isDataSRGB);
            readable.ReadPixels(new Rect(0, 0, source.width, source.height), 0, 0); readable.Apply();
            File.WriteAllBytes(path, readable.EncodeToPNG());
        }
        finally
        {
            RenderTexture.active = previous; GL.sRGBWrite = previousSrgbWrite; RenderTexture.ReleaseTemporary(rt);
            if (readable) UnityEngine.Object.Destroy(readable);
        }
    }
}
