async def test_health(client):
    resp = await client.get("/api/v1/health")
    assert resp.json() == {"status": "ok"}


async def test_unknown_path_uses_error_format(client):
    resp = await client.get("/api/v1/nope")
    assert resp.status_code == 404
    assert resp.json() == {"error": {"code": "NOT_FOUND", "message": "内容不存在或已被删除"}}
