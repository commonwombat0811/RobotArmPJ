"""
llm_parser.py
LLMから返されたJSON文字列を安全にパースする
"""

import json

def parse_llm_response(response_text: str):
    """
    LLMからのJSON応答文字列をパースする
    @param response_text: LLMが返した文字列
    @return (dict): パースされた辞書 or None
    """
    try:
        # "```json\n{...}\n```" のようなマークダウンブロックや
        # その前後の余計なテキストを考慮し、
        # 最初に出現する '{' と 最後に出現する '}' の間を切り出す

        start_index = response_text.find('{')
        end_index = response_text.rfind('}')

        if start_index == -1 or end_index == -1 or end_index < start_index:
            print(f"[LLMParser] Error: 応答に有効なJSON '{...}' が見つかりません。")
            print(f"   -> 応答: {response_text}")
            return None

        clean_text = response_text[start_index : end_index + 1]

        data = json.loads(clean_text)

        # 必須キーのチェック
        if "command" in data:
            return data
        else:
            print(f"[LLMParser] Error: 'command'キーがJSONにありません: {data}")
            return None

    except json.JSONDecodeError as e:
        print(f"[LLMParser] Error: LLMの応答JSONのパースに失敗: {e}")
        print(f"   -> 切り出し後のJSON: {clean_text}")
        return None
    except Exception as e:
        print(f"[LLMParser] Error: 予期せぬパースエラー: {e}")
        return None
