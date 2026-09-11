import time
import asyncio
from voice.tts import EdgeTTSService
from voice.stt import FasterWhisperSTTService


async def benchmark():
    print("=" * 60)
    print("🚀 Running Surfaces Tiles Voice Assistant Benchmark")
    print("=" * 60)

    # 1. Benchmark TTS
    tts = EdgeTTSService(voice="en-GB-SoniaNeural")
    sample_text = (
        "For kitchen floors, we recommend our durable grey porcelain tiles. "
        "They have an R10 slip rating, perfect for underfloor heating at 28 pounds 50 per square metre."
    )
    print(f"\n[TTS] Synthesizing sample text ({len(sample_text)} characters)...")
    t0 = time.time()
    tts_res = await tts.synthesize(sample_text)
    tts_time = time.time() - t0
    print(f"✅ TTS Generated {len(tts_res['audio_bytes'])} bytes MP3 in {tts_time:.3f}s")

    # 2. Benchmark Faster-Whisper Small on CPU
    stt = FasterWhisperSTTService()
    print("\n[STT] Transcribing synthesized audio with Faster-Whisper Small on CPU (int8)...")
    t1 = time.time()
    stt_res = stt.transcribe(tts_res["audio_bytes"], language="en")
    stt_time = time.time() - t1

    print(f"✅ STT Transcribed {stt_res['duration']:.2f}s of speech in {stt_time:.3f}s")
    print(f"   Real-time factor (RTF): {stt_time / max(stt_res['duration'], 0.1):.2f}x")
    print(f"   Transcribed Text: \"{stt_res['text']}\"")
    print(f"   Detected Language: {stt_res['language']} (confidence: {stt_res['language_probability']})")

    print("\n" + "=" * 60)
    print(f"📊 Summary:")
    print(f"   TTS Latency: {tts_time:.3f}s")
    print(f"   STT Latency (CPU int8): {stt_time:.3f}s")
    print(f"   Total Voice Roundtrip (excluding LLM): {tts_time + stt_time:.3f}s")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(benchmark())
