async def test_health(client):
    resp = await client.get("/api/v1/health")
    assert resp.json() == {"status": "ok"}


async def test_unknown_path_uses_error_format(client):
    resp = await client.get("/api/v1/nope")
    assert resp.status_code == 404
    assert resp.json() == {"error": {"code": "NOT_FOUND", "message": "内容不存在或已被删除"}}


async def test_android_app_origin_allowed(client):
    resp = await client.options(
        "/api/v1/auth/login",
        headers={"Origin": "https://localhost", "Access-Control-Request-Method": "POST"},
    )
    assert resp.headers["access-control-allow-origin"] == "https://localhost"
