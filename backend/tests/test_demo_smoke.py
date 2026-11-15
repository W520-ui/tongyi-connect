from app.domain.types import ToolCall
from tests.support import Decision
from tests.test_api import assert_workflow_contract


def test_readme_demo_four_steps(api_client):
    client, runtime = api_client
    runtime.provider.decisions.extend(
        [
            Decision(tool_calls=(ToolCall("search", "catalog_search", {"query": "headphones"}),)),
            Decision(
                tool_calls=(
                    ToolCall(
                        "shipping",
                        "catalog_shipping",
                        {"product_id": "headset-pro", "destination": "ES"},
                    ),
                )
            ),
            Decision(reply="The Nebula ANC Headphones Pro ships to Spain in 5–8 business days."),
            Decision(
                tool_calls=(
                    ToolCall(
                        "followup",
                        "catalog_shipping",
                        {"product_id": "headset-pro", "destination": "ES"},
                    ),
                )
            ),
            Decision(reply="它的物流时效为 5–8 个工作日。"),
            Decision(
                tool_calls=(
                    ToolCall(
                        "aftersales",
                        "after_sales_record",
                        {"issue": "耳机收到后无法开机", "product_id": "headset-pro"},
                    ),
                )
            ),
            Decision(reply="已记录售后诉求，等待商家接管。"),
        ]
    )

    def send(message):
        response = client.post(
            "/api/v1/agent/chat", json={"message": message, "session_id": "demo-smoke"}
        )
        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert_workflow_contract(data)
        return data

    # Step 1: language recognition, catalog lookup and English customer reply.
    first = send("请用英文回复：星云降噪耳机 Pro 支持发往西班牙吗？")
    assert first["language"] == "en-US"
    assert "logistics" in first["detected_intents"]
    assert first["matched_product"] == "星云降噪耳机 Pro"
    assert first["reply"] == "The Nebula ANC Headphones Pro ships to Spain in 5–8 business days."

    # Step 2: a follow-up resolves the product from the same session.
    followup = send("那它的物流要多久？")
    assert followup["product_id"] == "headset-pro"
    assert followup["product_confidence"] == 0.96
    assert followup["trace"][0]["name"] == "catalog_shipping"
    assert followup["trace"][0]["ok"] is True
    followup_prompt = runtime.provider.calls[3]["messages"][0].content
    assert "headset-pro" in followup_prompt
    assert "5–8" in followup["reply"]

    # Step 3: after-sales tool invocation and merchant acknowledgment.
    aftersales = send("客户说耳机收到后无法开机，帮我登记售后")
    assert aftersales["needs_human"] is True
    assert aftersales["source"] == "native+human-handoff"
    tickets = client.get("/api/v1/dashboard/handoffs").json()["data"]
    assert len(tickets) == 1
    record_id = tickets[0]["id"]
    response = client.post(f"/api/v1/dashboard/handoffs/{record_id}/acknowledge")
    assert response.status_code == 200
    assert response.json()["data"]["record_id"] == record_id

    # Step 4: dashboard counts, language distribution, archive and health.
    overview = client.get("/api/v1/dashboard/overview").json()["data"]
    assert overview["total_conversations"] == 3
    assert overview["human_handoffs"] == 1
    assert overview["pending_handoffs"] == overview["failed_requests"] == 0
    assert overview["resolution_rate"] == 66.7
    assert {item["code"]: item["count"] for item in overview["languages"]} == {
        "en-US": 1,
        "zh-CN": 2,
    }
    assert {item["code"]: item["count"] for item in overview["intents"]} == {
        "logistics": 2,
        "after_sales": 1,
    }
    recent = client.get("/api/v1/dashboard/recent").json()["data"]
    assert len(recent) == 3
    assert recent[0]["human_acknowledged"] is True
    assert recent[0]["reply"] == aftersales["reply"]
    assert all(item["session_id"] == "demo-smoke" for item in recent)
    assert client.get("/api/v1/dashboard/handoffs").json()["data"] == []
    assert client.get("/api/v1/health").status_code == 200
    assert (
        len(
            [
                turn
                for turn in runtime.service.store.load("demo-smoke").turns
                if turn.role == "user" or turn.role == "assistant" and not turn.tool_calls
            ]
        )
        == 6
    )
    assert any(turn.role == "tool" for turn in runtime.service.store.load("demo-smoke").turns)
    assert len(runtime.provider.calls) == 7
    assert not runtime.provider.decisions
