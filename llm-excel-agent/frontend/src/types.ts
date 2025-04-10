export interface Message {
  id?: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp?: Date;
}

export interface FormData {
  projectName: string;
  location: string;
  period: string;
  workerCount: string;
}

export interface ExcelData {
  safety_plan_sheet: Record<string, string[]>;
  risk_assessment_sheet: Record<string, string[]>;
}
