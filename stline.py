# 📦 IMPORT & CONFIG
import streamlit as st
import pandas as pd
import os, re
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from rapidfuzz import fuzz

st.set_page_config(page_title="Survey Column Builder", layout="wide")
st.title("📋 สร้าง Excel และ PDF จากแบบสอบถาม (Standard + Cross Product)")

# 📂 FILE UPLOAD
uploaded_file = st.file_uploader("📂 อัปโหลดไฟล์ Excel", type=["xlsx"])

# 🎯 SETTING
FUZZY_MATCH_THRESHOLD = 80

# 🔧 CLEAN & MATCH UTILITIES
def clean_question(text):
    text = text.strip().lower()
    text = re.sub(r"\d+$", "", text)  # ตัดเลขท้าย
    return text

def find_q_group(base_question, sheets_data):
    base = clean_question(base_question)
    best_score = 0
    best_group = "N/A"
    for df in sheets_data.values():
        if "standard_question_th" in df.columns and "q_group" in df.columns:
            df = df.copy()
            df["standard_clean"] = df["standard_question_th"].astype(str).apply(clean_question)
            for _, row in df.iterrows():
                ref_q = row["standard_clean"]
                score = max(fuzz.partial_ratio(base, ref_q), fuzz.token_sort_ratio(base, ref_q))
                if score > best_score and score >= FUZZY_MATCH_THRESHOLD:
                    best_score = score
                    best_group = str(row["q_group"])
    return best_group

# 🧠 MAIN LOGIC
if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    valid_sheets = [s for s in xls.sheet_names if s.lower() not in ["lift"]]
    sheets_data = {sheet: xls.parse(sheet) for sheet in valid_sheets}

    is_cross = "Product List" in sheets_data and "Product & Details" in sheets_data

    # 🧠 STATE INITIALIZATION
    if "selected_questions" not in st.session_state:
        st.session_state.selected_questions = []
    if "selected_details" not in st.session_state:
        st.session_state.selected_details = []

    selected_questions = st.session_state.selected_questions
    selected_details = st.session_state.selected_details

    # 🟦 CROSS MODE
    selected_products = []
    if is_cross:
        st.subheader("📦 เลือกผลิตภัณฑ์ (จาก Product List)")
        for i, row in sheets_data["Product List"].iterrows():
            q = str(row["standard_question_th"])
            if pd.notna(q) and q.strip():
                if st.checkbox(q, key=f"prod_{i}"):
                    qty = st.number_input(f"🔢 จำนวน: {q}", min_value=1, max_value=20, value=1, step=1, key=f"prod_qty_{i}")
                    selected_products.append({"name": q.strip(), "qty": qty})

        st.subheader("📋 คำถามจาก Product & Details")
        for i, row in sheets_data["Product & Details"].iterrows():
            q = str(row["standard_question_th"])
            if pd.notna(q) and q.strip():
                if st.checkbox(q, key=f"detail_{i}"):
                    selected_details.append(q.strip())

        st.markdown("### ➕ เพิ่มคำถามประกอบสินค้า (Custom Product Details)")
        custom_detail = st.text_input("กรอกคำถามสำหรับสินค้า", key="custom_detail_input")
        if st.button("➕ เพิ่มใน Product Details"):
            if custom_detail.strip():
                selected_details.append(custom_detail.strip())
                st.success(f"เพิ่มคำถาม: {custom_detail.strip()}")
            else:
                st.warning("ต้องกรอกคำถามก่อน")

    # 🟨 STANDARD MODE
    st.subheader("📌 คำถามมาตรฐาน (Standard Questions)")
    for sheet_name, df in sheets_data.items():
        if sheet_name in ["Product List", "Product & Details"]: continue
        if "standard_question_th" not in df.columns: continue

        st.markdown(f"**📑 Sheet: {sheet_name}**")
        for i, row in df.iterrows():
            q = str(row["standard_question_th"])
            if pd.notna(q) and q.strip():
                if st.checkbox(q, key=f"{sheet_name}_{i}"):
                    qty = st.number_input(f"🔢 จำนวน: {q[:30]}", min_value=1, max_value=20, value=1, step=1, key=f"{sheet_name}_{i}_qty")
                    selected_questions.append({"Question": q.strip(), "Quantity": qty})

    st.markdown("### ✍️ เพิ่มคำถามเอง (Custom Questions)")
    custom_question = st.text_input("กรอกคำถามใหม่ที่ต้องการเพิ่ม", "")
    custom_qty = st.number_input("จำนวนคอลัมน์", min_value=1, max_value=20, value=1, step=1, key="custom_qty")

    if st.button("➕ เพิ่มคำถามเข้า list"):
        if custom_question.strip():
            selected_questions.append({"Question": custom_question.strip(), "Quantity": custom_qty})
            st.success(f"เพิ่มคำถาม: {custom_question.strip()}")
        else:
            st.warning("กรุณากรอกคำถามก่อน")

    # ✅ EXPORT
    if st.button("📥 สร้างและดาวน์โหลด Excel + PDF"):
        columns, qgroup_row, question_row, pdf_rows = [], [], [], []

        for q in selected_questions:
            base_q = q["Question"]
            group = find_q_group(base_q, sheets_data)
            for i in range(1, q["Quantity"] + 1):
                label = f"{base_q}{i if q['Quantity'] > 1 else ''}"
                columns.append(label)
                qgroup_row.append(group)
                question_row.append(label)
                pdf_rows.append([group, label, ""])

        if is_cross and selected_products and selected_details:
            for product in selected_products:
                name, qty = product["name"], product["qty"]
                for i in range(1, qty + 1):
                    for detail_q in selected_details:
                        label = f"{name}-{detail_q}#{i}"
                        columns.append(label)
                        qgroup_row.append("Product Details")
                        question_row.append(label)
                        pdf_rows.append(["Product Details", label, ""])

        header_df = pd.DataFrame([qgroup_row, question_row])
        empty = pd.DataFrame([[""] * len(columns) for _ in range(5)])
        final_df = pd.concat([header_df, empty], ignore_index=True)

        st.markdown("### 🧾 ตัวอย่าง (Excel)")
        st.dataframe(final_df.head(5))

        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            final_df.to_excel(writer, sheet_name="Survey Template", index=False)
        st.download_button("⬇️ ดาวน์โหลด Excel", data=excel_buffer.getvalue(), file_name="survey_template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.markdown("### 🔍 ตัวอย่าง (PDF)")
        st.dataframe(pd.DataFrame(pdf_rows[:5], columns=["Group", "Question", "Answer"]))

        font_path = os.path.join("font", "THSarabun.ttf")
        pdfmetrics.registerFont(TTFont("THSarabun", font_path))

        pdf_rows.sort(key=lambda x: x[0])
        table_data = [["Group", "Question", "Answer"]] + pdf_rows
        row_heights = [25] + [60] * len(pdf_rows)

        pdf_buffer = BytesIO()
        doc = SimpleDocTemplate(pdf_buffer, pagesize=landscape(A4))
        table = Table(table_data, colWidths=[120, 280, 320], rowHeights=row_heights, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTNAME", (0, 0), (-1, -1), "THSarabun"),
            ("FONTSIZE", (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ]))
        doc.build([table])
        st.download_button("⬇️ ดาวน์โหลด PDF", data=pdf_buffer.getvalue(), file_name="survey_questions_structured.pdf", mime="application/pdf")

else:
    st.info("📎 กรุณาอัปโหลดไฟล์ Excel เพื่อเริ่ม")
