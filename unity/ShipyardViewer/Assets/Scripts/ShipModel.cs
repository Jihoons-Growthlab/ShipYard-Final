using System.Collections.Generic;
using UnityEngine;

// Demo Ship 01 과 조선소 배경을 런타임에 코드로 만든다. 선수 +Z, 지면 y=0. 실제 호선 형상이 아니다.
public static class ShipModel
{
    public const int HullLower = 0, HullUpper = 1, Deck = 2, House = 3, Accent = 4, Glass = 5, Steel = 6, Ground = 7;

    const float Length = 60f, Beam = 10f, Depth = 6f, KeelH = .8f, Split = 2.6f, Rake = 3f;
    const int Stations = 72;
    static readonly float[] Rows = { 0f, .2f, .5f, .9f, 1.3f, 1.6f, 2.1f, 2.6f, 3.2f, 4f, 5f, 5.6f, 6f };
    public const float DeckY = KeelH + Depth;

    public static float HalfWidth(float z, float h)
    {
        float section = 1f - .55f * Mathf.Pow(1f - Mathf.Clamp01(h / 1.6f), 3f);
        float zs = z - Rake * (h / Depth);
        float plan = 1f;
        if (zs > 12f) plan = 1f - Mathf.Pow(Mathf.Clamp01((zs - 12f) / 15f), 2.2f);
        if (z < -18f)
        {
            float s = Mathf.Clamp01((-18f - z) / 12f);
            plan *= 1f - .28f * s * s;
            section *= Mathf.Pow(Mathf.Clamp01((h + .15f) / 6f), .7f * s);
        }
        return Beam / 2f * section * plan;
    }

    static float StationZ(int i) => -Length / 2f + Length * i / (Stations - 1);

    // 반폭이 0인 정점은 그 높이의 선수 윤곽점(zs=27)으로 모아 계단 없는 선수 경사를 만든다.
    static Vector3 Point(float side, float z, float h)
    {
        float w = HalfWidth(z, h);
        if (w <= 1e-5f) z = Mathf.Min(z, 27f + Rake * (h / Depth));
        return new Vector3(side * w, KeelH + h, z);
    }

    class Buf
    {
        public readonly List<Vector3> V = new List<Vector3>();
        public readonly List<int>[] Sub = { new List<int>(), new List<int>(), new List<int>() };

        // 면 방향은 바깥 방향 힌트로 정한다. 0 면적 면과 중심면(x=0)에 붙은 면은 건너뛴다.
        public void Tri(int sub, int a, int b, int c, Vector3 hint)
        {
            Vector3 pa = V[a], pb = V[b], pc = V[c];
            Vector3 n = Vector3.Cross(pb - pa, pc - pa);
            if (n.sqrMagnitude < 1e-10f) return;
            if (Mathf.Abs(pa.x) < 1e-4f && Mathf.Abs(pb.x) < 1e-4f && Mathf.Abs(pc.x) < 1e-4f) return;
            if (Vector3.Dot(n, hint) < 0f) { int t = b; b = c; c = t; }
            Sub[sub].Add(a); Sub[sub].Add(b); Sub[sub].Add(c);
        }

        public void Quad(int sub, int a, int b, int c, int d, Vector3 hint)
        {
            Tri(sub, a, b, c, hint);
            Tri(sub, a, c, d, hint);
        }
    }

