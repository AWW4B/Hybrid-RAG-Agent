
import asyncio
import websockets
import json
import time
import wave
import io
import struct
import uuid

# Helper to make silent audio
def make_silent_wav(duration_ms: int = 500, sample_rate: int = 16000) -> bytes:
    num_samples = int(sample_rate * duration_ms / 1000)
    buf = struct.pack("<" + "h" * num_samples, *([0] * num_samples))
    out = io.BytesIO()
    with wave.open(out, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(buf)
    return out.getvalue()

async def benchmark_turn(session_id):
    uri = f"ws://localhost:8000/ws/chat?session_id={session_id}"
    try:
        async with websockets.connect(uri) as websocket:
            # Prepare silent audio chunk
            audio_chunk = make_silent_wav(500) # 0.5 sec of silence
            
            start_time = time.perf_counter()
            await websocket.send(audio_chunk)
            
            # Wait for audio response
            response = await websocket.recv()
            end_time = time.perf_counter()
            
            duration_ms = (end_time - start_time) * 1000
            
            if isinstance(response, bytes):
                print(f"  [pass] Audio response: {len(response)} bytes in {duration_ms:.0f} ms")
                return duration_ms
            else:
                print(f"  [fail] JSON response: {response}")
                return None
    except Exception as e:
        print(f"  [fail] Connection error: {e}")
        return None

async def main():
    runs = 3
    latencies = []
    print(f"Full pipeline benchmark (STT+LLM+TTS) - {runs} runs")
    for i in range(runs):
        session_id = f"bench-full-{uuid.uuid4()}"
        latency = await benchmark_turn(session_id)
        if latency:
            latencies.append(latency)
        await asyncio.sleep(1) 
    
    if latencies:
        avg = sum(latencies) / len(latencies)
        p50 = sorted(latencies)[len(latencies)//2]
        min_v = min(latencies)
        max_v = max(latencies)
        
        print("\n--- RESULTS ---")
        print(f"Average: {avg:,.0f} ms")
        print(f"p50:     {p50:,.0f} ms")
        print(f"Min:     {min_v:,.0f} ms")
        print(f"Max:     {max_v:,.0f} ms")
    else:
        print("Benchmark failed.")

if __name__ == "__main__":
    asyncio.run(main())
