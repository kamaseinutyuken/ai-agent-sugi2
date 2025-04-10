import os
import httpx
import time
import logging
import pathlib
from typing import List, Dict, Any, Optional, Tuple
from collections import OrderedDict
from dotenv import load_dotenv
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from .models import Message, MessageRole

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("llm_integration")

backend_dir = pathlib.Path(__file__).parent.parent
load_dotenv(backend_dir / ".env")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logger.error("OPENROUTER_API_KEY not found in environment variables")
    raise ValueError("OPENROUTER_API_KEY not found in environment variables")

LLM_MODELS = {
    "gpt-4-turbo": {
        "model": "openai/gpt-4-turbo",
        "role": "チャット内容の論理的構造化",
        "description": "ユーザーの入力を論理的に構造化し、必要な情報を整理します。",
        "acu_estimate": 15  # 推定ACU消費量
    },
    "gemini-pro": {
        "model": "google/gemini-pro",
        "role": "Excelデータ構造の分析",
        "description": "Excelファイルのデータ構造を分析し、適切なセルへの入力方法を提案します。",
        "acu_estimate": 5  # 推定ACU消費量
    },
    "claude-3-opus": {
        "model": "anthropic/claude-3-opus",
        "role": "表現の曖昧さを明確化",
        "description": "ユーザーの曖昧な表現を明確にし、具体的な情報に変換します。",
        "acu_estimate": 20  # 推定ACU消費量
    },
    "mixtral-8x7b": {
        "model": "mistralai/mixtral-8x7b-instruct",
        "role": "細かいニュアンスや例外処理の補完",
        "description": "細かいニュアンスや例外的なケースを処理し、VBAコードの生成を補助します。",
        "acu_estimate": 8  # 推定ACU消費量
    }
}

