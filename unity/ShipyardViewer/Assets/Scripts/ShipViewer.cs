using System.Collections;
using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Scripting;

// 브라우저 계약: GameObject 'ShipViewer', SetView(front|side|top|reset), SetFleet(0~6).
// 업무 데이터·토큰은 받지 않는다(조선소 모드는 척 수만).
public class ShipViewer : MonoBehaviour
{
    public Material[] materials;
    public Camera cam;

#if UNITY_WEBGL && !UNITY_EDITOR
    [DllImport("__Internal")] static extern void ShipViewer_NotifyReady();
    [DllImport("__Internal")] static extern void ShipViewer_NotifyHover(int active);
    [DllImport("__Internal")] static extern void ShipViewer_FleetEvent(int slot, int selected);
#else
    static void ShipViewer_NotifyReady() { }
    static void ShipViewer_NotifyHover(int active) { }
    static void ShipViewer_FleetEvent(int slot, int selected) { }
#endif

    const float Fov = 30f, Damp = 12f, MinDist = 50f, MaxDist = 540f;
    static readonly Vector3 DefaultPivot = new Vector3(0f, 7f, 0f);

    struct ViewDef { public float yaw, pitch, w, h; public ViewDef(float a, float b, float c, float d) { yaw = a; pitch = b; w = c; h = d; } }

    static bool TryDef(string v, out ViewDef d)
    {
        switch (v)
        {
            case "reset": d = new ViewDef(-130f, 35f, 49f, 32f); return true;
            case "front": d = new ViewDef(180f, 6f, 10f, 15f); return true;
            case "side": d = new ViewDef(-90f, 6f, 33f, 15f); return true;
            case "top": d = new ViewDef(-90f, 88f, 33f, 10f); return true;
        }
        d = default; return false;
    }

    GameObject singleRoot, fleetRoot;
    readonly GameObject[] slots = new GameObject[6];
    Transform trolley;
    bool fleet;
    int fleetCount;

    float yaw, pitch, dist, tYaw, tPitch, tDist;
    Vector3 pivot, tPivot;
    string view = "reset";
    int lastW, lastH;

    Vector3 lastMouse, downPos;
    int pressSlot = -1, hoverSlot = -1;
    bool hoverHull;

    void Awake()
    {
        QualitySettings.shadows = ShadowQuality.All;
        QualitySettings.shadowDistance = 400f;
#if UNITY_WEBGL && !UNITY_EDITOR
        WebGLInput.captureAllKeyboardInput = false;
#endif
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(.42f, .47f, .54f);
        RenderSettings.ambientEquatorColor = new Color(.34f, .37f, .41f);
        RenderSettings.ambientGroundColor = new Color(.24f, .26f, .29f);
        if (cam == null) cam = Camera.main;

        singleRoot = new GameObject("Single");
        singleRoot.transform.SetParent(transform, false);
        ShipModel.BuildShip(materials, singleRoot.transform);
        ShipModel.BuildSingleYard(materials, singleRoot.transform);
    }

    IEnumerator Start()
    {
        lastW = Screen.width; lastH = Screen.height;
        ApplyView("reset", true);
        Place();
        yield return null; // 첫 프레임 렌더 뒤
        yield return null;
        ShipViewer_NotifyReady();
    }

    void EnsureFleet()
    {
        if (fleetRoot != null) return;
        fleetRoot = new GameObject("Fleet");
        fleetRoot.transform.SetParent(transform, false);
        ShipModel.BuildFleetYard(materials, fleetRoot.transform, out trolley);
        for (int i = 0; i < 6; i++)
        {
            var slot = new GameObject("Slot" + i);
            slot.transform.SetParent(fleetRoot.transform, false);
            bool dock = i < 3;
            slot.transform.localPosition = new Vector3((i % 3 - 1) * 32f, dock ? 0f : -1.4f, dock ? -44f : 43f);
            slot.transform.localRotation = Quaternion.Euler(0f, dock ? 0f : 180f, 0f);
            slot.transform.localScale = Vector3.one * (.76f + .05f * (i % 3));
            slot.AddComponent<FleetSlot>().index = i;
            var ship = ShipModel.BuildShip(materials, slot.transform);
            if (!dock) ship.transform.Find("KeelBlocks").gameObject.SetActive(false);
            slots[i] = slot;
        }
    }

