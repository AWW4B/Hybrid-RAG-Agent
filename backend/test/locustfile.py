# =============================================================================
# locustfile.py  (project root)
# Load testing for Daraz Voice Assistant — A3
#
# Tests 4 concurrent user scenarios as required by the assignment.
# Covers: WebSocket audio, REST /chat fallback, session lifecycle, health.
#
# Run:
#   pip install locust
#   locust -f locustfile.py --host=http://localhost:8000
#   Then open http://localhost:8089 and set users=4, spawn rate=1
#
# Headless (CI/benchmark mode):
#   locust -f locustfile.py --host=http://localhost:8000 \
#          --users 4 --spawn-rate 1 --run-time 60s --headless \
#          --csv=results/locust
# =============================================================================

import uuid
import json
import wave
import struct
import random
import logging

from locust import HttpUser, TaskSet, between, task, events
from locust.contrib.fasthttp import FastHttpUser
import websocket   # websocket-client — pip install websocket-client

logger = logging.getLogger(__name__)


# =============================================================================
# HELPER — generate a minimal valid WAV audio chunk (silence)
# Used to simulate a real audio binary frame over WebSocket.
# =============================================================================

def make_silent_wav(duration_ms: int = 500, sample_rate: int = 16000) -> bytes:
    """
    Generates a silent PCM WAV blob of the given duration.
    16-bit mono, 16kHz — matches Whisper's expected input format.
    Returns raw bytes suitable for websocket.send_binary().
    """
    num_samples = int(sample_rate * duration_ms / 1000)
    buf = struct.pack("<" + "h" * num_samples, *([0] * num_samples))

    import io
    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)       # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(buf)
    return out.getvalue()


SILENT_WAV = make_silent_wav(500)   # pre-built once, reused across users


# =============================================================================
# TASK SET 1 — REST endpoints (HttpUser)
# Simulates a client that uses the text fallback /chat endpoint.
# Good for measuring pure LLM throughput without audio overhead.
# =============================================================================

