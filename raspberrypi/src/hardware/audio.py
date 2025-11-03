"""
audio.py
sounddevice を使った音声録音（簡易VAD付き）
"""

import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import tempfile
import time

class AudioRecorder:
    def __init__(self, samplerate, channels, silence_threshold, silence_duration):
        self.samplerate = samplerate
        self.channels = channels
        self.threshold = silence_threshold
        self.silence_sec = silence_duration
        self.frames_per_buffer = int(samplerate * 0.1) # 100msごとに判定
        self.silence_buffers_needed = int(self.silence_sec * 10)

    def _calculate_rms(self, data):
        """音声フレームのエネルギー(RMS)を計算"""
        return np.sqrt(np.mean(data**2))

    def listen_and_record(self):
        """
        話しかけられるまで待機し、録音を開始。
        一定時間無音が続いたら録音を終了し、ファイルパスを返す。
        """
        recorded_frames = []
        is_recording = False
        silent_buffers_count = 0

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav", prefix="rec_")
        temp_file.close()

        try:
            # sounddeviceのInputStream
            with sd.InputStream(
                samplerate=self.samplerate,
                channels=self.channels,
                blocksize=self.frames_per_buffer,
                dtype='float32'
            ) as stream:
                while True:
                    # 100ms分の音声データを読み込む
                    frames, overflowed = stream.read(self.frames_per_buffer)
                    if overflowed:
                        print("[Audio] Warning: マイクバッファがオーバーフローしました。")

                    rms = self._calculate_rms(frames)

                    if is_recording:
                        # --- 録音中の処理 ---
                        recorded_frames.append(frames)

                        if rms < self.threshold:
                            silent_buffers_count += 1
                        else:
                            silent_buffers_count = 0 # 無音カウントリセット

                        if silent_buffers_count >= self.silence_buffers_needed:
                            print("[Audio] 無音を検出。録音を終了します。")
                            break # 録音ループ終了

                    else:
                        # --- 待機中の処理 ---
                        if rms > self.threshold:
                            print("[Audio] 音声を検出。録音を開始します...")
                            is_recording = True
                            recorded_frames.append(frames) # 録音開始

            # --- 録音終了後、ファイルに保存 ---
            if recorded_frames:
                recording = np.concatenate(recorded_frames, axis=0)
                wav.write(temp_file.name, self.samplerate, recording)
                return temp_file.name
            else:
                return None

        except Exception as e:
            print(f"[Audio] Error: 録音中にエラー: {e}")
            return None