    public static Mesh HullMesh()
    {
        var buf = new Buf();
        int R = Rows.Length;
        // 좌우 현: 현별로 정점을 병합한다(곡면 법선). x=0을 공유하지 않는다.
        foreach (float side in new[] { -1f, 1f })
        {
            int b0 = buf.V.Count;
            for (int i = 0; i < Stations; i++)
                for (int r = 0; r < R; r++)
                    buf.V.Add(Point(side, StationZ(i), Rows[r]));
            for (int i = 0; i < Stations - 1; i++)
                for (int r = 0; r < R - 1; r++)
                {
                    int a = b0 + i * R + r, b = a + R;
                    int sub = Rows[r + 1] <= Split + 1e-4f ? HullLower : HullUpper;
                    buf.Quad(sub, a, b, b + 1, a + 1, new Vector3(side, 0f, 0f));
                }
        }
        // 바닥·갑판은 각지게(별도 정점).
        Strip(buf, 0f, HullLower, Vector3.down);
        Strip(buf, Depth, Deck, Vector3.up);
        // 선미판
        {
            int b0 = buf.V.Count;
            for (int r = 0; r < R; r++)
            {
                float w = HalfWidth(StationZ(0), Rows[r]);
                buf.V.Add(new Vector3(-w, KeelH + Rows[r], StationZ(0)));
                buf.V.Add(new Vector3(w, KeelH + Rows[r], StationZ(0)));
            }
            for (int r = 0; r < R - 1; r++)
            {
                int a = b0 + r * 2;
                int sub = Rows[r + 1] <= Split + 1e-4f ? HullLower : HullUpper;
                buf.Quad(sub, a, a + 1, a + 3, a + 2, Vector3.back);
            }
        }
        var mesh = new Mesh { name = "DemoShip01Hull" };
        mesh.SetVertices(buf.V);
        mesh.subMeshCount = 3;
        for (int s = 0; s < 3; s++) mesh.SetTriangles(buf.Sub[s], s);
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
        return mesh;
    }

    static void Strip(Buf buf, float h, int sub, Vector3 hint)
    {
        int b0 = buf.V.Count;
        for (int i = 0; i < Stations; i++)
        {
            buf.V.Add(Point(-1f, StationZ(i), h));
            buf.V.Add(Point(1f, StationZ(i), h));
        }
        for (int i = 0; i < Stations - 1; i++)
        {
            int a = b0 + i * 2;
            buf.Quad(sub, a, a + 1, a + 3, a + 2, hint);
        }
    }

    public static GameObject Box(Transform parent, string name, Vector3 center, Vector3 size, Material m, bool collider)
    {
        var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
        go.name = name;
        go.transform.SetParent(parent, false);
        go.transform.localPosition = center;
        go.transform.localScale = size;
        go.GetComponent<MeshRenderer>().sharedMaterial = m;
        if (!collider) Object.Destroy(go.GetComponent<BoxCollider>());
        return go;
    }

