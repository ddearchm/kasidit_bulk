import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from rapidfuzz import fuzz
import os
import re

st.set_page_config(page_title="Survey Column Builder", layout="wide")
st.title("📋 สร้าง Excel และ PDF สำหรับแบบสอบถาม")

uploaded_file = st.file_uploader("📂 อัปโหลดไฟล์ Excel สำหรับสร้างแบบสอบถาม", type=["xlsx"])

FUZZY_MATCH_THRESHOLD = 80

# === Utility ===
def clean_question(text):
    text = text.strip().lower()
    text = re.sub(r"\d+$", "", text)
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

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    valid_sheets = [sheet for sheet in xls.sheet_names if sheet.lower() != "lift"]
    sheets_data = {sheet: xls.parse(sheet) for sheet in valid_sheets}

    product_list_df = sheets_data.get("Product List")
    product_detail_df = sheets_data.get("Product & Details")

    selected_products = []
    selected_detail_questions = []

    # === เลือก Product ===
    if product_list_df is not None:
        st.header("📦 เลือกผลิตภัณฑ์ (Product List)")
        for i, row in product_list_df.iterrows():
            prod_th = str(row["standard_question_th"])
            if pd.notna(prod_th) and prod_th.strip():
                key = f"product_{i}"
                if st.checkbox(prod_th, key=key):
                    qty = st.number_input(
                        f"🔢 จำนวนสำหรับ {prod_th[:30]}",
                        min_value=1, max_value=20, value=1, step=1,
                        key=f"{key}_qty")
                    selected_products.append({"name": prod_th.strip(), "qty": qty})

    # === เลือกคำถามจาก Product & Details ===
    if product_detail_df is not None:
        st.header("📋 เลือกคำถามประกอบผลิตภัณฑ์ (Product & Details)")
        for i, row in product_detail_df.iterrows():
            detail_q = str(row["standard_question_th"])
            if pd.notna(detail_q) and detail_q.strip():
                key = f"detail_{i}"
                if st.checkbox(detail_q, key=key):
                    selected_detail_questions.append(detail_q.strip())

    # ปุ่มทำงาน
    if selected_products and selected_detail_questions:
        st.success(f"✅ เลือกสินค้า {len(selected_products)} รายการ และคำถาม {len(selected_detail_questions)} ข้อ")

        if st.button("📥 สร้างและดาวน์โหลดไฟล์ Excel + PDF"):
            columns = []
            qgroup_row = []
            question_row = []
            pdf_rows = []

            for product in selected_products:
                prod_name = product["name"]
                qty = product["qty"]
                for i in range(1, qty + 1):
                    for detail_q in selected_detail_questions:
                        combined_q = f"{prod_name}-{detail_q}#{i}"
                        columns.append(combined_q)
                        qgroup_row.append("Product Details")
                        question_row.append(combined_q)
                        pdf_rows.append(["Product Details", combined_q, ""])

            # Excel Header
            multi_header_df = pd.DataFrame([qgroup_row, question_row])
            empty_rows = pd.DataFrame([[""] * len(columns) for _ in range(5)])
            multi_header_df = pd.concat([multi_header_df, empty_rows], ignore_index=True)

            st.markdown("### 🧾 ตัวอย่างแบบสอบถาม (Excel)")
            st.dataframe(multi_header_df.head(5))

            # Export Excel
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                multi_header_df.to_excel(writer, sheet_name="Survey Template", index=False)
            st.download_button("⬇️ ดาวน์โหลด Excel", data=excel_buffer.getvalue(), file_name="survey_template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # Export PDF
            st.markdown("### 🔍 ตัวอย่างแบบสอบถาม (PDF)")
            preview_df = pd.DataFrame(pdf_rows[:5], columns=["Group", "Question", "Answer"])
            st.dataframe(preview_df)

            # Font for Thai
            font_path = os.path.join("font", "THSarabun.ttf")
            pdfmetrics.registerFont(TTFont("THSarabun", font_path))

            pdf_rows.sort(key=lambda x: x[1])
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
        st.info("⚠️ กรุณาเลือกผลิตภัณฑ์และคำถามก่อน")

