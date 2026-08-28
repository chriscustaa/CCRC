from harness.lmstudio import LMStudioClient

def test_auth_header_explicit():
    c = LMStudioClient("http://localhost:1234", api_token="abc123")
    assert c._headers()["Authorization"] == "Bearer abc123"

def test_auth_header_env(monkeypatch):
    monkeypatch.setenv("LM_API_TOKEN", "envtoken")
    c = LMStudioClient("http://localhost:1234")
    assert c._headers()["Authorization"] == "Bearer envtoken"

def test_no_auth_header(monkeypatch):
    monkeypatch.delenv("LM_API_TOKEN", raising=False)
    c = LMStudioClient("http://localhost:1234")
    assert "Authorization" not in c._headers()
