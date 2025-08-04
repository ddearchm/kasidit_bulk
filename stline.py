import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors

st.set_page_config(page_title="Survey Column Builder", layout="wide")
st.title("📋 สร้าง Excel และ PDF จากแบบสอบถาม (พร้อมจำนวนและกลุ่ม)")

uploaded_file = st.file_uploader("📂 อัปโหลดไฟล์ Excel", type=["xlsx"])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    valid_sheets = [sheet for sheet in xls.sheet_names if sheet.lower() != "lift"]
    sheets_data = {sheet: xls.parse(sheet) for sheet in valid_sheets}

    selected_questions = []

    for sheet_name, df in sheets_data.items():
        if "standard_question_th" not in df.columns:
            continue

        st.markdown(f"### 🗂️ {sheet_name}")
        for i, row in df.iterrows():
            question = str(row["standard_question_th"])
            if pd.notna(question) and question.strip():
                key = f"{sheet_name}_{i}"
                if st.checkbox(question, key=key):
                    qty = st.number_input(
                        f"🔢 จำนวนคอลัมน์สำหรับ: {question[:40]}...",
                        min_value=1,
                        max_value=20,
                        value=1,
                        step=1,
                        key=f"{key}_qty"
                    )
                    selected_questions.append({
                        "Question": question,
                        "Quantity": qty
                    })

    if selected_questions:
        st.success(f"✅ เลือกทั้งหมด {len(selected_questions)} คำถาม")

        if st.button("📥 สร้างและดาวน์โหลดไฟล์ Excel + PDF"):
            columns = []
            pdf_rows = []

            for q in selected_questions:
                base = q["Question"].strip()

                # ===== สร้างชื่อคอลัมน์ Excel =====
                for i in range(1, q["Quantity"] + 1):
                    columns.append(f"{base}{i if q['Quantity'] > 1 else ''}")

                              
                # ===== หา q_group แค่ครั้งเดียวก่อนลูปจำนวน =====

                q_group = None
                base_question = q["Question"].strip()

                for sheet_df in sheets_data.values():
                    if "standard_question_th" in sheet_df.columns and "q_group" in sheet_df.columns:
                        match_row = sheet_df[sheet_df["standard_question_th"] == base_question]
                        if not match_row.empty:
                         q_group = str(match_row.iloc[0]["q_group"])
                         break

                if q_group is None:
                    q_group = "N/A"
                    # ===== แล้วค่อยลูปตามจำนวน =====
                for i in range(1, q["Quantity"] + 1):
                    numbered_q = f"{base_question}{i if q['Quantity'] > 1 else ''}"
                    pdf_rows.append([q_group, numbered_q, ""])

            # ===== สร้าง Excel =====
            df_out = pd.DataFrame(columns=columns)
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                df_out.to_excel(writer, sheet_name="Survey Template", index=False)

            st.download_button(
                label="⬇️ ดาวน์โหลด Excel",
                data=excel_buffer.getvalue(),
                file_name="survey_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # ===== สร้าง PDF =====
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            import os

            # กำหนด path ไปยังฟอนต์
            font_path = os.path.join("font", "THSarabun.ttf")

            # ลงทะเบียนฟอนต์ใหม่
            pdfmetrics.registerFont(TTFont("THSarabun", font_path))

            pdf_rows.sort(key=lambda x: x[0])  # sort by q_group
            table_data = [["group", "standard_question_th", "Answer"]] + pdf_rows

            pdf_buffer = BytesIO()
            doc = SimpleDocTemplate(pdf_buffer, pagesize=landscape(A4))
            table = Table(table_data, colWidths=[160, 400, 160])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, -1), "THSarabun"),
                ("FONTSIZE", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ]))
            doc.build([table])

            st.download_button(
                label="⬇️ ดาวน์โหลด PDF",
                data=pdf_buffer.getvalue(),
                file_name="survey_questions_structured.pdf",
                mime="application/pdf"
            )
    else:
        st.info("⚠️ กรุณาเลือกคำถามก่อนสร้างไฟล์")


