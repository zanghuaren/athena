async def test_documentation_is_private_by_default(client):
    for path in ("/api/docs", "/api/openapi.json", "/api/redoc"):
        response = await client.get(path)
        assert response.status_code == 404
