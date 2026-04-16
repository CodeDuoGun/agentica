from traceback import print_tb
from typing import Any
import wave
from datetime import datetime

import numpy as np
import pyaudio
import torch
from silero_vad import VADIterator, load_silero_vad

torch.set_num_threads(1)
model = load_silero_vad()

CHANNELS = 1
SAMPLE_WIDTH = 2
INPUT_SAMPLE_RATE = 48000
VAD_SAMPLE_RATE = 16000
WINDOW_SIZE_SAMPLES = 512
CHUNK_FRAMES_48K = WINDOW_SIZE_SAMPLES * 3
THRESHOLD = 0.9
INPUT_DEVICE_INDEX = None

import numpy as np

class OnlineDenoiser:
    """
    轻量实时频谱降噪（用于 VAD 前）
    """
    def __init__(self, n_fft=512, alpha=1.2, beta=0.02):
        self.n_fft = n_fft
        self.alpha = alpha
        self.beta = beta
        self.noise_est = None
        self.window = np.hanning(n_fft)

    def process(self, audio: np.ndarray) -> np.ndarray:
        """
        audio: float32 一维数组（16k）
        """
        if len(audio) < self.n_fft:
            return audio

        # 加窗
        frame = audio[:self.n_fft] * self.window

        # FFT
        spec = np.fft.rfft(frame)
        mag = np.abs(spec)
        phase = np.angle(spec)

        # 噪声估计
        if self.noise_est is None:
            self.noise_est = mag
        else:
            self.noise_est = 0.98 * self.noise_est + 0.02 * mag

        # 频谱减法
        clean_mag = mag - self.alpha * self.noise_est
        clean_mag = np.maximum(clean_mag, self.beta * self.noise_est)

        # 重构
        clean_spec = clean_mag * np.exp(1j * phase)
        clean_frame = np.fft.irfft(clean_spec)

        # 拼回原音频长度
        output = np.copy(audio)
        output[:self.n_fft] = clean_frame

        return output.astype(np.float32)

def int2float(sound: np.ndarray) -> np.ndarray:
    abs_max = np.abs(sound).max()
    sound = sound.astype("float32")
    if abs_max > 0:
        sound *= 1 / 32768
    return sound.squeeze()


def downsample_48k_to_16k(audio_48k: np.ndarray) -> np.ndarray:
    return audio_48k[::3]


def float2int16_bytes(sound: np.ndarray) -> bytes:
    sound = np.clip(sound, -1.0, 1.0)
    return (sound * 32767.0).astype(np.int16).tobytes()


def list_input_devices(audio: pyaudio.PyAudio) -> None:
    print("可用输入设备:")
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if info.get("maxInputChannels", 0) > 0:
            print(f"  {i}: {info['name']} | in={info['maxInputChannels']} | sr={info['defaultSampleRate']}")


def get_input_device_index(audio: pyaudio.PyAudio, preferred_index: int | None = None) -> int:
    if preferred_index is not None:
        return preferred_index
    try:
        return audio.get_default_input_device_info()["index"]
    except OSError:
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            if info.get("maxInputChannels", 0) > 0:
                return i
        raise RuntimeError("没有可用的输入设备（麦克风）")


import numpy as np

def volume_limiter(audio: np.ndarray, threshold=0.8):
    """
    简单音量限制（防止爆音/异常峰值）
    """
    max_val = np.max(np.abs(audio)) + 1e-8
    if max_val > threshold:
        audio = audio * (threshold / max_val)
    return audio


def compute_db(audio: np.ndarray):
    """
    计算 RMS 分贝（dBFS）
    """
    rms = np.sqrt(np.mean(audio ** 2) + 1e-8)
    db = 20 * np.log10(rms + 1e-8)
    print("rms", rms, "db", db)
    return db



def main() -> None:
    audio = pyaudio.PyAudio()
    list_input_devices(audio)
    from collections import deque



    device_index = get_input_device_index(audio, INPUT_DEVICE_INDEX)
    device_info = audio.get_device_info_by_index(device_index)

    stream = audio.open(
        format=audio.get_format_from_width(SAMPLE_WIDTH),
        channels=CHANNELS,
        rate=INPUT_SAMPLE_RATE,
        input=True,
        input_device_index=device_index,
        frames_per_buffer=CHUNK_FRAMES_48K,
    )

    vad_iterator = VADIterator(model, threshold=THRESHOLD, sampling_rate=VAD_SAMPLE_RATE)

    denoiser = OnlineDenoiser(n_fft=512, alpha=1.2, beta=0.02)

    print(f"\n{'='*60}")
    print(f"使用输入设备: [{device_index}] {device_info['name']}")
    print(f"VAD 采样率: {VAD_SAMPLE_RATE} Hz, 置信度阈值: {THRESHOLD}")
    print(f"{'='*60}")
    print("开始持续收音（48kHz -> 16kHz + 降噪），按 Ctrl+C 停止\n")

    all_frames: list[bytes] = []

    try:
        buffer_audio = deque[Any](maxlen=16000 * 2)  # 最多缓存2秒（16k）
        is_collecting = False
        triggered = False  # 防止重复打印
        while True:
            audio_chunk_48k = stream.read(CHUNK_FRAMES_48K, exception_on_overflow=False)

            audio_int16_48k = np.frombuffer(audio_chunk_48k, dtype=np.int16)
            audio_float32_48k = int2float(audio_int16_48k)

            # 重采样
            audio_float32_16k = downsample_48k_to_16k(audio_float32_48k)

            # ===== 1️⃣ 音量限制（新增）=====
            audio_float32_16k = volume_limiter(audio_float32_16k, threshold=0.8)

            # ===== 2️⃣ 降噪 =====
            # audio_float32_16k = denoiser.process(audio_float32_16k)

            all_frames.append(float2int16_bytes(audio_float32_16k))

            chunk = torch.from_numpy(audio_float32_16k)

            speech_dict = vad_iterator(chunk, return_seconds=True)

            # ===== 3️⃣ 首次检测到人声 =====
            if speech_dict and "start" in speech_dict:
                if not is_collecting:
                    is_collecting = True
                    buffer_audio.clear()

            # ===== 4️⃣ 如果在收集阶段 =====
            if is_collecting:
                buffer_audio.extend(audio_float32_16k)

                # 缓存满 0.5 秒再判断（避免误触）
                if len(buffer_audio) >= 16000 // 2:
                    audio_np = np.array(buffer_audio)

                    db = compute_db(audio_np)

                    # ===== 5️⃣ 分贝阈值判断 =====
                    # 场景	dB
                    # 安静环境	-50 ~ -40
                    # 正常说话	-35 ~ -25
                    # 大声说话	-25 ~ -10
                    if db > -20:
                        if not triggered:
                            print(f"vad 检测到人声 | 平均分贝: {db:.2f} dB")
                            # triggered = True

                        # 重置（防止一直触发）
                        # is_collecting = False
                        buffer_audio.clear()

    except KeyboardInterrupt:
        print("\n停止收音...")
    finally:
        vad_iterator.reset_states()
        stream.stop_stream()
        stream.close()
        audio.terminate()

        if all_frames:
            output_file = f"vad_full_record_{datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
            with wave.open(str(output_file), "wb") as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(SAMPLE_WIDTH)
                wf.setframerate(VAD_SAMPLE_RATE)
                wf.writeframes(b"".join(all_frames))

            duration_sec = len(all_frames) * WINDOW_SIZE_SAMPLES / VAD_SAMPLE_RATE
            print(f"\n[保存] {output_file} | 时长: {duration_sec:.2f}s | 帧数: {len(all_frames)}")


if __name__ == "__main__":
    main()
