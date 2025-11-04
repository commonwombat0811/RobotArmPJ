# 「思考」と「指示」を担当する、低速・ブロッキングOKなプロセス。
# 音声入力 -> STT API -> LLM API -> JSON解析 -> プロセスAへ指示


import multiprocessing as mp
import time
from openai import OpenAI
import config
from src.hardware.audio import AudioRecorder
from src.processing.llm_parser import parse_llm_response

class OrchestratorProcess(mp.Process):

    def __init__(self, task_queue):
        super().__init__()
        self.task_queue = task_queue
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        self.recorder = AudioRecorder(
            samplerate=config.AUDIO_SAMPLE_RATE,
            channels=config.AUDIO_CHANNELS,
            silence_threshold=config.AUDIO_SILENCE_THRESHOLD,
            silence_duration=config.AUDIO_SILENCE_DURATION
        )
        print(f"[Orchestrator] プロセスB (PID: {self.pid}) を初期化")

    def transcribe_audio(self, audio_filepath):
        """Whisper APIで音声をテキストに変換"""
        print("[Orchestrator] Whisper APIに送信中...")
        try:
            with open(audio_filepath, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="ja" # 日本語を指定
                )
            print(f"[Orchestrator] 認識結果: {transcription.text}")
            return transcription.text
        except Exception as e:
            print(f"[Orchestrator] Whisper APIエラー: {e}")
            return None

    def get_llm_instruction(self, text):
        """LLM APIでテキストをJSONコマンドに変換"""
        print("[Orchestrator] LLM APIに送信中...")

        # ★★★ プロンプトエンジニアリングの核心 ★★★
        system_prompt = """
            あなたはロボットアームの司令塔です。
            ユーザーからの自然言語の指示を、以下の厳密なJSON形式に変換してください。

            1. 物体を探して掴む:
            {"command": "PICKUP", "target": "物体名"}
            2. 物体を置く:
            {"command": "PLACE", "location": "場所名"}
            3. 停止:
            {"command": "STOP"}

            例:
            User: "りんごを掴んで" -> {"command": "PICKUP", "target": "りんご"}
            User: "それをテーブルに置いて" -> {"command": "PLACE", "location": "テーブル"}
            User: "止まって" -> {"command": "STOP"}

            指示が無効な場合は {"command": "INVALID"} と返してください。
            JSONのみを返答してください。
            """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4-turbo", # または gpt-3.5-turbo
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                response_format={"type": "json_object"}
            )
            json_response = response.choices[0].message.content
            print(f"[Orchestrator] LLM応答 (JSON): {json_response}")
            return json_response
        except Exception as e:
            print(f"[Orchestrator] LLM APIエラー: {e}")
            return None

    def run(self):
        """プロセスのメインループ (ブロッキングOK)"""
        print(f"[Orchestrator] 思考プロセス実行中 (PID: {self.pid})...")
        while True:
            try:
                # 1. 音声入力を待機 (ここで無音ならブロック)
                print("\n[Orchestrator] マイク入力待機中... (話しかけてください)")
                audio_filepath = self.recorder.listen_and_record()

                # 2. 音声をテキストに変換 (ここで数秒ブロック)
                transcribed_text = self.transcribe_audio(audio_filepath)
                if not transcribed_text:
                    continue

                # 3. テキストをLLMコマンドに変換 (ここで数秒ブロック)
                llm_json_command = self.get_llm_instruction(transcribed_text)
                if not llm_json_command:
                    continue

                # 4. JSONを辞書にパース
                task = parse_llm_response(llm_json_command)

                # 5. パース成功したら、リアルタイムプロセスAに指示を送信
                if task and task.get("command") != "INVALID":
                    print(f"[Orchestrator] タスクキューに指示を送信: {task}")
                    self.task_queue.put(task)

                time.sleep(0.1) # 念のため

            except KeyboardInterrupt:
                print("[Orchestrator] 終了シグナル受信。")
                break
            except Exception as e:
                print(f"[Orchestrator] メインループでエラー: {e}")
                time.sleep(1)

