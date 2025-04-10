import pandas as pd
import openpyxl
from io import BytesIO
from typing import Dict, List, Any, Optional, Tuple
import base64

class ExcelProcessor:
    def __init__(self):
        self.safety_plan_ranges = {
            "D": [(34, 43), (54, 73), (81, 100), (108, 127)],
            "AS": [(34, 43), (54, 73), (81, 100), (108, 127)],
            "BK": [(34, 43), (54, 73), (81, 100), (108, 127)]
        }

        self.risk_assessment_rows = [
            34, 37, 40, 48, 51, 54, 57, 60, 63, 66, 69, 72, 75, 78, 81, 84, 87,
            96, 99, 102, 105, 108, 111, 114, 117, 120, 123, 126, 129, 132, 135,
            144, 147, 150, 153, 156, 159, 162, 165, 168, 171, 174, 177, 180, 183,
            192, 195, 198, 201, 204, 207, 210, 213, 216, 219, 222, 225, 228, 231,
            240, 243, 246, 249, 252, 255, 258, 261, 264, 267, 270, 273, 276, 279,
            288, 291, 294, 297, 300, 303, 306, 309, 312, 315, 318, 321, 324, 327,
            336, 339, 342, 345, 348, 351, 354, 357, 360, 363, 366, 369, 372, 375,
            384, 387, 390, 393, 396, 399, 402, 405, 408, 411, 414, 417, 420, 423,
            432, 435, 438, 441, 444, 447, 450, 453, 456, 459, 462, 465, 468, 471,
            480, 483, 486, 489, 492, 495, 498, 501, 504, 507, 510, 513, 516, 519,
            528, 531, 534, 537, 540, 543, 546, 549, 552, 555, 558, 561, 564, 567
        ]

        self.risk_assessment_columns = [
            "C", "O", "Y", "AI", "AS", "CC", "AV", "CF", "BE", "CL"
        ]

    async def process_excel_file(self, file_content: bytes) -> Dict[str, Any]:
        """
        Process the uploaded Excel file and extract data from specified ranges
        ワークフロー: ファイルアップロード→VBA出力個所のセルの内容を理解→ナレッジ化
        
        注意: ファイルのアップロードは、あくまでもナレッジの生成にしか使わない。
        VBAコード生成はチャットでの対話プロセスを通じて行う。
        """
        try:
            wb = openpyxl.load_workbook(BytesIO(file_content), data_only=True)

            safety_plan_data = {}
            if "安全施工計画書" in wb.sheetnames:
                sheet = wb["安全施工計画書"]
                safety_plan_data = self._extract_safety_plan_data(sheet)
                print(f"安全施工計画書シートからデータを抽出: D, AS, BK列（行34-43, 54-73, 81-100, 108-127）")

            risk_assessment_data = {}
            if "リスクアセスメント" in wb.sheetnames:
                sheet = wb["リスクアセスメント"]
                risk_assessment_data = self._extract_risk_assessment_data(sheet)
                print(f"リスクアセスメントシートからデータを抽出: C, O, Y, AI, AS, CC, AV, CF, BE, CL列")

            form_data = self._extract_form_data(wb)

            return {
                "safety_plan_sheet": safety_plan_data,
                "risk_assessment_sheet": risk_assessment_data,
                "form_data": form_data
            }

        except Exception as e:
            raise Exception(f"Excel処理エラー: {str(e)}")

    def _extract_safety_plan_data(self, sheet) -> Dict[str, List[str]]:
        """Extract data from the safety plan sheet"""
        result = {}

        for column, ranges in self.safety_plan_ranges.items():
            column_data = []

            for start_row, end_row in ranges:
                for row in range(start_row, end_row + 1):
                    cell_value = sheet[f"{column}{row}"].value
                    if cell_value is not None:
                        column_data.append(str(cell_value))

            result[column] = column_data

        return result

    def _extract_risk_assessment_data(self, sheet) -> Dict[str, List[str]]:
        """Extract data from the risk assessment sheet"""
        result = {}

        for column in self.risk_assessment_columns:
            column_data = []

            for row in self.risk_assessment_rows:
                cell_value = sheet[f"{column}{row}"].value
                if cell_value is not None:
                    column_data.append(str(cell_value))

            result[column] = column_data

        return result

    def _extract_form_data(self, workbook) -> Dict[str, Any]:
        """Extract the form data (confirmed information) from the Excel file"""
        form_data: Dict[str, Any] = {}

        for sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]

            project_name = sheet["I9"].value
            location = sheet["I11"].value
            period = sheet["I13"].value
            workers = sheet["Q15"].value

            if any([project_name, location, period, workers]):
                if project_name is not None:
                    form_data["project_name"] = str(project_name)
                if location is not None:
                    form_data["location"] = str(location)
                if period is not None:
                    form_data["period"] = str(period)
                if workers is not None and str(workers).isdigit():
                    form_data["workers"] = int(workers)
                break

        return form_data

    def generate_vba_template(self, form_data: Dict[str, Any], excel_data: Dict[str, Any]) -> str:
        """Generate a VBA code template based on the extracted data"""
        vba_template = """
Sub 安全施工計画書入力()
    ' 準備作業
    Application.ScreenUpdating = False
    Application.DisplayAlerts = False

    ' 本作業
    ' 確定事項の入力
    Worksheets("安全施工計画書").Range("I9").Value = "{project_name}"  ' 工事名
    Worksheets("安全施工計画書").Range("I11").Value = "{location}"     ' 施工場所
    Worksheets("安全施工計画書").Range("I13").Value = "{period}"       ' 工期
    Worksheets("安全施工計画書").Range("Q15").Value = {workers}        ' 作業者数

    ' 安全施工計画書シートの入力
    {safety_plan_code}

    ' リスクアセスメントシートの入力
    {risk_assessment_code}

    ' 後始末作業
    Application.ScreenUpdating = True
    Application.DisplayAlerts = True
    MsgBox "入力が完了しました。", vbInformation
End Sub
"""

        safety_plan_code = self._generate_safety_plan_vba(excel_data.get("safety_plan_sheet", {}))

        risk_assessment_code = self._generate_risk_assessment_vba(excel_data.get("risk_assessment_sheet", {}))

        vba_code = vba_template.format(
            project_name=form_data.get("project_name", ""),
            location=form_data.get("location", ""),
            period=form_data.get("period", ""),
            workers=form_data.get("workers", 0),
            safety_plan_code=safety_plan_code,
            risk_assessment_code=risk_assessment_code
        )

        return vba_code

    def _generate_safety_plan_vba(self, safety_plan_data: Dict[str, List[str]]) -> str:
        """Generate VBA code for safety plan sheet"""
        vba_code = "    ' 安全施工計画書シートのデータ入力\n"

        for column, values in safety_plan_data.items():
            if not values:
                continue

            vba_code += f"    ' {column}列のデータ入力\n"

            row_ranges = self.safety_plan_ranges[column]
            current_row_idx = 0

            for start_row, end_row in row_ranges:
                range_values = []
                for row in range(start_row, end_row + 1):
                    if current_row_idx < len(values):
                        range_values.append(values[current_row_idx])
                        current_row_idx += 1
                    else:
                        break

                if range_values:
                    vba_code += f"    ' 行{start_row}-{end_row}のデータ\n"
                    for i, value in enumerate(range_values):
                        row = start_row + i
                        vba_code += f'    Worksheets("安全施工計画書").Range("{column}{row}").Value = "{value}"\n'

        return vba_code

    def _generate_risk_assessment_vba(self, risk_assessment_data: Dict[str, List[str]]) -> str:
        """Generate VBA code for risk assessment sheet"""
        vba_code = "    ' リスクアセスメントシートのデータ入力\n"

        for column, values in risk_assessment_data.items():
            if not values:
                continue

            vba_code += f"    ' {column}列のデータ入力\n"

            for i, value in enumerate(values):
                if i < len(self.risk_assessment_rows):
                    row = self.risk_assessment_rows[i]
                    vba_code += f'    Worksheets("リスクアセスメント").Range("{column}{row}").Value = "{value}"\n'

        return vba_code