class LLMIntegration:
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://ai-agent-sugi.example.com",
            "X-Title": "LLM Excel Agent"
        }
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        
        self.max_cache_size = 100
        self.response_cache = OrderedDict()
        self.max_retries = 3
        
        self.total_acu_consumed = 0
        self.api_calls_count = 0
        
        logger.info(f"LLMIntegration initialized with OpenRouter API")
        logger.info(f"Authorization header: Bearer {self.api_key[:10]}...")
        
    def _update_cache(self, key: str, value: str) -> None:
        """
        LRUキャッシュを更新する
        
        Parameters:
        - key: キャッシュキー
        - value: キャッシュする値
        """
        if len(self.response_cache) >= self.max_cache_size:
            self.response_cache.popitem(last=False)
            
        self.response_cache[key] = value
        
    def clear_cache(self) -> None:
        """キャッシュをクリアする"""
        self.response_cache.clear()
        logger.info("Cache cleared")
        
    def get_acu_stats(self) -> Dict[str, Any]:
        """
        ACU消費統計を取得する
        
        Returns:
        - ACU消費統計の辞書
        """
        return {
            "total_acu_consumed": self.total_acu_consumed,
            "api_calls_count": self.api_calls_count,
            "average_acu_per_call": self.total_acu_consumed / self.api_calls_count if self.api_calls_count > 0 else 0
        }
        
    async def call_llm(self, model_key: str, messages: List[Dict[str, str]], force_refresh: bool = False) -> str:
        """
        Call a specific LLM model via OpenRouter API
        
        Parameters:
        - model_key: LLMモデルのキー
        - messages: 送信するメッセージリスト
        - force_refresh: キャッシュを無視して強制的に新しい応答を取得するかどうか
        
        Returns:
        - LLMからの応答テキスト
        
        Raises:
        - ValueError: 不明なモデルキーが指定された場合
        - Exception: API呼び出しに失敗した場合
        """
        if model_key not in LLM_MODELS:
            raise ValueError(f"Unknown model: {model_key}")
            
        message_content = "_".join([f"{m.get('role', '')}:{m.get('content', '')[:50]}" for m in messages])
        cache_key = f"{model_key}_{hash(message_content)}"
        
        if not force_refresh and cache_key in self.response_cache:
            logger.info(f"キャッシュヒット: {model_key} モデル")
            value = self.response_cache.pop(cache_key)
            self.response_cache[cache_key] = value
            return value
            
        model_info = LLM_MODELS[model_key]
        
        payload = {
            "model": model_info["model"],
            "messages": messages
        }
        
        start_time = time.time()
        retries = 0
        last_error = None
        
        while retries < self.max_retries:
            try:
                async with httpx.AsyncClient() as client:
                    logger.info(f"API呼び出し開始: {model_key} モデル")
                    logger.info(f"Sending request to {self.base_url} with headers: {self.headers}")
                    logger.info(f"Payload: {payload}")
                    response = await client.post(
                        self.base_url,
                        headers=self.headers,
                        json=payload,
                        timeout=60.0
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        response_content = result["choices"][0]["message"]["content"]
                        
                        self.api_calls_count += 1
                        estimated_acu = model_info.get("acu_estimate", 10)  # デフォルト値として10を使用
                        self.total_acu_consumed += estimated_acu
                        
                        elapsed_time = time.time() - start_time
                        
                        logger.info(f"API呼び出し成功: {model_key} モデル (推定ACU: {estimated_acu}, 実行時間: {elapsed_time:.2f}秒)")
                        
                        self._update_cache(cache_key, response_content)
                        return response_content
                    else:
                        error_msg = f"API呼び出しエラー (試行 {retries+1}/{self.max_retries}): {response.status_code} - {response.text}"
                        logger.error(error_msg)
                        last_error = Exception(error_msg)
            except Exception as e:
                error_msg = f"例外発生 (試行 {retries+1}/{self.max_retries}): {str(e)}"
                logger.error(error_msg)
                last_error = e
            
            import asyncio
            backoff_time = 1 * (2 ** retries)
            logger.info(f"リトライ待機中: {backoff_time}秒")
            await asyncio.sleep(backoff_time)
            retries += 1
        
        if last_error:
            logger.error(f"API呼び出し失敗 ({self.max_retries}回試行): {str(last_error)}")
            raise Exception(f"API呼び出し失敗 ({self.max_retries}回試行): {str(last_error)}")
        else:
            logger.error("API呼び出し失敗: 不明なエラー")
            raise Exception(f"API呼び出し失敗: 不明なエラー")

    
    async def process_with_all_llms(self, messages: List[Message], excel_data: Optional[Dict[str, Any]] = None, form_data: Optional[Dict[str, Any]] = None) -> List[str]:
        """
        Process the input with all LLMs in sequence
        
        各LLMの役割：
        - GPT-4 Turbo：チャット内容の論理的構造化 - ユーザーの入力を論理的に構造化し、必要な情報を整理
        - Gemini Pro：Excelデータ構造の分析 - Excelファイルのデータ構造を分析し、適切なセルへの入力方法を提案
        - Claude 3 Opus：表現の曖昧さを明確化と追加質問の生成 - ユーザーの曖昧な表現を明確にし、次の質問を生成
        - Mixtral：細かいニュアンスや例外処理の補完 - 細かいニュアンスや例外的なケースを処理し、VBAコード生成を補助
        
        ワークフロー：チャット→追加質問→チャット→追加質問→チャット→情報生成→VBAコード生成
        
        ACU消費の最小化：
        - 会話ラウンドに応じて必要なLLMのみを呼び出す
        - 同じ入力に対する出力をキャッシュして再利用
        - エラー発生時のリトライ戦略
        """
        user_messages = [msg for msg in messages if msg.role == MessageRole.USER]
        conversation_round = len(user_messages)
        
        models_to_use = []
        
        if conversation_round <= 1:
            models_to_use = ["gpt-4-turbo", "claude-3-opus"]
        elif conversation_round < 4:
            models_to_use = ["claude-3-opus"]
        elif conversation_round == 4:
            models_to_use = ["gpt-4-turbo"]
        else:
            models_to_use = ["mixtral-8x7b"]
            
            if excel_data:
                models_to_use.append("gemini-pro")
        
        print(f"会話ラウンド {conversation_round}: 使用するモデル {models_to_use}")
        
        openrouter_messages = [{"role": msg.role.value, "content": msg.content} for msg in messages]
        
        if excel_data or form_data:
            context = "追加情報:\n"
            if form_data:
                context += f"フォームデータ: {form_data}\n"
            if excel_data:
                context += f"Excelデータの概要: {len(excel_data.get('safety_plan_sheet', {}))} 安全計画項目, {len(excel_data.get('risk_assessment_sheet', {}))} リスク評価項目\n"
            
            if openrouter_messages and openrouter_messages[-1]["role"] == "user":
                openrouter_messages[-1]["content"] += f"\n\n{context}"
            else:
                openrouter_messages.append({"role": "system", "content": context})
        
        results = [""] * len(LLM_MODELS)
        model_indices = {model_key: i for i, model_key in enumerate(LLM_MODELS.keys())}
        
        for model_key in models_to_use:
            if model_key not in LLM_MODELS:
                continue
                
            specific_instruction = ""
            if model_key == "claude-3-opus":
                specific_instruction = """
                あなたの主な役割は、ユーザーの曖昧な表現を明確にし、具体的な情報に変換することです。
                また、ユーザーから十分な情報を得るために、次の質問を自動的に生成してください。
                
                質問は具体的で、VBAコード生成に必要な情報を引き出すものにしてください。
                特に以下の情報を収集することが重要です：
                1. 工事の種類と詳細（建築、土木、設備など）
                2. 作業内容の詳細（高所作業、重機使用、電気工事など）
                3. 現場の特性（屋内/屋外、高層/低層など）
                4. 特殊な安全対策が必要な条件（危険物取扱、交通量の多い場所など）
                5. 作業員の資格や経験レベル
                
                必ず質問文で終わるようにしてください。ユーザーが回答しやすいよう、具体的な質問を1-2個に絞って提示してください。
                あなたの回答は自動的にユーザーに表示されるため、「メッセージを受け取りました」などの定型文は使わず、
                直接質問を生成してください。
                """
            elif model_key == "gpt-4-turbo":
                specific_instruction = """
                あなたの主な役割は、ユーザーの入力を論理的に構造化し、必要な情報を整理することです。
                会話の流れを分析し、重要なポイントを抽出してください。
                """
            elif model_key == "gemini-pro":
                specific_instruction = """
                あなたの主な役割は、Excelファイルのデータ構造を分析し、適切なセルへの入力方法を提案することです。
                特に安全施工計画書シートとリスクアセスメントシートの構造に注目してください。
                """
            elif model_key == "mixtral-8x7b":
                specific_instruction = """
                あなたの主な役割は、細かいニュアンスや例外的なケースを処理し、VBAコードの生成を補助することです。
                特に、準備作業→本作業→後始末作業の順にコードを構成することを意識してください。
                """
            
            model_info = LLM_MODELS[model_key]
            model_messages = [
                {"role": "system", "content": f"あなたは{model_info['role']}を担当するAIアシスタントです。{model_info['description']}{specific_instruction}"}
            ] + openrouter_messages
            
            try:
                force_refresh = conversation_round >= 4
                result = await self.call_llm(model_key, model_messages, force_refresh)
                results[model_indices[model_key]] = result
                
                if model_key in ["claude-3-opus", "gpt-4-turbo"]:
                    openrouter_messages.append({"role": "assistant", "content": result})
            except Exception as e:
                print(f"モデル {model_key} の呼び出しに失敗: {str(e)}")
                results[model_indices[model_key]] = f"エラー: {str(e)}"
        
        return results
    
    async def generate_vba_code(self, messages: List[Message], excel_data: Dict[str, Any], form_data: Dict[str, Any]) -> str:
        """Generate VBA code based on the conversation and Excel data"""
        system_prompt = """
        以下の情報に基づいて、Excelファイルに入力するためのVBAコードを生成してください。
        コードは準備作業→本作業→後始末作業の順に構成し、以下の項目を入力する必要があります。
        
        確定事項:
        - 工事名（セルI9）
        - 施工場所（セルI11）
        - 工期（セルI13）
        - 作業者数（セルQ15）
        
        不確定事項（以下のセルに入力）:
        - 安全施工計画書シート：D, AS, BK列（行34-43, 54-73, 81-100, 108-127）
        - リスクアセスメントシート：C, O, Y, AI, AS, CC, AV, CF, BE, CL列（行34, 37, 40, 48, 51, 54, 57, 60, 63, 66, 69, 72, 75, 78, 81, 84, 87, 96, 99, 102, 105, 108, 111, 114, 117, 120, 123, 126, 129, 132, 135, 144, 147, 150, 153, 156, 159, 162, 165, 168, 171, 174, 177, 180, 183, 192, 195, 198, 201, 204, 207, 210, 213, 216, 219, 222, 225, 228, 231, 240～567）
        
        VBAコードはWindowsのExcelで動作するように作成してください。
        """
        
        conversation = "\n".join([f"{msg.role.value}: {msg.content}" for msg in messages])
        
        prompt = f"""
        {system_prompt}
        
        フォームデータ:
        {form_data}
        
        Excelデータ:
        {excel_data}
        
        会話履歴:
        {conversation}
        
        上記の情報に基づいて、VBAコードを生成してください。
        """
        
        vba_code = await self.call_llm("mixtral-8x7b", [{"role": "user", "content": prompt}])
        
        return vba_code
