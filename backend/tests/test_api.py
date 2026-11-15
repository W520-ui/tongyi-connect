import pytest

from app.agent.models import AgentError, Decision
from app.schemas.agent import AgentChatRequest

WORKFLOW_FIELDS = {
    "reply",
    "merchant_summary",
    "intent",
    "intent_label",
    "detected_intents",
    "detected_intent_labels",
    "task_plan",
    "language",
    "language_label",
    "confidence",
    "product_confidence",
    "matched_product",
    "product_id",
    "matched_products",
    "needs_human",
    "handoff_reason",
    "steps",
    "source",
}
PRODUCT_FIELDS = {
    "id",
    "name",
    "english_name",
    "category",
    "price_usd",
    "stock",
    "shipping_days",
    "specs",
}
OVERVIEW_FIELDS = {
    "total_conversations",
    "failed_requests",
    "human_handoffs",
    "pending_handoffs",
    "resolution_rate",
    "top_intent",
    "languages",
    "intents",
    "started_at",
}
RECENT_FIELDS = {
    "id",
    "created_at",
    "session_id",
    "message",
    "reply",
    "merchant_summary",
    "intent_label",
    "language_label",
    "needs_human",
    "human_acknowledged",
    "handoff_reason",
}


def assert_workflow_contract(data):
    assert WORKFLOW_FIELDS <= data.keys()
    for field in (
        "reply",
        "merchant_summary",
        "intent",
        "intent_label",
        "language",
        "language_label",
        "matched_product",
        "source",
    ):
        assert isinstance(data[field], str), field
    for field in ("detected_intents", "detected_intent_labels", "task_plan", "steps"):
        assert isinstance(data[field], list), field
        assert all(isinstance(item, str) for item in data[field]), field
    for field in ("confidence", "product_confidence"):
        assert type(data[field]) in (int, float), field
        assert 0 <= data[field] <= 1, field
    assert type(data["needs_human"]) is bool
    assert data["product_id"] is None or isinstance(data["product_id"], str)
    assert data["handoff_reason"] is None or isinstance(data["handoff_reason"], str)
    assert data["source"] in {"native", "native+human-handoff"}
    assert isinstance(data["matched_products"], list)
    for product in data["matched_products"]:
        assert PRODUCT_FIELDS <= product.keys()
        assert "aliases" not in product
        assert isinstance(product["specs"], dict)
        assert all(isinstance(value, str) for value in product["specs"].values())


def test_chat_request_field_contract():
    assert set(AgentChatRequest.model_fields) == {
        "message",
        "session_id",
        "username",
        "locale",
        "flags",
    }


@pytest.mark.parametrize("message", ["你好", "Please quote the headphones", "我要退款"])
def test_chat_response_contract(api_client, message):
    client, runtime = api_client
    runtime.provider.decisions.append(Decision(reply="Scripted response."))
    response = client.post("/api/v1/agent/chat", json={"message": message, "session_id": "api"})
    assert response.status_code == 200
    envelope = response.json()
    assert set(envelope) == {"status", "data", "message"}
    assert envelope["status"] == "ok"
    assert envelope["message"] is None
    assert_workflow_contract(envelope["data"])


def test_health_catalog_and_empty_dashboard(api_client):
    client, _ = api_client
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "tongyi-connect-api", "version": "0.1.0"}
    products = client.get("/api/v1/catalog/products").json()
    assert products["status"] == "ok"
    assert len(products["data"]) == 3
    for product in products["data"]:
        assert set(product) == PRODUCT_FIELDS
    overview = client.get("/api/v1/dashboard/overview").json()["data"]
    assert set(overview) == OVERVIEW_FIELDS
    assert overview["total_conversations"] == overview["pending_handoffs"] == 0
    assert overview["resolution_rate"] == 100.0
    assert overview["top_intent"] == "暂无数据"
    for route in ("recent", "handoffs"):
        assert client.get(f"/api/v1/dashboard/{route}").json() == {"status": "ok", "data": []}


def test_handoff_acknowledgment_and_recent_contract(api_client):
    client, _ = api_client
    result = client.post(
        "/api/v1/agent/chat", json={"message": "/handoff", "session_id": "handoff"}
    )
    assert result.status_code == 200
    ticket = client.get("/api/v1/dashboard/handoffs").json()["data"][0]
    assert set(ticket) == RECENT_FIELDS
    assert ticket["needs_human"] is True
    record_id = ticket["id"]
    path = f"/api/v1/dashboard/handoffs/{record_id}/acknowledge"
    assert client.post(path).json() == {"status": "ok", "data": {"record_id": record_id}}
    assert client.post(path).status_code == 404
    assert client.get("/api/v1/dashboard/handoffs").json()["data"] == []
    recent = client.get("/api/v1/dashboard/recent").json()["data"][0]
    assert set(recent) == RECENT_FIELDS
    assert recent["human_acknowledged"] is True
    overview = client.get("/api/v1/dashboard/overview").json()["data"]
    assert overview["human_handoffs"] == 1
    assert overview["pending_handoffs"] == 0


@pytest.mark.parametrize(
    "payload",
    [
        {"message": ""},
        {"message": "x" * 20001},
        {"message": "hi", "extra": True},
        {"message": "hi", "flags": {"unknown": True}},
    ],
)
def test_chat_rejects_invalid_requests_without_model_calls(api_client, payload):
    client, runtime = api_client
    assert client.post("/api/v1/agent/chat", json=payload).status_code == 422
    assert runtime.provider.calls == []
    assert runtime.metrics.snapshot()["total_conversations"] == 0


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/dashboard/recent?limit=0",
        "/api/v1/dashboard/recent?limit=21",
        "/api/v1/dashboard/handoffs?limit=0",
        "/api/v1/dashboard/handoffs?limit=51",
    ],
)
def test_dashboard_limit_validation(api_client, path):
    client, _ = api_client
    assert client.get(path).status_code == 422


def test_missing_handoff_returns_404(api_client):
    client, _ = api_client
    response = client.post("/api/v1/dashboard/handoffs/missing/acknowledge")
    assert response.status_code == 404
    assert response.json() == {"detail": "待接管记录不存在或已处理"}


@pytest.mark.parametrize("upstream_status,expected", [(None, 503), (502, 502)])
def test_model_errors_count_failures_without_archiving(api_client, upstream_status, expected):
    client, runtime = api_client
    runtime.provider.decisions.append(AgentError("Scripted failure", status_code=upstream_status))
    response = client.post("/api/v1/agent/chat", json={"message": "hello", "session_id": "error"})
    assert response.status_code == expected
    assert response.json() == {"detail": "Scripted failure"}
    assert runtime.metrics.snapshot()["failed_requests"] == 1
    assert runtime.metrics.snapshot()["total_conversations"] == 0
    assert runtime.engine.store.load("error").turns == []


def test_missing_model_configuration_does_not_call_model(api_client):
    client, runtime = api_client
    runtime.provider.is_configured = False
    response = client.post("/api/v1/agent/chat", json={"message": "hello"})
    assert response.status_code == 503
    assert "AGENT_LLM_API_KEY" in response.json()["detail"]
    assert "test-key" not in response.text
    assert runtime.provider.calls == []