    public static GameObject BuildShip(Material[] m, Transform parent)
    {
        var root = new GameObject("DemoShip01");
        root.transform.SetParent(parent, false);
        var t = root.transform;

        var hull = new GameObject("Hull");
        hull.transform.SetParent(t, false);
        var mesh = HullMesh();
        hull.AddComponent<MeshFilter>().sharedMesh = mesh;
        hull.AddComponent<MeshRenderer>().sharedMaterials = new[] { m[HullLower], m[HullUpper], m[Deck] };
        hull.AddComponent<MeshCollider>().sharedMesh = mesh;

        float y = DeckY;
        // 3단 선실 + 브리지
        Box(t, "House1", new Vector3(0, y + 1.4f, -19.5f), new Vector3(9.4f, 2.8f, 8f), m[House], true);
        Box(t, "House2", new Vector3(0, y + 4.0f, -20f), new Vector3(8.6f, 2.4f, 7f), m[House], true);
        Box(t, "House3", new Vector3(0, y + 6.4f, -20.5f), new Vector3(7.6f, 2.4f, 6f), m[House], true);
        Box(t, "Bridge", new Vector3(0, y + 8.7f, -20f), new Vector3(8.4f, 2.2f, 5f), m[House], true);
        Box(t, "BridgeRoof", new Vector3(0, y + 9.9f, -20f), new Vector3(8.8f, .2f, 5.4f), m[House], true);
        Box(t, "BridgeWing", new Vector3(0, y + 8.0f, -18.5f), new Vector3(13f, .35f, 2f), m[House], true);
        // 창
        Box(t, "WinBridge", new Vector3(0, y + 9.0f, -17.45f), new Vector3(7.4f, .7f, .12f), m[Glass], true);
        Box(t, "Win3", new Vector3(0, y + 6.6f, -17.45f), new Vector3(5.5f, .4f, .12f), m[Glass], true);
        Box(t, "Win2", new Vector3(0, y + 4.2f, -16.45f), new Vector3(6f, .4f, .12f), m[Glass], true);
        Box(t, "Win1", new Vector3(0, y + 1.8f, -15.45f), new Vector3(7f, .4f, .12f), m[Glass], true);
        foreach (float s in new[] { -1f, 1f })
        {
            Box(t, "WinSide1", new Vector3(s * 4.75f, y + 1.8f, -19.5f), new Vector3(.12f, .4f, 6f), m[Glass], true);
            Box(t, "WinSide2", new Vector3(s * 4.35f, y + 4.2f, -20f), new Vector3(.12f, .4f, 5f), m[Glass], true);
            Box(t, "WinSide3", new Vector3(s * 3.85f, y + 6.6f, -20.5f), new Vector3(.12f, .4f, 4f), m[Glass], true);
        }
        // 굴뚝·마스트
        Box(t, "Funnel", new Vector3(0, y + 4.6f, -25.2f), new Vector3(2.8f, 9.2f, 3f), m[Accent], true);
        Box(t, "FunnelCap", new Vector3(0, y + 9.4f, -25.2f), new Vector3(3f, .4f, 3.2f), m[Steel], true);
        Box(t, "Mast", new Vector3(0, y + 11.6f, -20f), new Vector3(.22f, 3.2f, .22f), m[Steel], true);
        Box(t, "MastBar", new Vector3(0, y + 12.4f, -20f), new Vector3(2.2f, .15f, .15f), m[Steel], true);
        // 해치 4개: 오렌지 코밍 + 강재 덮개
        for (int k = 0; k < 4; k++)
        {
            float z = -9.5f + 8.2f * k;
            Box(t, "Coaming" + k, new Vector3(0, y + .4f, z), new Vector3(7f, .8f, 6.4f), m[Accent], true);
            Box(t, "Cover" + k, new Vector3(0, y + .95f, z), new Vector3(6.4f, .3f, 5.8f), m[Steel], true);
        }
        // 카고 포스트 3개
        foreach (float z in new[] { -13.6f, 2.8f, 19.4f })
        {
            Box(t, "Post", new Vector3(0, y + 2.5f, z), new Vector3(.5f, 5f, .5f), m[Steel], true);
            Box(t, "Jib", new Vector3(0, y + 4.9f, z + 3f), new Vector3(.3f, .3f, 6f), m[Steel], true);
        }
        // 킬 블록 9개
        var keel = new GameObject("KeelBlocks");
        keel.transform.SetParent(t, false);
        for (int k = 0; k < 9; k++)
            Box(keel.transform, "KeelBlock" + k, new Vector3(0, .4f, -24f + 6f * k), new Vector3(1.6f, .8f, 2f), m[Steel], true);
        return root;
    }

    public static GameObject BuildSingleYard(Material[] m, Transform parent)
    {
        var root = new GameObject("SingleYard");
        root.transform.SetParent(parent, false);
        var t = root.transform;
        Box(t, "Sea", new Vector3(0, -2.5f, 0), new Vector3(500f, 1f, 500f), m[HullUpper], false);
        Box(t, "DockFloor", new Vector3(0, -.6f, -6f), new Vector3(25f, 1.2f, 84f), m[Ground], false);
        foreach (float s in new[] { -1f, 1f })
        {
            Box(t, "Wall", new Vector3(s * 23f, 0f, -6f), new Vector3(21f, 3f, 96f), m[Ground], false);
            Box(t, "WallEdge", new Vector3(s * 12.9f, 1.55f, -6f), new Vector3(.4f, .1f, 96f), m[Accent], false);
            foreach (float z in new[] { -27f, -21f })
                Box(t, "CraneLeg", new Vector3(s * 16f, 11.75f, z), new Vector3(1.6f, 20.5f, 1.6f), m[Accent], false);
        }
        Box(t, "CraneBeam", new Vector3(0, 22f, -24f), new Vector3(33f, 2f, 4f), m[Accent], false);
        Box(t, "Workshop", new Vector3(24f, 5f, 10f), new Vector3(14f, 7f, 24f), m[House], false);
        Box(t, "WorkshopRoof", new Vector3(24f, 8.8f, 10f), new Vector3(15f, .6f, 25f), m[Steel], false);
        int[] cm = { HullLower, Steel, HullLower };
        for (int k = 0; k < 3; k++)
            Box(t, "Container" + k, new Vector3(-23f, 2.8f, 0f + 3.2f * k), new Vector3(6f, 2.6f, 2.4f), m[cm[k]], false);
        return root;
    }

