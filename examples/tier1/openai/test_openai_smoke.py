"""Offline smoke test for docs/frameworks/openai-responses-and-agents-sdk.md.

A stdlib HTTP server impersonates the Responses API; no network, no credentials. It exercises the
calls the page makes (conversations.create, responses.create, @function_tool, Runner.run) against
the INSTALLED openai / openai-agents, so a breaking rename fails here. Model name is a label only.
"""
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from agents import Agent, Runner, function_tool, set_default_openai_client, set_tracing_disabled
from openai import AsyncOpenAI, OpenAI

RESPONSE = {
    "id": "resp_1", "object": "response", "created_at": 1, "status": "completed", "model": "fake-model",
    "output": [{"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
                "content": [{"type": "output_text", "text": "fake answer", "annotations": []}]}],
    "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
}
CONVERSATION = {"id": "conv_1", "object": "conversation", "created_at": 1, "metadata": {}}


@pytest.fixture()
def server():
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("content-length", 0)))
            seen.append((self.path, json.loads(raw or b"{}")))
            body = json.dumps(CONVERSATION if self.path.endswith("/conversations") else RESPONSE).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/v1", seen
    srv.shutdown()
    srv.server_close()


def test_responses_and_conversations(server):
    base_url, seen = server
    client = OpenAI(api_key="fake", base_url=base_url, max_retries=0)
    conversation = client.conversations.create()
    response = client.responses.create(
        model="fake-model", conversation=conversation.id,
        instructions="You are a concise study tutor.", input="Explain checkpointing.",
    )
    assert response.output_text == "fake answer"
    path, body = seen[-1]
    assert path == "/v1/responses"
    assert body["conversation"] == "conv_1" and body["instructions"] and body["input"]


def test_function_tool_and_runner(server):
    base_url, _ = server

    @function_tool
    def multiply(a: int, b: int) -> int:
        """Multiply two integers without external side effects."""
        return a * b

    agent = Agent(name="Study tutor", model="fake-model", instructions="Use the tool.", tools=[multiply])
    assert multiply.params_json_schema["required"] == ["a", "b"]

    set_default_openai_client(AsyncOpenAI(api_key="fake", base_url=base_url, max_retries=0), use_for_tracing=False)
    set_tracing_disabled(True)
    result = asyncio.run(Runner.run(agent, "What is 12 times 7?"))
    assert result.final_output == "fake answer"
    assert len(result.to_input_list()) == 2  # user item + assistant item
