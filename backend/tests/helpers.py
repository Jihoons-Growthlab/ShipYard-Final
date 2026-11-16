HULL = "8004"  # 시드에 공정이 없는 호선(테스트 공정 생성용)


def mk_plan(client, h, start, end, preds=None, hull=HULL, expect=201, **kw):
    r = client.post(f"/api/hulls/{hull}/plans", json={"proc_cd": kw.pop("proc_cd", "CUT"), "plan_start_dt": start,
                                                      "plan_end_dt": end, "pred_plan_ids": preds or [], **kw}, headers=h)
    assert r.status_code == expect, r.text
    return r.json()["plan_id"] if expect == 201 else r.json()


def add_drawing(conn, no, issued, hull=HULL):
    did = conn.execute("INSERT INTO TB_DWG_Drawing(DrawingNo, DrawingNm, HullNo, DwgStatus) VALUES (?, ?, ?, ?)",
                       (no, no, hull, "ISSUED" if issued else "DRAFT")).lastrowid
    conn.execute("INSERT INTO TB_DWG_Revision(DrawingId, RevNo, RevStatus) VALUES (?, 0, ?)",
                 (did, "ISSUED" if issued else "DRAFT"))
    return did