    [Preserve]
    public void SetView(string v)
    {
        if (!TryDef(v, out _)) return;
        ApplyView(v, false);
    }

    [Preserve]
    public void SetFleet(string count)
    {
        if (!int.TryParse(count, out int n) || n < 0 || n > 6) return;
        EnsureFleet();
        fleet = true;
        fleetCount = n;
        singleRoot.SetActive(false);
        fleetRoot.SetActive(true);
        for (int i = 0; i < 6; i++) slots[i].SetActive(i < n);
        Physics.SyncTransforms();
        if (hoverSlot != -1) { hoverSlot = -1; ShipViewer_FleetEvent(-1, 0); }
        pressSlot = -1;
        hoverHull = false;
        ApplyView("reset", true);
        Place();
    }

    float Aspect => Screen.height > 0 ? (float)Screen.width / Screen.height : 1.6f;
    static float Tan => Mathf.Tan(Fov * .5f * Mathf.Deg2Rad);

    void ApplyView(string v, bool snap)
    {
        view = v;
        if (!fleet)
        {
            TryDef(v, out ViewDef d);
            tYaw = yaw + Mathf.DeltaAngle(yaw, d.yaw);
            tPitch = d.pitch;
            tPivot = DefaultPivot;
            tDist = Mathf.Clamp(Mathf.Max(d.w / (Tan * Aspect), d.h / Tan) * 1.15f, MinDist, MaxDist);
        }
        else
        {
            float fy = v == "front" ? 180f : v == "side" ? -90f : -64f;
            tYaw = yaw + Mathf.DeltaAngle(yaw, fy);
            tPitch = v == "top" ? 88f : 58f;
            Bounds b = FleetBounds();
            tPivot = ClampPivot(b.center);
            tDist = Mathf.Clamp(FitBounds(b, tYaw, tPitch, tPivot), MinDist, MaxDist);
        }
        if (snap) { yaw = tYaw; pitch = tPitch; dist = tDist; pivot = tPivot; }
    }

    Bounds FleetBounds()
    {
        bool any = false;
        var b = new Bounds();
        for (int i = 0; i < fleetCount; i++)
            foreach (var r in slots[i].GetComponentsInChildren<Renderer>())
            {
                if (!any) { b = r.bounds; any = true; } else b.Encapsulate(r.bounds);
            }
        if (!any) b = new Bounds(new Vector3(0f, 2f, -10f), new Vector3(110f, 8f, 150f));
        return b;
    }

    float FitBounds(Bounds b, float y, float p, Vector3 pv)
    {
        var inv = Quaternion.Inverse(Quaternion.Euler(p, y, 0f));
        float need = 0f, t = Tan, a = Aspect;
        for (int i = 0; i < 8; i++)
        {
            var c = new Vector3((i & 1) == 0 ? b.min.x : b.max.x, (i & 2) == 0 ? b.min.y : b.max.y, (i & 4) == 0 ? b.min.z : b.max.z);
            var l = inv * (c - pv);
            need = Mathf.Max(need, Mathf.Abs(l.x) / (t * a) - l.z, Mathf.Abs(l.y) / t - l.z);
        }
        return need * 1.06f;
    }

    Vector3 ClampPivot(Vector3 p)
    {
        float lim = fleet ? 110f : 14f;
        return new Vector3(Mathf.Clamp(p.x, -lim, lim), Mathf.Clamp(p.y, 2f, 24f), Mathf.Clamp(p.z, -lim, lim));
    }

