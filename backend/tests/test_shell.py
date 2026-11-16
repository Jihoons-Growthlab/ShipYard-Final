from app.permissions import menu_level, menu_levels
from app.services import weather


def ids(menu):
    return [m["menu_id"] for m in menu]


def test_shell_t01_menu_by_group(client, login):
    m = client.get("/api/me/menu", headers=login("choi.qa")).json()
    assert ids(m) == ["M00", "M10", "M11", "M20", "M21", "M22", "M30", "M31", "M33", "M95"]
    assert all(not x["can_write"] for x in m if x["menu_id"] != "M95")
    hl = next(x for x in m if x["menu_id"] == "M11")
    assert hl == {"menu_id": "M11", "parent_id": "M10", "title": "호선 목록", "token": "hull-list", "seq": 3,
                  "level": 1, "auth_gbn": "View", "can_write": False}
    pm = ids(client.get("/api/me/menu", headers=login("park.pm")).json())
    assert "M33" not in pm and "M91" not in pm and "M22" in pm
    dwg = ids(client.get("/api/me/menu", headers=login("lee.dwg")).json())
    assert "M22" not in dwg and "M33" in dwg
    adm = client.get("/api/me/menu", headers=login("admin")).json()
    assert len(adm) == 13 and all(x["can_write"] for x in adm)


def test_shell_t01_menu_access_403_and_log(client, login, conn):
    h = login("park.pm")
    r = client.post("/api/me/menu-access", json={"menu_id": "M91"}, headers=h)
    assert r.status_code == 403 and r.json()["details"] == {"menu_id": "M91"}
    assert client.post("/api/me/menu-access", json={"menu_id": "M00"}, headers=h).status_code == 204
    row = conn.execute("SELECT m.MenuId, a.UserId FROM TB_SYS_LogMenuAccess m JOIN TB_SYS_LogAccess a"
                       " ON a.LogId=m.LogId ORDER BY AccIndex DESC").fetchone()
    assert tuple(row) == ("M00", "park.pm")
    assert client.post("/api/me/menu-access", json={"menu_id": "ZZZ"}, headers=h).status_code == 404


def test_br10_user_override(client, login, conn):
    # 그룹 최고값
    conn.execute("INSERT INTO TB_SYS_AuthUser VALUES('VIEW','park.pm')")
    assert menu_level(conn, "park.pm", "M11") == 2
    # 회원별 None은 접근 불가, Write는 상향
    conn.execute("INSERT INTO TB_SYS_UserMenu VALUES('park.pm','M11','None')")
    conn.execute("INSERT INTO TB_SYS_UserMenu VALUES('choi.qa','M22','Write')")
    assert menu_levels(conn, "park.pm")["M11"] == 0
    m = client.get("/api/me/menu", headers=login("park.pm")).json()
    assert "M11" not in ids(m) and "M10" in ids(m)
    qa = {x["menu_id"]: x for x in client.get("/api/me/menu", headers=login("choi.qa")).json()}
    assert qa["M22"]["can_write"] is True and qa["M22"]["auth_gbn"] == "Write"
    # 부모를 볼 수 없으면 자식도 숨김
    conn.execute("INSERT INTO TB_SYS_UserMenu VALUES('choi.qa','M20','None')")
    qa = ids(client.get("/api/me/menu", headers=login("choi.qa")).json())
    assert "M21" not in qa and "M22" not in qa


def test_codes(client, login):
    c = client.get("/api/codes", headers=login("choi.qa")).json()
    assert set(c) == {"SHIPTYPE", "HULLSTAT", "MILESTONE", "BLOCKTYPE", "PLANSTAT", "DWGDISC", "DWGSTAT"}
    assert c["MILESTONE"][0] == {"code": "CUT", "name": "강재절단"}
    assert client.get("/api/codes").status_code == 401


def test_user_options(client, login):
    o = client.get("/api/users/options", headers=login("choi.qa")).json()
    assert "jung.new" not in [x["emp_no"] for x in o]
    names = [x["display_name"] for x in o]
    assert names == sorted(names) and len(o) == 5


def test_weather_t01_regions(client, login):
    h = login("choi.qa")
    w = client.get("/api/weather", params={"region": "거제"}, headers=h).json()
    assert (w["region"], w["source"], w["tempC"], w["condition"], w["humidity"], w["windMs"]) == \
        ("거제", "SAMPLE", 18.9, "구름조금", 61, 4.1)
    assert client.get("/api/weather", headers=h).json()["region"] == "울산"
    assert client.get("/api/weather", params={"region": "목포"}, headers=h).json()["tempC"] == 16.2
    assert client.get("/api/weather", params={"region": "서울"}, headers=h).status_code == 400


def test_weather_t02_fallback_never_fake_live(client, login, monkeypatch):
    h = login("choi.qa")
    w = client.get("/api/weather", headers=h).json()
    assert w["source"] == "SAMPLE" and w["error"]
    monkeypatch.setenv("WEATHER_PROVIDER", "nope")
    assert client.get("/api/weather", headers=h).json()["source"] == "SAMPLE"

    def boom(region):
        raise RuntimeError("down")
    monkeypatch.setitem(weather.PROVIDERS, "boom", boom)
    monkeypatch.setenv("WEATHER_PROVIDER", "boom")
    w = client.get("/api/weather", headers=h).json()
    assert w["source"] == "SAMPLE" and w["error"]
    monkeypatch.setitem(weather.PROVIDERS, "bad", lambda r: {"tempC": "hot"})
    monkeypatch.setenv("WEATHER_PROVIDER", "bad")
    assert client.get("/api/weather", headers=h).json()["source"] == "SAMPLE"
    monkeypatch.setitem(weather.PROVIDERS, "ok", lambda r: {"obsDt": "2026-10-19 10:00", "tempC": 20.0,
                                                           "condition": "맑음", "humidity": 40, "windMs": 1.0})
    monkeypatch.setenv("WEATHER_PROVIDER", "ok")
    w = client.get("/api/weather", headers=h).json()
    assert w["source"] == "LIVE" and w["error"] is None and w["tempC"] == 20.0
