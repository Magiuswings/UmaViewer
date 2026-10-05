using System;
using System.Collections.Generic;
using System.IO;
using Unity.Collections;
using UnityEditor;
using UnityEngine;
using UnityEngine.Rendering;

/// <summary>Run in Unity with a graphics device. Creates a synthetic rig, no game data required.</summary>
public static class BlenderExportSmokeTest
{
    [MenuItem("UmaViewer/Tests/Blender export snapshot")]
    public static void Run()
    {
        var root = new GameObject("ExporterSmokeTest");
        var mesh = new Mesh { name = "TwoStreamsTwoParts" };
        var material = new Material(Shader.Find("Unlit/Texture"));
        var texture = new Texture2D(2, 2, TextureFormat.RGBA32, false);
        try
        {
            var container = root.AddComponent<UmaContainerCharacter>();
            var bone = new GameObject("Hip").transform; bone.SetParent(root.transform);
            var renderer = new GameObject("M_Body").AddComponent<SkinnedMeshRenderer>();
            renderer.transform.SetParent(root.transform);
            mesh.SetVertexBufferParams(6,
                new VertexAttributeDescriptor(VertexAttribute.Position, VertexAttributeFormat.Float32, 3, 0),
                new VertexAttributeDescriptor(VertexAttribute.Normal, VertexAttributeFormat.Float32, 3, 1),
                new VertexAttributeDescriptor(VertexAttribute.TexCoord0, VertexAttributeFormat.Float32, 2, 2));
            mesh.vertices = new[] { Vector3.zero, Vector3.right, Vector3.up, Vector3.left, Vector3.up * 2, Vector3.one };
            mesh.normals = new[] { Vector3.forward, Vector3.forward, Vector3.forward, Vector3.forward, Vector3.forward, Vector3.forward };
            mesh.uv = new[] { Vector2.zero, Vector2.right, Vector2.up, Vector2.left, Vector2.one, Vector2.zero };
            mesh.subMeshCount = 2;
            mesh.SetTriangles(new[] { 0, 1, 2 }, 0);
            mesh.SetTriangles(new[] { 0, 2, 1 }, 1, true, 3);
            mesh.bindposes = new[] { Matrix4x4.identity };
            using (var counts = new NativeArray<byte>(new byte[] { 1, 1, 1, 1, 1, 1 }, Allocator.Temp))
            using (var weights = new NativeArray<BoneWeight1>(6, Allocator.Temp))
            {
                for (int i = 0; i < weights.Length; i++) weights[i] = new BoneWeight1 { boneIndex = 0, weight = 1 };
                mesh.SetBoneWeights(counts, weights);
            }
            var deltas = new[] { Vector3.right * .1f, Vector3.right * .1f, Vector3.right * .1f, Vector3.right * .1f, Vector3.right * .1f, Vector3.right * .1f };
            mesh.AddBlendShapeFrame("TestShape", 100, deltas, null, null);
            renderer.sharedMesh = mesh; renderer.bones = new[] { bone }; renderer.rootBone = bone;
            renderer.sharedMaterials = new[] { material, material };
            renderer.SetBlendShapeWeight(0, 25);
            texture.SetPixels(new[] { Color.red, Color.green, Color.blue, Color.white }); texture.Apply();
            material.mainTexture = texture;
            var choices = new List<BlenderModelExporter.Selection>
            {
                new BlenderModelExporter.Selection { Renderer = renderer, Submesh = 0, Part = BlenderModelExporter.Part.Clothing },
                new BlenderModelExporter.Selection { Renderer = renderer, Submesh = 1, Part = BlenderModelExporter.Part.Body }
            };
            string output = Path.GetFullPath(Path.Combine(Application.dataPath, "../Tests/Local/unity"));
            Verify(BlenderModelExporter.Export(container, choices, output), renderer, mesh);
            mesh.UploadMeshData(true);
            Verify(BlenderModelExporter.Export(container, choices, output), renderer, mesh);
            Debug.Log("UMA_UNITY_SNAPSHOT_SMOKE_TEST_OK: readable + GPU-only mesh, baseVertex, weights, morphs and state preservation. " + output);
        }
        finally
        {
            UnityEngine.Object.DestroyImmediate(root);
            UnityEngine.Object.DestroyImmediate(mesh);
            UnityEngine.Object.DestroyImmediate(material);
            UnityEngine.Object.DestroyImmediate(texture);
        }
    }
    static void Verify(string directory, SkinnedMeshRenderer renderer, Mesh source)
    {
        var data = JsonUtility.FromJson<BlenderModelExporter.Snapshot>(File.ReadAllText(Path.Combine(directory, "model.uma.json")));
        if (data.meshes.Count != 1 || data.meshes[0].faces.Count != 2 || data.meshes[0].weights.Count != 6 || data.meshes[0].shapes.Count != 1)
            throw new Exception("Snapshot lost mesh sections, bone weights or shape keys.");
        if (data.meshes[0].faces[1].triangles[0] != 3 || Math.Abs(data.meshes[0].shapes[0].weight - .25f) > .0001f)
            throw new Exception("Submesh baseVertex or morph weight was lost.");
        if (renderer.sharedMesh != source || Math.Abs(renderer.GetBlendShapeWeight(0) - 25) > .0001f)
            throw new Exception("Export mutated the source renderer.");
    }
}
