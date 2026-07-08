import pytest
from fastapi.testclient import TestClient
from app.main import app  # Import ứng dụng FastAPI của bạn

@pytest.fixture(scope="module")
def client():
    # Khởi tạo TestClient của FastAPI
    with TestClient(app) as c:
        yield c