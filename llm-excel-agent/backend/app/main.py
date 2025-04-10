from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Dict, Any, Optional
import json
import os
from dotenv import load_dotenv
import base64
from io import BytesIO

from .models import Message, ChatRequest, FormData, VBACodeResponse, MessageRole
from .llm_integration import LLMIntegration
from .excel_processor import ExcelProcessor

load_dotenv()

app = FastAPI()

# Disable CORS. Do not remove this for full-stack development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

llm_service = LLMIntegration()
excel_service = ExcelProcessor()

conversation_store: Dict[str, List[Message]] = {}
excel_data_store: Dict[str, Dict[str, Any]] = {}
form_data_store: Dict[str, Dict[str, Any]] = {}
question_round_store: Dict[str, int] = {}  # Track question rounds

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}
    
@app.get("/api/acu-stats")
async def acu_stats():
    """Get ACU consumption statistics"""
    global llm_service
    if not llm_service:
        llm_service = LLMIntegration()
    return llm_service.get_acu_stats()
    
@app.post("/api/clear-cache")
async def clear_cache():
    """Clear the LLM response cache"""
    global llm_service
    if not llm_service:
        llm_service = LLMIntegration()
    llm_service.clear_cache()
    return {"status": "ok", "message": "Cache cleared successfully"}

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """
    Process chat messages and generate responses using multiple LLMs
    
    インタラクティブ質問プロセス（3回以上）:
    - 初回：工事名、施工場所、工期、作業員数など確定情報を聞く
    - 2回目以降：LLMが不足と判断した情報を追加で質問（Claude 3が担当）
    - 最終確認：入力項目を整理してユーザーに最終確認をする
    - VBAコード生成：確認後にコードを生成
    
    ワークフロー：チャット→追加質問→チャット→追加質問→チャット→情報生成→VBAコード生成
    """
    session_id = "default"  # Use a single session for simplicity
    
    if session_id not in conversation_store:
        conversation_store[session_id] = []
        question_round_store[session_id] = 0
    
    conversation_store[session_id].append(request.messages[-1])
    
    question_round_store[session_id] += 1
    current_round = question_round_store[session_id]
    
    if request.form_data:
        form_data_store[session_id] = request.form_data
    
    if request.file_data:
        excel_data_store[session_id] = request.file_data
    
    try:
        llm_responses = await llm_service.process_with_all_llms(
            conversation_store[session_id],
            excel_data_store.get(session_id),
            form_data_store.get(session_id)
        )
        
        if current_round == 1:
            system_message = Message(
                role=MessageRole.SYSTEM,
                content="あなたは工事現場の安全計画に関する情報を収集するアシスタントです。最初の質問として、工事名、施工場所、工期、作業員数などの基本情報を尋ねてください。"
            )
            
            temp_messages = [system_message] + conversation_store[session_id]
            
            claude_responses = await llm_service.process_with_all_llms(temp_messages)
            response_content = claude_responses[2]  # Claude's response (index 2)
            
            if not response_content or len(response_content.strip()) == 0:
                response_content = "工事名、施工場所、工期、作業員数などの確定情報を教えてください。"
        
        elif current_round < 4:
            response_content = llm_responses[2]  # Claude's response (index 2)
        
        elif current_round == 4:
            form_info = ""
            if session_id in form_data_store:
                form_data = form_data_store[session_id]
                form_info = f"""
                【確定情報】
                工事名: {form_data.get('project_name', '未入力')}
                施工場所: {form_data.get('location', '未入力')}
                工期: {form_data.get('period', '未入力')}
                作業者数: {form_data.get('workers', '未入力')}
                """
            
            conversation_summary = llm_responses[0]
            
            response_content = f"""
            これまでの情報を整理しました。以下の内容で最終確認をお願いします。
            
            {form_info}
            
            【会話から抽出した情報】
            {conversation_summary}
            
            この情報でVBAコードを生成してよろしいですか？
            不足している情報があれば教えてください。
            """
        
        else:
            if session_id in excel_data_store and session_id in form_data_store:
                last_user_message = request.messages[-1].content.lower()
                if "はい" in last_user_message or "ok" in last_user_message or "よろしい" in last_user_message:
                    vba_code = await llm_service.generate_vba_code(
                        conversation_store[session_id],
                        excel_data_store[session_id],
                        form_data_store[session_id]
                    )
                    response_content = f"VBAコードを生成しました。以下のコードをExcelマクロとして使用できます：\n\n```vba\n{vba_code}\n```"
                else:
                    response_content = llm_responses[2]
            else:
                response_content = "Excelファイルと必要な情報をすべて提供してください。VBAコードを生成するには、Excelファイルのアップロードと工事名、施工場所、工期、作業員数の情報が必要です。"
        
        assistant_message = Message(role=MessageRole.ASSISTANT, content=response_content)
        conversation_store[session_id].append(assistant_message)
        
        return {
            "message": assistant_message,
            "conversation": conversation_store[session_id],
            "round": current_round
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM処理エラー: {str(e)}")

@app.post("/api/upload-excel")
async def upload_excel(file: UploadFile = File(...)):
    """
    Upload and process Excel file
    """
    try:
        if not file.filename.endswith('.xlsm'):
            raise HTTPException(status_code=400, detail="XLSMファイル(.xlsm)のみアップロード可能です。")
        
        file_content = await file.read()
        
        excel_data = await excel_service.process_excel_file(file_content)
        
        session_id = "default"
        excel_data_store[session_id] = excel_data
        
        return {
            "message": "Excelファイルが正常に処理されました。",
            "data": excel_data
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Excelファイル処理エラー: {str(e)}")

@app.post("/api/submit-form")
async def submit_form(form_data: FormData):
    """
    Submit form data with project details
    """
    try:
        session_id = "default"
        form_data_store[session_id] = form_data.dict()
        
        return {
            "message": "フォームデータが正常に保存されました。",
            "data": form_data.dict()
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"フォームデータ処理エラー: {str(e)}")

@app.post("/api/generate-vba")
async def generate_vba():
    """
    Generate VBA code based on conversation, Excel data, and form data
    """
    session_id = "default"
    
    if session_id not in excel_data_store:
        raise HTTPException(status_code=400, detail="Excelファイルがアップロードされていません。")
    
    if session_id not in form_data_store:
        raise HTTPException(status_code=400, detail="フォームデータが提供されていません。")
    
    if session_id not in conversation_store or len(conversation_store[session_id]) < 2:
        raise HTTPException(status_code=400, detail="十分な会話履歴がありません。")
    
    try:
        vba_code = await llm_service.generate_vba_code(
            conversation_store[session_id],
            excel_data_store[session_id],
            form_data_store[session_id]
        )
        
        response = VBACodeResponse(
            vba_code=vba_code,
            excel_data=excel_data_store[session_id],
            messages=conversation_store[session_id]
        )
        
        return response
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VBAコード生成エラー: {str(e)}")

@app.get("/api/conversation")
async def get_conversation():
    """
    Get current conversation history
    """
    session_id = "default"
    
    if session_id not in conversation_store:
        return {"conversation": []}
    
    return {"conversation": conversation_store[session_id]}

@app.delete("/api/reset")
async def reset_conversation():
    """
    Reset the conversation and stored data
    """
    session_id = "default"
    
    if session_id in conversation_store:
        del conversation_store[session_id]
    
    if session_id in excel_data_store:
        del excel_data_store[session_id]
    
    if session_id in form_data_store:
        del form_data_store[session_id]
    
    if session_id in question_round_store:
        del question_round_store[session_id]
    
    return {"message": "会話とデータがリセットされました。"}