    void Update()
    {
        if (Screen.width != lastW || Screen.height != lastH)
        {
            lastW = Screen.width; lastH = Screen.height;
            if (lastW > 0 && lastH > 0) ApplyView(view, false);
        }
        HandleInput();
        float k = 1f - Mathf.Exp(-Damp * Time.unscaledDeltaTime);
        yaw = Approach(yaw, tYaw, k, .001f);
        pitch = Approach(pitch, tPitch, k, .001f);
        dist = Approach(dist, tDist, k, .001f);
        pivot = Vector3.Distance(pivot, tPivot) < .0005f ? tPivot : Vector3.Lerp(pivot, tPivot, k);
        Place();
        if (fleet && trolley != null)
            trolley.localPosition = new Vector3(Mathf.Sin(Time.time * .45f) * 26f, 19f, -68f);
        UpdateHover();
    }

    static float Approach(float c, float t, float k, float eps) => Mathf.Abs(t - c) < eps ? t : Mathf.Lerp(c, t, k);

    void Place()
    {
        var q = Quaternion.Euler(pitch, yaw, 0f);
        cam.transform.SetPositionAndRotation(pivot + q * new Vector3(0f, 0f, -dist), q);
    }

    bool MouseInScreen()
    {
        var m = Input.mousePosition;
        return m.x >= 0 && m.y >= 0 && m.x <= Screen.width && m.y <= Screen.height;
    }

    void HandleInput()
    {
        Vector3 m = Input.mousePosition;
        Vector3 d = m - lastMouse;
        if (Input.GetMouseButtonDown(0))
        {
            downPos = m; d = Vector3.zero;
            pressSlot = fleet ? SlotAt(m) : -1;
        }
        if (Input.GetMouseButtonDown(1)) d = Vector3.zero;

        if (Input.GetMouseButton(0))
        {
            tYaw += d.x * .3f;
            tPitch = Mathf.Clamp(tPitch - d.y * .25f, 4f, 88f);
        }
        else if (Input.GetMouseButton(1))
        {
            float s = 2f * dist * Tan / Mathf.Max(1, Screen.height);
            var tr = cam.transform;
            tPivot = ClampPivot(tPivot - tr.right * d.x * s - tr.up * d.y * s);
        }
        if (Input.GetMouseButtonUp(0))
        {
            if (fleet && pressSlot >= 0 && (m - downPos).magnitude <= 6f && SlotAt(m) == pressSlot)
                ShipViewer_FleetEvent(pressSlot, 1);
            pressSlot = -1;
        }
        float w = Input.mouseScrollDelta.y;
        if (w != 0f && MouseInScreen())
        {
            w = Mathf.Clamp(w, -3f, 3f);
            float maxD = Mathf.Max(MaxDist, tDist);
            tDist = Mathf.Clamp(tDist * Mathf.Exp(-w * .12f), MinDist, maxD);
        }
        lastMouse = m;
    }

    Collider HitAt(Vector3 m)
    {
        if (m.x < 0 || m.y < 0 || m.x > Screen.width || m.y > Screen.height) return null;
        return Physics.Raycast(cam.ScreenPointToRay(m), out RaycastHit hit, 3000f) ? hit.collider : null;
    }

    int SlotAt(Vector3 m)
    {
        var c = HitAt(m);
        var s = c != null ? c.GetComponentInParent<FleetSlot>() : null;
        return s != null && s.index < fleetCount ? s.index : -1;
    }

    void UpdateHover()
    {
        if (Input.GetMouseButton(0) || Input.GetMouseButton(1)) return;
        var m = Input.mousePosition;
        if (fleet)
        {
            int s = SlotAt(m);
            if (s != hoverSlot) { hoverSlot = s; ShipViewer_FleetEvent(s, 0); }
        }
        else
        {
            bool h = HitAt(m) != null;
            if (h != hoverHull) { hoverHull = h; ShipViewer_NotifyHover(h ? 1 : 0); }
        }
    }
}