    public static GameObject BuildFleetYard(Material[] m, Transform parent, out Transform trolley)
    {
        var root = new GameObject("FleetYard");
        root.transform.SetParent(parent, false);
        var t = root.transform;
        Box(t, "Sea", new Vector3(0, -3.5f, 0), new Vector3(700f, 1f, 700f), m[HullUpper], false);
        Box(t, "Quay", new Vector3(0, -1f, 0), new Vector3(124f, 2f, 22f), m[Ground], false);
        Box(t, "QuayLine", new Vector3(0, .05f, -10.6f), new Vector3(124f, .1f, .5f), m[Accent], false);
        int[] cm = { HullLower, Steel, HullLower };
        foreach (float x in new[] { -32f, 0f, 32f })
        {
            Box(t, "DryDock", new Vector3(x, -.5f, -44f), new Vector3(26f, 1f, 72f), m[Ground], false);
            Box(t, "Pier", new Vector3(x + 12f, -1.25f, 43f), new Vector3(3f, 2.5f, 68f), m[Ground], false);
            for (int k = 0; k < 3; k++)
                Box(t, "Container", new Vector3(x + 8f, 1.3f, 1f + (k - 1) * 3.2f), new Vector3(6f, 2.6f, 2.4f), m[cm[k]], false);
        }
        foreach (float s in new[] { -1f, 1f })
        {
            Box(t, "CraneBase", new Vector3(s * 58f, .5f, -44f), new Vector3(4f, 1f, 76f), m[Steel], false);
            Box(t, "CraneLeg", new Vector3(s * 58f, 11f, -68f), new Vector3(2f, 21f, 2f), m[Accent], false);
        }
        Box(t, "CraneBeam", new Vector3(0, 22f, -68f), new Vector3(120f, 2f, 4f), m[Accent], false);
        // 움직이는 트롤리(시뮬레이션 표시): 상자 5 + 케이블 + 스프레더
        var tr = new GameObject("Trolley").transform;
        tr.SetParent(t, false);
        tr.localPosition = new Vector3(0, 19f, -68f);
        Box(tr, "Body", new Vector3(0, 0, 0), new Vector3(5f, 2f, 5f), m[Steel], false);
        Box(tr, "Cab", new Vector3(2.2f, -1.6f, 0), new Vector3(1.6f, 1.4f, 1.8f), m[House], false);
        Box(tr, "SideA", new Vector3(0, 1.4f, 2.2f), new Vector3(5f, .8f, .4f), m[Accent], false);
        Box(tr, "SideB", new Vector3(0, 1.4f, -2.2f), new Vector3(5f, .8f, .4f), m[Accent], false);
        Box(tr, "Top", new Vector3(0, 1.1f, 0), new Vector3(4f, .3f, 4f), m[Steel], false);
        Box(tr, "Cable", new Vector3(0, -5f, 0), new Vector3(.15f, 8f, .15f), m[Steel], false);
        Box(tr, "Spreader", new Vector3(0, -9.2f, 0), new Vector3(8f, .5f, 3f), m[Accent], false);
        trolley = tr;
        return root;
    }
}