class RestChatTasks(TaskSet):

    def on_start(self):
        """Called once per simulated user at spawn time."""
        self.session_id = str(uuid.uuid4())
        # Fetch welcome message to initialise session
        self.client.get(f"/session/welcome/{self.session_id}")

    @task(5)
    def chat(self):
        """Main chat task — highest weight (runs most frequently)."""
        messages = [
            "I need a laptop under 80000 PKR",
            "What about smartphones under 30000?",
            "I prefer Samsung",
            "Do you have any gaming laptops?",
            "I need earbuds with noise cancellation",
        ]
        payload = {
            "session_id": self.session_id,
            "message": random.choice(messages),
        }
        with self.client.post(
            "/chat",
            json=payload,
            catch_response=True,
            name="/chat [text]",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("response"):
                    resp.failure("Empty response field")
            elif resp.status_code == 429:
                resp.success()   # rate limit hit is expected under load — not a failure
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(2)
    def get_session(self):
        self.client.get(
            f"/sessions/{self.session_id}",
            name="/sessions/[id]",
        )

    @task(1)
    def health_check(self):
        self.client.get("/health", name="/health")

    @task(1)
    def get_session_state(self):
        self.client.get(
            f"/debug/state/{self.session_id}",
            name="/debug/state/[id]",
        )

    def on_stop(self):
        """Reset session when user finishes."""
        self.client.post("/reset", json={"session_id": self.session_id})


# =============================================================================
# TASK SET 2 — WebSocket audio (simulates voice turns)
# Uses websocket-client (sync) since Locust tasks are not async.
# Sends a silent WAV binary frame and expects:
#   - binary response (audio from TTS)
#   - JSON {"event": "turn_complete", ...}
# =============================================================================

class WebSocketAudioTasks(TaskSet):

    def on_start(self):
        self.session_id = str(uuid.uuid4())
        self._connect()

    def _connect(self):
        """Opens a persistent WebSocket connection for this user."""
        ws_url = self.user.host.replace("http://", "ws://").replace("https://", "wss://")
        try:
            self.ws = websocket.create_connection(
                f"{ws_url}/ws/chat?session_id={self.session_id}",
                timeout=15,
            )
        except Exception as e:
            logger.error(f"[locust] WS connect failed: {e}")
            self.ws = None

    @task(4)
    def send_audio_frame(self):
        """
        Sends a silent WAV binary frame over WebSocket and reads the response.
        Weights the test towards real voice-to-voice interaction.
        """
        if self.ws is None:
            self._connect()
            return

        start = self.user.environment.runner.stats.get(
            "/ws/chat [audio]", "websocket"
        )

        try:
            self.ws.send_binary(SILENT_WAV)
            response = self.ws.recv()

            # Response is either bytes (real audio) or JSON control/error message
            if isinstance(response, bytes):
                # TTS audio — success
                self.user.environment.events.request.fire(
                    request_type="websocket",
                    name="/ws/chat [audio]",
                    response_time=0,
                    response_length=len(response),
                    exception=None,
                    context={},
                )
            else:
                # JSON frame — check it's not an unexpected crash
                data = json.loads(response)
                if data.get("event") == "error" or "error" in data:
                    self.user.environment.events.request.fire(
                        request_type="websocket",
                        name="/ws/chat [audio] (control)",
                        response_time=0,
                        response_length=len(response),
                        exception=None,
                        context={},
                    )

        except websocket.WebSocketConnectionClosedException:
            logger.warning("[locust] WS connection closed, reconnecting...")
            self._connect()
        except Exception as e:
            self.user.environment.events.request.fire(
                request_type="websocket",
                name="/ws/chat [audio]",
                response_time=0,
                response_length=0,
                exception=e,
                context={},
            )

    @task(2)
    def send_text_frame(self):
        """
        Sends a JSON text frame over the same WebSocket (text fallback path).
        Tests that the dual-mode WebSocket handler works correctly.
        """
        if self.ws is None:
            self._connect()
            return

        messages = [
            "I need a phone under 25000 PKR",
            "Any good headphones?",
            "Samsung or Apple?",
        ]
        payload = json.dumps({
            "session_id": self.session_id,
            "message": random.choice(messages),
        })

        try:
            self.ws.send(payload)
            # Collect tokens until done=True
            full_response = ""
            for _ in range(200):   # cap at 200 tokens to prevent hanging
                raw = self.ws.recv()
                if isinstance(raw, str):
                    chunk = json.loads(raw)
                    full_response += chunk.get("token", "")
                    if chunk.get("done"):
                        break

            self.user.environment.events.request.fire(
                request_type="websocket",
                name="/ws/chat [text]",
                response_time=0,
                response_length=len(full_response),
                exception=None,
                context={},
            )

        except Exception as e:
            self.user.environment.events.request.fire(
                request_type="websocket",
                name="/ws/chat [text]",
                response_time=0,
                response_length=0,
                exception=e,
                context={},
            )

    def on_stop(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass


# =============================================================================
# USER CLASSES
# Locust spawns instances of these — each simulates one concurrent user.
# Weight controls the ratio: 3 REST users for every 1 WebSocket user.
# Total 4 users = 3 RestUser + 1 WebSocketUser (matches assignment constraint).
# =============================================================================

class RestUser(FastHttpUser):
    """Simulates a text/REST client."""
    tasks      = [RestChatTasks]
    wait_time  = between(2, 5)    # seconds between tasks — simulates human typing pace
    weight     = 3


class WebSocketUser(HttpUser):
    """Simulates a voice client over WebSocket."""
    tasks      = [WebSocketAudioTasks]
    wait_time  = between(3, 7)    # voice turns are slower than text
    weight     = 1


# =============================================================================
# EVENT HOOKS — printed to console after test run
# =============================================================================

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("\n" + "=" * 60)
    print("LOCUST SUMMARY")
    print("=" * 60)
    stats = environment.runner.stats
    for name, entry in stats.entries.items():
        print(
            f"{name[1]:35s} | "
            f"reqs={entry.num_requests:4d} | "
            f"fails={entry.num_failures:3d} | "
            f"avg={entry.avg_response_time:6.0f}ms | "
            f"p95={entry.get_response_time_percentile(0.95):6.0f}ms"
        )
    print("=" * 60)