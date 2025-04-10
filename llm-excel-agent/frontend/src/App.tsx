import { useState, useRef, FormEvent } from 'react'
import { Upload, Send, FileSpreadsheet, Bot, RefreshCw } from 'lucide-react'
import './App.css'

import { Button } from './components/ui/button'
import { Input } from './components/ui/input'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from './components/ui/card'
import { FormControl, FormItem, FormLabel } from './components/ui/form'
import { ScrollArea } from './components/ui/scroll-area'
import { Alert, AlertDescription } from './components/ui/alert'

interface Message {
  id: string;
  content: string;
  sender: 'user' | 'ai';
  timestamp: Date;
}

interface FormData {
  projectName: string;
  location: string;
  period: string;
  workerCount: string;
}

interface UIMessage {
  id: string;
  content: string;
  sender: 'user' | 'ai';
  timestamp: Date;
}

function App() {
  const [messages, setMessages] = useState<UIMessage[]>([]);
  const [currentMessage, setCurrentMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isFileUploaded, setIsFileUploaded] = useState(false);
  const [fileData, setFileData] = useState(null);
  const [apiFormData, setApiFormData] = useState(null);
  
  const [formData, setFormData] = useState<FormData>({
    projectName: '',
    location: '',
    period: '',
    workerCount: ''
  });
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const handleFileChange = (event: any) => {
    const file = event.target.files?.[0] || null;
    if (file && file.name.endsWith('.xlsm')) {
      setSelectedFile(file);
      setIsFileUploaded(true);
      setIsLoading(true);
      
      const formData = new FormData();
      formData.append('file', file);
      
      fetch('http://localhost:8000/api/upload-excel', {
        method: 'POST',
        body: formData,
      })
      .then(response => response.json())
      .then(data => {
        setFileData(data.data);
        addMessage(`Excelファイル "${file.name}" がアップロードされました。ナレッジベースを生成しています。`, 'ai');
      })
      .catch(error => {
        console.error('File upload error:', error);
        addMessage(`ファイルのアップロードに失敗しました。`, 'ai');
      })
      .finally(() => {
        setIsLoading(false);
      });
    } else if (file) {
      alert('アップロードできるのは.xlsmファイルのみです。');
    }
  };
  
  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };
  
  const handleSubmitMessage = (e: FormEvent) => {
    e.preventDefault();
    if (currentMessage.trim() && !isLoading) {
      addMessage(currentMessage, 'user');
      setCurrentMessage('');
      setIsLoading(true);
      
      const apiMessages = messages
        .filter(msg => msg.sender === 'user' || msg.sender === 'ai')
        .map(msg => ({
          role: msg.sender === 'user' ? 'user' : 'assistant',
          content: msg.content
        }));
      
      apiMessages.push({
        role: 'user',
        content: currentMessage
      });
      
      fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messages: apiMessages,
          file_data: fileData,
          form_data: apiFormData
        }),
      })
      .then(response => {
        if (!response.ok) {
          throw new Error('API response was not ok');
        }
        return response.json();
      })
      .then(data => {
        console.log('API response:', data);
        if (data && data.message && data.message.content) {
          addMessage(data.message.content, 'ai');
        } else if (data && data.message) {
          addMessage(String(data.message), 'ai');
        } else {
          addMessage('応答の形式が正しくありません。', 'ai');
        }
      })
      .catch(error => {
        console.error('Chat error:', error);
        addMessage('エラーが発生しました。もう一度お試しください。', 'ai');
      })
      .finally(() => {
        setIsLoading(false);
      });
    }
  };
  
  const addMessage = (content: string, sender: 'user' | 'ai') => {
    const newMessage: UIMessage = {
      id: Date.now().toString(),
      content,
      sender,
      timestamp: new Date()
    };
    
    setMessages(prev => [...prev, newMessage]);
    
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  };
  
  const handleFormChange = (field: keyof FormData, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
  };
  
  const handleFormSubmit = (e: FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    
    const apiData = {
      project_name: formData.projectName,
      location: formData.location,
      period: formData.period,
      workers: parseInt(formData.workerCount) || 0
    };
    
    fetch('http://localhost:8000/api/submit-form', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(apiData),
    })
    .then(response => {
      if (!response.ok) {
        throw new Error('API response was not ok');
      }
      return response.json();
    })
    .then(data => {
      setApiFormData(data.data);
      
      addMessage(`確定情報が入力されました:
工事名: ${formData.projectName} (セルI9)
施工場所: ${formData.location} (セルI11)
工期: ${formData.period} (セルI13)
作業者数: ${formData.workerCount} (セルQ15)`, 'ai');
    })
    .catch(error => {
      console.error('Form submission error:', error);
      addMessage('フォームデータの送信に失敗しました。', 'ai');
    })
    .finally(() => {
      setIsLoading(false);
    });
  };
  
  const handleReset = () => {
    if (window.confirm('会話とデータをリセットしますか？')) {
      setIsLoading(true);
      
      fetch('http://localhost:8000/api/reset', {
        method: 'DELETE',
      })
      .then(() => {
        setMessages([]);
        setFileData(null);
        setSelectedFile(null);
        setIsFileUploaded(false);
        setFormData({
          projectName: '',
          location: '',
          period: '',
          workerCount: ''
        });
      })
      .catch(error => {
        console.error('Error:', error);
        alert('リセットに失敗しました。');
      })
      .finally(() => {
        setIsLoading(false);
      });
    }
  };
  
  return (
    <div className="container mx-auto p-4 max-w-6xl">
      <header className="mb-6">
        <h1 className="text-3xl font-bold text-center mb-2">LLM Excel エージェント</h1>
        <p className="text-center text-gray-600">
          複数のLLMを連携させ、Excelファイルへの入力を自動化するAIエージェント
        </p>
      </header>
      
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Left Column - Chat & File Upload */}
        <div className="md:col-span-2">
          <Card className="h-full flex flex-col">
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle className="flex items-center">
                    <Bot className="mr-2" size={20} />
                    チャットインターフェース
                  </CardTitle>
                  <CardDescription>
                    情報を入力するか、Excelファイルをアップロードしてください
                  </CardDescription>
                </div>
                <Button 
                  variant="outline" 
                  size="sm" 
                  onClick={handleReset}
                  disabled={isLoading}
                >
                  <RefreshCw className="h-4 w-4 mr-2" />
                  リセット
                </Button>
              </div>
            </CardHeader>
            
            <CardContent className="flex-grow">
              {/* File Upload Area */}
              <div className="mb-4">
                <h2 className="text-xl font-bold mb-2">Excelファイルのアップロード</h2>
                <p className="text-sm text-gray-600 mb-2">
                  （※ファイルアップロードはナレッジベース生成のみに使用されます。VBAコード生成はチャットでの対話プロセスを通じて行います）
                </p>
                <div 
                  className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer hover:bg-gray-50 transition-colors ${isFileUploaded ? 'border-green-500 bg-green-50' : 'border-gray-300'}`}
                  onClick={handleUploadClick}
                >
                  <input 
                    type="file" 
                    ref={fileInputRef} 
                    onChange={handleFileChange} 
                    className="hidden" 
                    accept=".xlsm" 
                  />
                  <div className="flex flex-col items-center justify-center py-4">
                    {isFileUploaded ? (
                      <>
                        <FileSpreadsheet className="h-8 w-8 text-green-500 mb-2" />
                        <p className="text-sm font-medium">{selectedFile?.name}</p>
                        <p className="text-xs text-gray-500 mt-1">ファイルがアップロードされました</p>
                      </>
                    ) : (
                      <>
                        <Upload className="h-8 w-8 text-gray-400 mb-2" />
                        <p className="text-sm font-medium">Excelファイル (.xlsm) をアップロード</p>
                        <p className="text-xs text-gray-500 mt-1">クリックまたはドラッグ&ドロップ</p>
                      </>
                    )}
                  </div>
                </div>
              </div>
              
              {/* Chat Messages */}
              <ScrollArea className="h-[400px] pr-4">
                {messages.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-full text-gray-400">
                    <Bot size={48} className="mb-4 opacity-50" />
                    <p>メッセージを送信するか、Excelファイルをアップロードしてください</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {messages.map((msg) => (
                      <div 
                        key={msg.id} 
                        className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div 
                          className={`max-w-[80%] rounded-lg p-3 ${
                            msg.sender === 'user' 
                              ? 'bg-blue-500 text-white' 
                              : 'bg-gray-100 text-gray-800'
                          }`}
                        >
                          <p className="whitespace-pre-wrap">{msg.content}</p>
                          <div 
                            className={`text-xs mt-1 ${
                              msg.sender === 'user' ? 'text-blue-100' : 'text-gray-500'
                            }`}
                          >
                            {msg.timestamp.toLocaleTimeString()}
                          </div>
                        </div>
                      </div>
                    ))}
                    <div ref={messagesEndRef} />
                  </div>
                )}
              </ScrollArea>
            </CardContent>
            
            <CardFooter>
              <form onSubmit={handleSubmitMessage} className="w-full flex gap-2">
                <Input
                  value={currentMessage}
                  onChange={(e) => setCurrentMessage(e.target.value)}
                  placeholder="メッセージを入力..."
                  className="flex-grow"
                  disabled={isLoading}
                />
                <Button type="submit" disabled={isLoading}>
                  <Send className="h-4 w-4 mr-2" />
                  送信
                </Button>
              </form>
            </CardFooter>
          </Card>
        </div>
        
        {/* Right Column - Form Inputs */}
        <div className="md:col-span-1">
          <Card className="h-full">
            <CardHeader>
              <CardTitle>確定事項入力フォーム</CardTitle>
              <CardDescription>
                以下の項目を入力してください
              </CardDescription>
            </CardHeader>
            
            <CardContent>
              <form onSubmit={handleFormSubmit} className="space-y-4">
                <FormItem>
                  <FormLabel>工事名 (セルI9)</FormLabel>
                  <FormControl>
                    <Input 
                      value={formData.projectName}
                      onChange={(e) => handleFormChange('projectName', e.target.value)}
                      placeholder="例: ○○ビル改修工事"
                    />
                  </FormControl>
                </FormItem>
                
                <FormItem>
                  <FormLabel>施工場所 (セルI11)</FormLabel>
                  <FormControl>
                    <Input 
                      value={formData.location}
                      onChange={(e) => handleFormChange('location', e.target.value)}
                      placeholder="例: 東京都渋谷区○○"
                    />
                  </FormControl>
                </FormItem>
                
                <FormItem>
                  <FormLabel>工期 (セルI13)</FormLabel>
                  <FormControl>
                    <Input 
                      value={formData.period}
                      onChange={(e) => handleFormChange('period', e.target.value)}
                      placeholder="例: 2025/4/1～2025/6/30"
                    />
                  </FormControl>
                </FormItem>
                
                <FormItem>
                  <FormLabel>作業者数 (セルQ15)</FormLabel>
                  <FormControl>
                    <Input 
                      value={formData.workerCount}
                      onChange={(e) => handleFormChange('workerCount', e.target.value)}
                      placeholder="例: 5"
                      type="number"
                    />
                  </FormControl>
                </FormItem>
                
                <Button type="submit" className="w-full mt-4" disabled={isLoading}>
                  確定情報を保存
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
      
      {/* Information Section */}
      <div className="mt-6">
        <Alert>
          <AlertDescription>
            <p className="text-sm">
              このシステムは複数のLLM（GPT-4 Turbo、Gemini 2.0、Claude 3、Mixtral）を連携させ、
              Excelファイルへの入力を自動化します。
            </p>
            <p className="text-sm mt-2 font-medium">ワークフロー:</p>
            <ol className="text-sm list-decimal pl-5 mt-1">
              <li>チャット → 追加質問 → チャット → 追加質問 → チャット → 情報生成 → VBAコード生成</li>
              <li>ファイルアップロード → VBA出力個所のセルの内容を理解 → ナレッジ化</li>
            </ol>
            <p className="text-sm mt-2">
              <span className="font-medium">確定事項入力フォーム</span>では、工事名（セルI9）、施工場所（セルI11）、
              工期（セルI13）、作業者数（セルQ15）の情報を入力してください。
            </p>
          </AlertDescription>
        </Alert>
      </div>
    </div>
  )
}

export default App
