using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.SceneManagement;

// 씬·재질을 매번 재생성하고 Web 빌드까지 수행한다.
// Unity -batchmode -quit -buildTarget WebGL -projectPath unity/ShipyardViewer -executeMethod ViewerBuild.Build
public static class ViewerBuild
{
    const string ScenePath = "Assets/Scenes/Viewer.unity";
    const string MatDir = "Assets/Materials";

    static readonly (string name, string hex, float smooth)[] Mats =
    {
        ("HullLower", "#9E2F2A", .3f), ("HullUpper", "#1B3A66", .4f), ("Deck", "#6F8A7A", .2f), ("House", "#E4E8EE", .3f),
        ("Accent", "#D97F2A", .3f), ("Glass", "#202C3C", .8f), ("Steel", "#5B6573", .3f), ("Ground", "#B4BDC9", .05f),
    };

    public static void Build()
    {
        try { Run(); }
        catch (Exception e)
        {
            Debug.LogError("ViewerBuild failed: " + e);
            EditorApplication.Exit(1);
        }
    }

    static Color Hex(string h) { ColorUtility.TryParseHtmlString(h, out Color c); return c; }

    static void Run()
    {
        Configure();
        var mats = MakeMaterials();
        MakeScene(mats);
        string outDir = Path.GetFullPath(Path.Combine(Application.dataPath, "../../../frontend/public/unity/ship-viewer"));
        if (Directory.Exists(outDir)) Directory.Delete(outDir, true);
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = new[] { ScenePath },
            locationPathName = outDir,
            target = BuildTarget.WebGL,
            options = BuildOptions.None,
        });
        if (report.summary.result != BuildResult.Succeeded)
            throw new Exception("build result " + report.summary.result + " errors=" + report.summary.totalErrors);
        PostProcess(outDir);
        Debug.Log("ViewerBuild OK " + outDir);
    }

    static void Configure()
    {
        PlayerSettings.companyName = "SWP";
        PlayerSettings.productName = "ShipyardViewer";
        PlayerSettings.colorSpace = ColorSpace.Linear;
        PlayerSettings.runInBackground = true;
        PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
        PlayerSettings.WebGL.decompressionFallback = false;
        PlayerSettings.WebGL.nameFilesAsHashes = false;
        PlayerSettings.WebGL.dataCaching = false;
        PlayerSettings.WebGL.exceptionSupport = WebGLExceptionSupport.None;
        PlayerSettings.WebGL.template = "APPLICATION:Minimal";
        PlayerSettings.stripEngineCode = true;
        PlayerSettings.SetManagedStrippingLevel(NamedBuildTarget.WebGL, ManagedStrippingLevel.High);
        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.WebGL, false);
        PlayerSettings.SetGraphicsAPIs(BuildTarget.WebGL, new[] { GraphicsDeviceType.OpenGLES3 });
        AssetDatabase.SaveAssets();
    }

    static Material[] MakeMaterials()
    {
        if (!AssetDatabase.IsValidFolder(MatDir)) AssetDatabase.CreateFolder("Assets", "Materials");
        var shader = Shader.Find("Standard");
        if (shader == null) throw new Exception("Standard shader not found");
        var list = new Material[Mats.Length];
        for (int i = 0; i < Mats.Length; i++)
        {
            string path = $"{MatDir}/{Mats[i].name}.mat";
            AssetDatabase.DeleteAsset(path);
            var m = new Material(shader) { name = Mats[i].name, color = Hex(Mats[i].hex) };
            m.SetFloat("_Glossiness", Mats[i].smooth);
            AssetDatabase.CreateAsset(m, path);
            list[i] = m;
        }
        AssetDatabase.SaveAssets();
        return list;
    }

    static void MakeScene(Material[] mats)
    {
        if (!AssetDatabase.IsValidFolder("Assets/Scenes")) AssetDatabase.CreateFolder("Assets", "Scenes");
        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
        var cam = camGo.AddComponent<Camera>();
        cam.clearFlags = CameraClearFlags.SolidColor;
        cam.backgroundColor = Hex("#DDE4EE");
        cam.fieldOfView = 30f;
        cam.nearClipPlane = 1f;
        cam.farClipPlane = 1000f;

        var sunGo = new GameObject("Sun");
        var sun = sunGo.AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.intensity = .95f;
        sun.shadows = LightShadows.Soft;
        sun.color = Color.white;
        sunGo.transform.rotation = Quaternion.Euler(52f, -35f, 0f);

        RenderSettings.skybox = null;
        RenderSettings.fog = false;
        RenderSettings.sun = sun;
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(.42f, .47f, .54f);
        RenderSettings.ambientEquatorColor = new Color(.34f, .37f, .41f);
        RenderSettings.ambientGroundColor = new Color(.24f, .26f, .29f);

        var viewerGo = new GameObject("ShipViewer");
        var viewer = viewerGo.AddComponent<ShipViewer>();
        viewer.materials = mats;
        viewer.cam = cam;

        EditorSceneManager.SaveScene(scene, ScenePath);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        AssetDatabase.SaveAssets();
    }

    static void PostProcess(string outDir)
    {
        string index = Path.Combine(outDir, "index.html");
        if (File.Exists(index)) File.Delete(index);
        string tpl = Path.Combine(outDir, "TemplateData");
        if (Directory.Exists(tpl)) Directory.Delete(tpl, true);
        string build = Path.Combine(outDir, "Build");
        var files = Directory.GetFiles(build).Select(Path.GetFileName).ToArray();
        string Find(string suffix) => files.FirstOrDefault(f => f.EndsWith(suffix)) ?? throw new Exception("missing *" + suffix);
        string json = "{\n"
            + $"  \"loaderUrl\": \"{Find(".loader.js")}\",\n"
            + $"  \"dataUrl\": \"{Find(".data")}\",\n"
            + $"  \"frameworkUrl\": \"{Find(".framework.js")}\",\n"
            + $"  \"codeUrl\": \"{Find(".wasm")}\",\n"
            + $"  \"companyName\": \"{PlayerSettings.companyName}\",\n"
            + $"  \"productName\": \"{PlayerSettings.productName}\",\n"
            + $"  \"productVersion\": \"{PlayerSettings.bundleVersion}\"\n"
            + "}\n";
        File.WriteAllText(Path.Combine(build, "build.json"), json);
    }
}
