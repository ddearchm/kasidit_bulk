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
st.title("📋 สร้าง Excel และ PDF แบบสอบถาม")

# 🎯 SETUP SESSION STATE
if "custom_questions" not in st.session_state:
    st.session_state.custom_questions = []
if "custom_product_details" not in st.session_state:
    st.session_state.custom_product_details = []

# 📂 FILE UPLOAD
uploaded_file = st.file_uploader("📂 อัปโหลดไฟล์ Excel สำหรับเลือกคำถาม", type=["xlsx"])

# 🌟 FUZZY MATCH
FUZZY_MATCH_THRESHOLD = 80

def clean_question(text):
    text = text.strip().lower()
    return re.sub(r"\d+$", "", text)

def find_q_group(base_question, sheets_data):
    base = clean_question(base_question)
    best_score, best_group = 0, "N/A"
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

# 🔐 ป้องกัน duplicate column names
seen_labels = set()
def generate_unique_label(base, i, qty):
    raw = f"{base}#{i}" if qty > 1 else base
    label = raw
    count = 2
    while label in seen_labels:
        label = f"{raw}#{count}"
        count += 1
    seen_labels.add(label)
    return label

# 🧪 MAIN
if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    valid_sheets = [s for s in xls.sheet_names if s.lower() != "lift"]
    sheets_data = {sheet: xls.parse(sheet) for sheet in valid_sheets}

    is_cross = "Product List" in sheets_data and "Product & Details" in sheets_data
    selected_products, selected_details = [], []

    if is_cross:
        st.subheader("📦 เลือกผลิตภัณฑ์ (Product List)")
        for i, row in sheets_data["Product List"].iterrows():
            q = str(row["standard_question_th"])
            if pd.notna(q) and q.strip():
                if st.checkbox(q, key=f"prod_{i}"):
                    qty = st.number_input(f"🔢 จำนวน: {q}", 1, 20, 1, 1, key=f"qty_{i}")
                    selected_products.append({"name": q.strip(), "qty": qty})

        st.subheader("📋 คำถามจาก Product & Details")
        for i, row in sheets_data["Product & Details"].iterrows():
            q = str(row["standard_question_th"])
            if pd.notna(q) and q.strip():
                if st.checkbox(q, key=f"detail_{i}"):
                    selected_details.append(q.strip())

        with st.expander("➕ เพิ่มคำถามสินค้า (Custom Product Details)"):
            custom_detail = st.text_input("กรอกคำถามสินค้า", key="custom_detail_input")
            if st.button("➕ เพิ่มคำถามประกอบสินค้า"):
                if custom_detail.strip():
                    st.session_state.custom_product_details.append(custom_detail.strip())
                    st.success(f"✅ เพิ่มคำถามสินค้า \"{custom_detail.strip()}\" แล้วเรียบร้อย")
                else:
                    st.warning("กรุณากรอกคำถาม")

    st.subheader("📌 คำถามมาตรฐาน")
    selected_questions = []
    for sheet_name, df in sheets_data.items():
        if sheet_name in ["Product List", "Product & Details"] or "standard_question_th" not in df.columns:
            continue
        st.markdown(f"**📑 Sheet: {sheet_name}**")
        for i, row in df.iterrows():
            q = str(row["standard_question_th"])
            if pd.notna(q) and q.strip():
                if st.checkbox(q, key=f"{sheet_name}_{i}"):
                    qty = st.number_input(f"🔢 จำนวน: {q[:30]}", 1, 20, 1, 1, key=f"{sheet_name}_{i}_qty")
                    selected_questions.append({"Question": q.strip(), "Quantity": qty})

    with st.expander("✍️ เพิ่มคำถามเอง (Custom Questions)"):
        custom_q = st.text_input("กรอกคำถาม", key="custom_question_input")
        custom_q_qty = st.number_input("จำนวนคอลัมน์", 1, 20, 1, 1, key="custom_question_qty")
        custom_q_group = st.selectbox(
            "เลือกกลุ่มคำถาม (q_group)",
            options=[
                "BUSINESS_TYPE",
                "Respondent Profile",
                "Customer & Market",
                "Business & Strategy",
                "Pain Points & Needs",
                "Product & Process",
                "Product & Details",
                "Special Topic",
                "อื่นๆ"
            ],
            index=1,
            key="custom_question_group"
        )
        if st.button("➕ เพิ่มคำถามมาตรฐาน"):
            if custom_q.strip():
                st.session_state.custom_questions.append({
                    "Question": custom_q.strip(),
                    "Quantity": custom_q_qty,
                    "Group": custom_q_group if custom_q_group != "อื่นๆ" else "N/A"
                })
                st.success(f"✅ เพิ่มคำถาม \"{custom_q.strip()}\" เข้า group \"{custom_q_group}\" แล้ว!")
            else:
                st.warning("กรุณากรอกคำถาม")

    # รวม custom เข้าไปด้วย
    for item in st.session_state.custom_questions:
        selected_questions.append({
            "Question": item["Question"],
            "Quantity": item["Quantity"],
            "Group": item.get("Group", "N/A")
        })
    selected_details += st.session_state.custom_product_details

    if st.button("📅 สร้างและดาวน์โหลด Excel + PDF"):
        columns, qgroup_row, question_row, pdf_rows = [], [], [], []
        seen_labels.clear()

        # ✅ Group questions
        grouped_questions_by_group = {}
        unmatched_questions = []

        for q in selected_questions:
            base_q = q["Question"]
            group = q.get("Group") or find_q_group(base_q, sheets_data)
            item = {"question": base_q, "qty": q["Quantity"], "group": group}
            if group == "N/A":
                unmatched_questions.append(item)
            else:
                grouped_questions_by_group.setdefault(group, []).append(item)

        # ✅ ลำดับ group ที่ต้องการ
        preferred_qgroup_order = [
            "BUSINESS_TYPE",
            "Respondent Profile",
            "Customer & Market",
            "Business & Strategy",
            "Pain Points & Needs",
            "Product & Process",
            "Product & Details",
            "Special Topic"
        ]

        already_handled = set()
        for group in preferred_qgroup_order:
            if group in grouped_questions_by_group:
                already_handled.add(group)
                for item in grouped_questions_by_group[group]:
                    base_q, qty = item["question"], item["qty"]
                    for i in range(1, qty + 1):
                        label = generate_unique_label(base_q, i, qty)
                        columns.append(label)
                        qgroup_row.append(group)
                        question_row.append(label)
                        pdf_rows.append([group, label, ""])

        for group in grouped_questions_by_group:
            if group not in already_handled and group != "N/A":
                for item in grouped_questions_by_group[group]:
                    base_q, qty = item["question"], item["qty"]
                    for i in range(1, qty + 1):
                        label = generate_unique_label(base_q, i, qty)
                        columns.append(label)
                        qgroup_row.append(group)
                        question_row.append(label)
                        pdf_rows.append([group, label, ""])

        for item in unmatched_questions:
            base_q, qty = item["question"], item["qty"]
            for i in range(1, qty + 1):
                label = generate_unique_label(base_q, i, qty)
                columns.append(label)
                qgroup_row.append("N/A")
                question_row.append(label)
                pdf_rows.append(["N/A", label, ""])

        if is_cross and selected_products and selected_details:
            for prod in selected_products:
                for i in range(1, prod["qty"] + 1):
                    for detail in selected_details:
                        label = generate_unique_label(f"{prod['name']}-{detail}", i, prod["qty"])
                        columns.append(label)
                        qgroup_row.append("Product & Details")
                        question_row.append(label)
                        pdf_rows.append(["Product & Details", label, ""])

        header_df = pd.DataFrame([qgroup_row, question_row])
        empty = pd.DataFrame([[""] * len(columns) for _ in range(5)])
        final_df = pd.concat([header_df, empty], ignore_index=True)

        st.markdown("### 📓 ตัวอย่าง (Excel)")
        st.dataframe(final_df.head(5))

        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            final_df.to_excel(writer, sheet_name="Survey Template", index=False)
        st.download_button("🔽️ ดาวน์โหลด Excel", data=excel_buffer.getvalue(), file_name="survey_template.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.markdown("### 🔍 ตัวอย่าง (PDF)")
        st.dataframe(pd.DataFrame(pdf_rows[:5], columns=["Group", "Question", "Answer"]))

        font_path = os.path.join("font", "THSarabun.ttf")
        pdfmetrics.registerFont(TTFont("THSarabun", font_path))
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

        # ✅ Preview Excel แนวตั้งใน Streamlit
        st.markdown("### 📋 ตัวอย่าง (Excel แนวตั้ง)")
        st.dataframe(df_vertical.head(10))
        st.download_button("🔽️ ดาวน์โหลด PDF", data=pdf_buffer.getvalue(), file_name="survey_questions_structured.pdf", mime="application/pdf")
        # ✅ Excel แนวตั้ง (แบบ PDF) + ลำดับ
        df_vertical = pd.DataFrame(pdf_rows, columns=["Group", "Question", "Answer"])
        df_vertical.index += 1  # ให้เริ่มจาก 1
        df_vertical.reset_index(inplace=True)
        df_vertical.rename(columns={"index": "No."}, inplace=True)

        excel_vertical_buffer = BytesIO()
        with pd.ExcelWriter(excel_vertical_buffer, engine="openpyxl") as writer:
            df_vertical.to_excel(writer, sheet_name="Survey Vertical", index=False)

        st.download_button(
            label="⬇️ ดาวน์โหลด Excel (แนวตั้ง + ลำดับ)",
            data=excel_vertical_buffer.getvalue(),
            file_name="survey_template_vertical.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


else:
    st.info("📌 กรุณาอัปโหลด Excel เพื่อเริ่ม")

