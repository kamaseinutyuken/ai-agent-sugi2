interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

const API_URL = 'http://localhost:8000';

export interface ChatResponse {
  message: Message;
  conversation: Message[];
  round: number;
}

export interface FormData {
  project_name: string;
  location: string;
  period: string;
  workers: number;
}

export interface ExcelData {
  safety_plan_sheet: Record<string, string[]>;
  risk_assessment_sheet: Record<string, string[]>;
}

export interface ApiError {
  detail: string;
}

/**
 * Send a chat message to the backend API
 */
export const sendChatMessage = async (messages: Message[], fileData?: any, formData?: FormData): Promise<ChatResponse> => {
  try {
    const response = await fetch(`${API_URL}/api/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        messages,
        file_data: fileData,
        form_data: formData,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json() as ApiError;
      throw new Error(errorData.detail || 'APIエラーが発生しました');
    }

    return await response.json() as ChatResponse;
  } catch (error) {
    console.error('Chat API error:', error);
    throw error;
  }
};

/**
 * Upload an Excel file to the backend API
 */
export const uploadExcelFile = async (file: File): Promise<{ message: string; data: ExcelData }> => {
  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_URL}/api/upload-excel`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const errorData = await response.json() as ApiError;
      throw new Error(errorData.detail || 'ファイルアップロードエラーが発生しました');
    }

    return await response.json();
  } catch (error) {
    console.error('File upload error:', error);
    throw error;
  }
};

/**
 * Submit form data to the backend API
 */
export const submitFormData = async (formData: FormData): Promise<{ message: string; data: FormData }> => {
  try {
    const response = await fetch(`${API_URL}/api/submit-form`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(formData),
    });

    if (!response.ok) {
      const errorData = await response.json() as ApiError;
      throw new Error(errorData.detail || 'フォームデータ送信エラーが発生しました');
    }

    return await response.json();
  } catch (error) {
    console.error('Form submission error:', error);
    throw error;
  }
};

/**
 * Generate VBA code based on conversation, Excel data, and form data
 */
export const generateVbaCode = async (): Promise<{ vba_code: string; excel_data: ExcelData; messages: Message[] }> => {
  try {
    const response = await fetch(`${API_URL}/api/generate-vba`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const errorData = await response.json() as ApiError;
      throw new Error(errorData.detail || 'VBAコード生成エラーが発生しました');
    }

    return await response.json();
  } catch (error) {
    console.error('VBA generation error:', error);
    throw error;
  }
};

/**
 * Reset the conversation and stored data
 */
export const resetConversation = async (): Promise<{ message: string }> => {
  try {
    const response = await fetch(`${API_URL}/api/reset`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      const errorData = await response.json() as ApiError;
      throw new Error(errorData.detail || 'リセットエラーが発生しました');
    }

    return await response.json();
  } catch (error) {
    console.error('Reset error:', error);
    throw error;
  }
};
