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
st.title("📋 สร้างแบบสอบถาม (Excel และ PDF)")

# 🎯 SETUP SESSION STATE
if "custom_questions" not in st.session_state:
    st.session_state.custom_questions = []
if "custom_product_details" not in st.session_state:
    st.session_state.custom_product_details = []

# 🌟 FUZZY MATCH
FUZZY_MATCH_THRESHOLD = 80

def clean_question(text):
    text = str(text).strip().lower()
    return re.sub(r"\d+$", "", text)

def find_q_group(base_question, sheets_data):
    """
    คง logic เดิมไว้: หา group จากคลังคำถามของ business type ที่เลือก (sheets_data)
    """
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

# 🧰 QUESTION BANK (ใส่คำถามจริงของคุณแทนที่ตัวอย่างด้านล่าง)
# โครงสร้าง: QUESTION_BANK[BUSINESS_TYPE][SHEET_NAME] = list ของ dict ที่มี standard_question_th, q_group
# sheet name ใช้ชื่อเดียวกับตอนอ่านจาก Excel เดิม เช่น "Respondent Profile", "Customer & Market", "Product List", "Product & Details"
QUESTION_BANK = {
    "Bulk transformer": {
        "Respondent Profile": [
            {"standard_question_th": "ชื่อ", "q_group": "Respondent Profile"},
            {"standard_question_th": "ชื่อธุรกิจ", "q_group": "Respondent Profile"},
            {"standard_question_th": "จังหวัด (ตามที่อยู่)", "q_group": "Respondent Profile"},
            {"standard_question_th": "เบอร์โทร", "q_group": "Respondent Profile"},
            {"standard_question_th": "เพศ", "q_group": "Respondent Profile"},
            {"standard_question_th": "อายุ", "q_group": "Respondent Profile"},                        
            {"standard_question_th": "ตำแหน่ง", "q_group": "Respondent Profile"},
            {"standard_question_th": "Persona", "q_group": "Respondent Profile"},

        ],
        "Customer & Market": [
            {"standard_question_th": "ประเภทงานก่อสร้างของลูกค้าหลัก", "q_group": "Customer & Market"},
            {"standard_question_th": "วิธีสื่อสารกับลูกค้าแบบออฟไลน์", "q_group": "Customer & Market"},
            {"standard_question_th": "วิธีสื่อสารกับลูกค้าแบบออนไลน์", "q_group": "Customer & Market"},
            {"standard_question_th": "ช่วงอายุของลูกค้า", "q_group": "Customer & Market"},
            {"standard_question_th": "วิธีดูแลลูกค้าประจำของร้าน", "q_group": "Customer & Market"},
            {"standard_question_th": "ระบบสะสมแต้มของตัวเอง", "q_group": "Customer & Market"},
            {"standard_question_th": "ของแจกที่ลูกค้าชอบ", "q_group": "Customer & Market"},
            {"standard_question_th": "ช่องทางการขายที่ยอดมากที่สุด", "q_group": "Customer & Market"},
            {"standard_question_th": "ช่องทางการซื้อของลูกค้าส่วนใหญ่", "q_group": "Customer & Market"},

        ],
        "Business & Strategy": [
            {"standard_question_th": "Dealer", "q_group": "Business & Strategy"},
            {"standard_question_th": "BP Model", "q_group": "Business & Strategy"},
            {"standard_question_th": "ความเป็นมาของธุรกิจ", "q_group": "Business & Strategy"},
            {"standard_question_th": "มีคนรับช่วงธุรกิจต่อหรือไม่", "q_group": "Business & Strategy"},
            {"standard_question_th": "ธุรกิจอื่นที่ทำควบคู่กัน", "q_group": "Business & Strategy"},
            {"standard_question_th": "ธุรกิจอื่นที่ทำควบคู่กัน (detail)", "q_group": "Business & Strategy"},
            {"standard_question_th": "แผนขยายธุรกิจอื่นๆ", "q_group": "Business & Strategy"},
            {"standard_question_th": "แผนขยายธุรกิจหลัก", "q_group": "Business & Strategy"},

        ],
        "Pain Points & Needs": [
            {"standard_question_th": "need ในขั้นตอนการทำงาน", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "pain ในขั้นตอนการทำงาน", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "แก้ไข pain ในขั้นตอนการทำงานอย่างไร", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "สิ่งที่อยากให้ SCG สนับสนุน/ช่วยเหลือ", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "สิ่งที่อยากให้ SCG สนับสนุน/ช่วยเหลือ (detail)", "q_group": "Pain Points & Needs"},
            
        ],
        "Product & Process": [
            {"standard_question_th": "ปูน SCG ที่ใช้ในกระบวนการผลิต", "q_group": "Product & Process"},
            {"standard_question_th": "ปัจจัยสำคัญในการเลือกซื้อปูน เสือ/SCG", "q_group": "Product & Process"},
            {"standard_question_th": "แบรนด์ขายดี", "q_group": "Product & Process"},
            {"standard_question_th": "สินค้าอื่นที่ผลิตขาย", "q_group": "Product & Process"},
            {"standard_question_th": "กลยุทธ์รักษาฐานลูกค้า และสู้กับคู่แข่ง", "q_group": "Product & Process"},
            {"standard_question_th": "ปัจจัยเสี่ยงต่อธุรกิจ", "q_group": "Product & Process"},
            {"standard_question_th": "ปัจจัยสำคัญของการผลิต", "q_group": "Product & Process"},
            {"standard_question_th": "ความสำคัญของคุณภาพปูนในกระบวนการผลิต", "q_group": "Product & Process"},
            {"standard_question_th": "คุณสมบัติปูนที่สำคัญ", "q_group": "Product & Process"},
            {"standard_question_th": "คุณสมบัติสำคัญในกระบวนการผลิตสินค้าคอนกรีตขายดี", "q_group": "Product & Process"},
            {"standard_question_th": "คุณสมบัติของสินค้าคอนกรีตขายดี", "q_group": "Product & Process"},
            {"standard_question_th": "วิธีการทำงานในส่วน Pre-Stressed", "q_group": "Product & Process"},
            {"standard_question_th": "วิธีการทำงานในส่วน RMC", "q_group": "Product & Process"},
            {"standard_question_th": "วิธีการทำงานในส่วน Non-Prestressed", "q_group": "Product & Process"},
            {"standard_question_th": "กระบวนการทำงานในโรงหล่อที่สำคัญ", "q_group": "Product & Process"},
            {"standard_question_th": "แหล่งวัตถุดิบ", "q_group": "Product & Process"},
            {"standard_question_th": "วิธีเช็คคุณภาพวัตถุดิบ", "q_group": "Product & Process"},
            {"standard_question_th": "การตรวจสอบคุณภาพสินค้า", "q_group": "Product & Process"},

        ],        
    },
    "Bag transformer": {
        "Respondent Profile": [
            {"standard_question_th": "ชื่อ", "q_group": "Respondent Profile"},
            {"standard_question_th": "ชื่อธุรกิจ", "q_group": "Respondent Profile"},
            {"standard_question_th": "จังหวัด (ตามที่อยู่)", "q_group": "Respondent Profile"},
            {"standard_question_th": "เบอร์โทร", "q_group": "Respondent Profile"},
            {"standard_question_th": "เพศ", "q_group": "Respondent Profile"},
            {"standard_question_th": "อายุ", "q_group": "Respondent Profile"},                        
            {"standard_question_th": "ตำแหน่ง", "q_group": "Respondent Profile"},
            {"standard_question_th": "Persona", "q_group": "Respondent Profile"},

        ],
        "Customer & Market": [
            {"standard_question_th": "ประเภทงานก่อสร้างของลูกค้าหลัก", "q_group": "Customer & Market"},
            {"standard_question_th": "วิธีสื่อสารกับลูกค้าแบบออฟไลน์", "q_group": "Customer & Market"},
            {"standard_question_th": "วิธีสื่อสารกับลูกค้าแบบออนไลน์", "q_group": "Customer & Market"},
        ],
        "Business & Strategy": [
            {"standard_question_th": "Dealer", "q_group": "Business & Strategy"},
            {"standard_question_th": "BP Model", "q_group": "Business & Strategy"},
            {"standard_question_th": "ความเป็นมาของธุรกิจ", "q_group": "Business & Strategy"},
            {"standard_question_th": "มีคนรับช่วงธุรกิจต่อหรือไม่", "q_group": "Business & Strategy"},
            {"standard_question_th": "ธุรกิจอื่นที่ทำควบคู่กัน", "q_group": "Business & Strategy"},
            {"standard_question_th": "แผนขยายธุรกิจอื่นๆ", "q_group": "Business & Strategy"},
            {"standard_question_th": "แผนขยายธุรกิจหลัก", "q_group": "Business & Strategy"},
        ],
        "Pain Points & Needs": [
            {"standard_question_th": "need ในขั้นตอนการทำงาน", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "pain ในขั้นตอนการทำงาน", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "แก้ไข pain ในขั้นตอนการทำงานอย่างไร", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "สิ่งที่อยากให้ SCG สนับสนุน/ช่วยเหลือ", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "สิ่งที่อยากให้ SCG สนับสนุน/ช่วยเหลือ (detail)", "q_group": "Pain Points & Needs"},
            
        ],
        "Product & Process": [
            {"standard_question_th": "ปูน SCG ที่ใช้ในกระบวนการผลิต", "q_group": "Product & Process"},
            {"standard_question_th": "ปัจจัยสำคัญในการเลือกซื้อปูน เสือ/SCG", "q_group": "Product & Process"},
            {"standard_question_th": "แบรนด์ขายดี", "q_group": "Product & Process"},
            {"standard_question_th": "สินค้าอื่นที่ผลิตขาย", "q_group": "Product & Process"},
            {"standard_question_th": "กลยุทธ์รักษาฐานลูกค้า และสู้กับคู่แข่ง", "q_group": "Product & Process"},
            {"standard_question_th": "ปัจจัยเสี่ยงต่อธุรกิจ", "q_group": "Product & Process"},
            {"standard_question_th": "ปัจจัยสำคัญของการผลิต", "q_group": "Product & Process"},
            {"standard_question_th": "ความสำคัญของคุณภาพปูนในกระบวนการผลิต", "q_group": "Product & Process"},
            {"standard_question_th": "คุณสมบัติปูนที่สำคัญ", "q_group": "Product & Process"},
            {"standard_question_th": "คุณสมบัติสำคัญในกระบวนการผลิตสินค้าคอนกรีตขายดี", "q_group": "Product & Process"},
            {"standard_question_th": "คุณสมบัติของสินค้าคอนกรีตขายดี", "q_group": "Product & Process"},
            {"standard_question_th": "วิธีการทำงานในส่วน Pre-Stressed", "q_group": "Product & Process"},
            {"standard_question_th": "วิธีการทำงานในส่วน RMC", "q_group": "Product & Process"},
            {"standard_question_th": "วิธีการทำงานในส่วน Non Pre-Stressed", "q_group": "Product & Process"},
            {"standard_question_th": "กระบวนการทำงานในโรงหล่อที่สำคัญ", "q_group": "Product & Process"},
            {"standard_question_th": "แหล่งวัตถุดิบ", "q_group": "Product & Process"},
            {"standard_question_th": "วิธีเช็คคุณภาพวัตถุดิบ", "q_group": "Product & Process"},
            {"standard_question_th": "การตรวจสอบคุณภาพสินค้า", "q_group": "Product & Process"},
        ],        
    },
    "Subdealer & Bag transformer": {
        "Respondent Profile": [
            {"standard_question_th": "บริษัทรับเหมาก่อสร้าง", "q_group": "Respondent Profile"},
            {"standard_question_th": "ชื่อ", "q_group": "Respondent Profile"},
            {"standard_question_th": "เบอร์โทร", "q_group": "Respondent Profile"},
            {"standard_question_th": "เพศ", "q_group": "Respondent Profile"},
            {"standard_question_th": "อายุ", "q_group": "Respondent Profile"},
            {"standard_question_th": "ตำแหน่ง", "q_group": "Respondent Profile"},
            {"standard_question_th": "จังหวัด (ตามที่อยู่)", "q_group": "Respondent Profile"},
        ],
        "Customer & Market": [
            {"standard_question_th": "ประเภทงานก่อสร้างของลูกค้าหลัก", "q_group": "Customer & Market"},
            {"standard_question_th": "ยอดซื้อเฉลี่ยของลูกค้า (บาท/บิล)", "q_group": "Customer & Market"},
            {"standard_question_th": "สัดส่วนลูกค้าโทรสั่ง", "q_group": "Customer & Market"},
            {"standard_question_th": "สัดส่วนลูกค้าไลน์สั่ง", "q_group": "Customer & Market"},
            {"standard_question_th": "สัดส่วนลูกค้าสั่งที่ร้าน", "q_group": "Customer & Market"},
            {"standard_question_th": "กลุ่มลูกค้าประจำของร้าน", "q_group": "Customer & Market"},
            {"standard_question_th": "วิธีดูแลลูกค้าประจำของร้าน", "q_group": "Customer & Market"},
        ],
        "Business & Strategy": [
            {"standard_question_th": "Dealer", "q_group": "Business & Strategy"},
            {"standard_question_th": "สถานการณ์ตลาด", "q_group": "Business & Strategy"},
            {"standard_question_th": "สถานการณ์แข่งขันด้านราคา", "q_group": "Business & Strategy"},
            {"standard_question_th": "Price Gap ที่เหมาะสม", "q_group": "Business & Strategy"},
            {"standard_question_th": "สรุปช่องทางที่ลูกค้าสั่งซื้อสินค้า", "q_group": "Business & Strategy"},
            {"standard_question_th": "รูปแบบการชำระเงิน", "q_group": "Business & Strategy"},
            {"standard_question_th": "แฟนพันธ์แท้ปูนเสือ/SCG", "q_group": "Business & Strategy"},
            {"standard_question_th": "Capacity หน้าร้าน (ตัน)", "q_group": "Business & Strategy"},
            {"standard_question_th": "Capacity รวมทั้งร้าน (ตัน)", "q_group": "Business & Strategy"},
            {"standard_question_th": "มีคนรับช่วงธุรกิจต่อหรือไม่", "q_group": "Business & Strategy"},
            {"standard_question_th": "ธุรกิจอื่นที่ทำควบคู่กัน", "q_group": "Business & Strategy"},
            {"standard_question_th": "แผนขยายธุรกิจ", "q_group": "Business & Strategy"},
            {"standard_question_th": "ทำธุรกิจโรงหล่อควบคู่ร้านวัสดุก่อสร้าง", "q_group": "Business & Strategy"},
            {"standard_question_th": "ปูน SCG ที่ใช้ในกระบวนการผลิต", "q_group": "Business & Strategy"},
            {"standard_question_th": "สินค้าหลักที่ผลิต", "q_group": "Business & Strategy"},
            {"standard_question_th": "สินค้าขายดี", "q_group": "Business & Strategy"},
            {"standard_question_th": "กลุ่มลูกค้าหลักของธุรกิจโรงหล่อ", "q_group": "Business & Strategy"},
            {"standard_question_th": "แหล่งวัตถุดิบและวิธีเช็คคุณภาพ", "q_group": "Business & Strategy"},            
        ],
        "Pain Points & Needs": [
            {"standard_question_th": "need ในขั้นตอนการทำงาน", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "pain ในขั้นตอนการทำงาน", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "แก้ไข pain ในขั้นตอนการทำงานอย่างไร", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "สิ่งที่อยากให้ SCG สนับสนุน/ช่วยเหลือ", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "สิ่งที่อยากให้ SCG สนับสนุน/ช่วยเหลือ (detail)", "q_group": "Pain Points & Needs"},
            
        ],
        "Product & Process": [
            {"standard_question_th": "ระบบขายหน้าร้าน", "q_group": "Product & Process"},
            {"standard_question_th": "แบรนด์ขายดี", "q_group": "Product & Process"},
            {"standard_question_th": "ปัจจัยสำคัญในการเลือกซื้อปูน เสือ/SCG", "q_group": "Product & Process"},
            {"standard_question_th": "กลยุทธ์รักษาฐานลูกค้า และสู้กับคู่แข่ง", "q_group": "Product & Process"},
            {"standard_question_th": "ปัจจัยสำคัญของการผลิต", "q_group": "Product & Process"},            
        ],   
        "Product List": [
            {"standard_question_th": "ก่อฉาบเท-Grey", "q_group": "Product & Details"},
            {"standard_question_th": "ก่อ-Grey", "q_group": "Product & Details"},
            {"standard_question_th": "ก่อ-Mortar", "q_group": "Product & Details"},
            {"standard_question_th": "ก่อ-Mortar-LW", "q_group": "Product & Details"},
            {"standard_question_th": "ฉาบ-Grey", "q_group": "Product & Details"},
            {"standard_question_th": "ฉาบ-Mortar", "q_group": "Product & Details"},
            {"standard_question_th": "ฉาบ-Mortar-LW", "q_group": "Product & Details"},
            {"standard_question_th": "ฉาบ-Grey-จับเซี๊ยม", "q_group": "Product & Details"},
            {"standard_question_th": "ฉาบ-Mortar-จับเซี๊ยม", "q_group": "Product & Details"},
            {"standard_question_th": "ฉาบบาง-Mortar-สกิมโค้ท", "q_group": "Product & Details"},
            {"standard_question_th": "เทโครงสร้าง-Grey", "q_group": "Product & Details"},
            {"standard_question_th": "เทโครงสร้าง-Mortar", "q_group": "Product & Details"},
            {"standard_question_th": "เทโครงสร้าง-RMC", "q_group": "Product & Details"},
            {"standard_question_th": "เทเสาเอ็น-Grey", "q_group": "Product & Details"},
            {"standard_question_th": "เทเสาเอ็น-Mortar", "q_group": "Product & Details"},
            {"standard_question_th": "เทเสาเอ็น-RMC", "q_group": "Product & Details"},
            {"standard_question_th": "เทปรับพื้น-Grey", "q_group": "Product & Details"},
            {"standard_question_th": "เทปรับพื้น-Mortar", "q_group": "Product & Details"},
            {"standard_question_th": "เทปรับพื้น-RMC", "q_group": "Product & Details"},
            {"standard_question_th": "ปูกระเบื้อง-Mortar-TA", "q_group": "Product & Details"},
            {"standard_question_th": "ปูกระเบื้อง-Mortar-TG", "q_group": "Product & Details"},
            {"standard_question_th": "ผนัง-อิฐมอญ", "q_group": "Product & Details"},
            {"standard_question_th": "ผนัง-อิฐบล็อก", "q_group": "Product & Details"},
            {"standard_question_th": "ผนัง-อิฐมวลเบา", "q_group": "Product & Details"},
            {"standard_question_th": "ผนัง-CLC", "q_group": "Product & Details"},
            {"standard_question_th": "ผนัง-Wall system", "q_group": "Product & Details"},
            {"standard_question_th": "สี-รองพื้น", "q_group": "Product & Details"},
            {"standard_question_th": "สี-สีจริง", "q_group": "Product & Details"},
            {"standard_question_th": "อื่นๆ-Water proof", "q_group": "Product & Details"},
            {"standard_question_th": "อื่นๆ-Non shrink", "q_group": "Product & Details"},
            {"standard_question_th": "อื่นๆ-White", "q_group": "Product & Details"},
        ],
        "Product & Details": [
            {"standard_question_th": "ยี่ห้อ", "q_group": "Product & Details"},
            {"standard_question_th": "ราคาหน้าร้าน", "q_group": "Product & Details"},
            {"standard_question_th": "ราคาทุน", "q_group": "Product & Details"},
            {"standard_question_th": "สต็อก", "q_group": "Product & Details"},
        ],
        "Special Topic": [
            {"standard_question_th": "Giant Banner", "q_group": "Special Topic"},
            {"standard_question_th": "รูปแบบบิลที่ใช้ในแต้มปูน", "q_group": "Special Topic"},
            {"standard_question_th": "เหตุผลที่เป็นแฟนพันธุ์แท้ปูนเสือ/SCG", "q_group": "Special Topic"},
        ],
    },
    "Contractor": {
         "Respondent Profile": [
            {"standard_question_th": "ชื่อ", "q_group": "Respondent Profile"},
            {"standard_question_th": "ชื่อเล่น", "q_group": "Respondent Profile"},
            {"standard_question_th": "เพศ", "q_group": "Respondent Profile"},
            {"standard_question_th": "อายุ", "q_group": "Respondent Profile"},
            {"standard_question_th": "ตำแหน่ง", "q_group": "Respondent Profile"},
            {"standard_question_th": "จำนวนทีมงาน", "q_group": "Respondent Profile"},
            {"standard_question_th": "ประสบการณ์ทำงาน", "q_group": "Respondent Profile"},
            {"standard_question_th": "กิจวัตรประจำวันและงานอดิเรก", "q_group": "Respondent Profile"},
            {"standard_question_th": "เป้าหมายชีวิต", "q_group": "Respondent Profile"},
            {"standard_question_th": "สิ่งที่อยากพัฒนาเพื่อให้ธุรกิจดีขึ้น", "q_group": "Respondent Profile"},
            {"standard_question_th": "ประวัติการศึกษาและจุดเริ่มต้นการทำงาน", "q_group": "Respondent Profile"},
            {"standard_question_th": "ดูทีวีหรือไม่", "q_group": "Respondent Profile"},
            {"standard_question_th": "ดูยูทูปหรือไม่", "q_group": "Respondent Profile"},
            {"standard_question_th": "เล่นเฟซบุ๊คหรือไม่", "q_group": "Respondent Profile"},
            {"standard_question_th": "เล่นติ๊กต๊อกหรือไม่", "q_group": "Respondent Profile"},
            {"standard_question_th": "เล่นไอจีหรือไม่", "q_group": "Respondent Profile"},
            {"standard_question_th": "สื่อช่องทางอื่นๆที่เล่น หรือสนใจเลยหันมาเล่น", "q_group": "Respondent Profile"},
            {"standard_question_th": "ดูทีวี (detail)", "q_group": "Respondent Profile"},
            {"standard_question_th": "ดูยูทูป (detail)", "q_group": "Respondent Profile"},
            {"standard_question_th": "เล่นเฟซบุ๊ค (detail)", "q_group": "Respondent Profile"},
            {"standard_question_th": "เล่นติ๊กต๊อก (detail)", "q_group": "Respondent Profile"},
            {"standard_question_th": "เล่นไอจี (detail)", "q_group": "Respondent Profile"},
            {"standard_question_th": "lifestyle-กาแฟ/คาเฟ่", "q_group": "Respondent Profile"},
            {"standard_question_th": "lifestyle-ทานอาหารนอกบ้าน", "q_group": "Respondent Profile"},
            {"standard_question_th": "lifestyle-ซื้อของบิ๊กซี/โลตัส", "q_group": "Respondent Profile"},
            {"standard_question_th": "lifestyle-ซื้อของเซ็นทรัล", "q_group": "Respondent Profile"},
            {"standard_question_th": "lifestyle-ท่องเที่ยว", "q_group": "Respondent Profile"},
            {"standard_question_th": "lifestyle-ออกกำลังกาย", "q_group": "Respondent Profile"},
            {"standard_question_th": "lifestyle-กีฬา", "q_group": "Respondent Profile"},
            {"standard_question_th": "lifestyle-อื่นๆ", "q_group": "Respondent Profile"},
        ],
        "Customer & Market": [
            {"standard_question_th": "ใครเป็นผู้ตัดสินใจซื้อวัสดุก่อสร้าง", "q_group": "Customer & Market"},
            {"standard_question_th": "ประเภทงานก่อสร้างที่ให้บริการเป็นหลัก", "q_group": "Customer & Market"},
            {"standard_question_th": "ปัจจัยสำคัญในการเลือกซื้อปูน", "q_group": "Customer & Market"},
            {"standard_question_th": "ปัจจัยสำคัญในการเลือกซื้อปูน เสือ/SCG", "q_group": "Customer & Market"},
            {"standard_question_th": "แบรนด์ใดที่คุณมองว่าใกล้เคียงกับปูน เสือ/SCG", "q_group": "Customer & Market"},
            {"standard_question_th": "ร้านค้า-มีอิทธิพลต่อการซื้อปูน", "q_group": "Customer & Market"},
            {"standard_question_th": "สื่อโทรทัศน์-มีอิทธิพลต่อการซื้อปูน", "q_group": "Customer & Market"},
            {"standard_question_th": "สื่อวิทยุ-มีอิทธิพลต่อการซื้อปูน", "q_group": "Customer & Market"},
            {"standard_question_th": "การบอกต่อ-มีอิทธิพลต่อการซื้อปูน", "q_group": "Customer & Market"},
            {"standard_question_th": "สื่อโซเชียล-มีอิทธิพลต่อการซื้อปูน", "q_group": "Customer & Market"},
            {"standard_question_th": "งานสัมมนา-มีอิทธิพลต่อการซื้อปูน", "q_group": "Customer & Market"},
            {"standard_question_th": "งานเอ็กซ์โป-มีอิทธิพลต่อการซื้อปูน", "q_group": "Customer & Market"},
            {"standard_question_th": "ช่องทางอื่นๆ-มีอิทธิพลต่อการซื้อปูน", "q_group": "Customer & Market"},
            {"standard_question_th": "วิธีการสั่งซื้อปูนและวัสดุก่อสร้าง", "q_group": "Customer & Market"},
            {"standard_question_th": "%สั่งซื้อปูนและวัสดุก่อสร้างทางโทรศัพท์", "q_group": "Customer & Market"},
            {"standard_question_th": "%สั่งซื้อปูนและวัสดุก่อสร้างทางไลน์", "q_group": "Customer & Market"},
            {"standard_question_th": "%สั่งซื้อปูนและวัสดุก่อสร้างที่หน้าร้าน", "q_group": "Customer & Market"},
            {"standard_question_th": "วิธีการจ่ายเงิน (เงินสด, เครดิต, เงินสดและเครดิต)", "q_group": "Customer & Market"},
            {"standard_question_th": "ยอดซื้อปูน และวัสดุก่อสร้างโดยเฉลี่ย (บาทต่อบิล)", "q_group": "Customer & Market"},
            {"standard_question_th": "ซื้อปูนและวัสดุก่อสร้างจาก-ไทวัสดุ", "q_group": "Customer & Market"},
            {"standard_question_th": "ซื้อปูนและวัสดุก่อสร้างจาก-โกลบอลเฮาส์", "q_group": "Customer & Market"},
            {"standard_question_th": "ซื้อปูนและวัสดุก่อสร้างจาก-ดูโฮม", "q_group": "Customer & Market"},
            {"standard_question_th": "ซื้อปูนและวัสดุก่อสร้างจาก-โฮมโปร", "q_group": "Customer & Market"},
            {"standard_question_th": "ซื้อปูนและวัสดุก่อสร้างจาก-บุญถาวร", "q_group": "Customer & Market"},
            {"standard_question_th": "สินค้าที่ซื้อมากที่สุดจาก-ไทวัสดุ", "q_group": "Customer & Market"},
            {"standard_question_th": "สินค้าที่ซื้อมากที่สุดจาก-ไทวัสดุ เหตุผล", "q_group": "Customer & Market"},
            {"standard_question_th": "สินค้าที่ซื้อมากที่สุดจาก-โกลบอลเฮาส์", "q_group": "Customer & Market"},
            {"standard_question_th": "สินค้าที่ซื้อมากที่สุดจาก-โกลบอลเฮาส์ เหตุผล", "q_group": "Customer & Market"},
            {"standard_question_th": "สินค้าที่ซื้อมากที่สุดจาก-ดูโฮม", "q_group": "Customer & Market"},
            {"standard_question_th": "สินค้าที่ซื้อมากที่สุดจาก-ดูโฮม เหตุผล", "q_group": "Customer & Market"},
            {"standard_question_th": "สินค้าที่ซื้อมากที่สุดจาก-โฮมโปร", "q_group": "Customer & Market"},
            {"standard_question_th": "สินค้าที่ซื้อมากที่สุดจาก-โฮมโปร เหตุผล", "q_group": "Customer & Market"},
            {"standard_question_th": "สินค้าที่ซื้อมากที่สุดจาก-บุญถาวร", "q_group": "Customer & Market"},
            {"standard_question_th": "สินค้าที่ซื้อมากที่สุดจาก-บุญถาวร เหตุผล", "q_group": "Customer & Market"},
            {"standard_question_th": "โมเดิร์นเทรดที่เป็นสมาชิกในการสะสมแต้ม", "q_group": "Customer & Market"},
            {"standard_question_th": "ระบบสะสมแต้มนี้ตอบโจทย์คุณในด้านใด", "q_group": "Customer & Market"},
            {"standard_question_th": "สิ่งที่ไม่ประทับใจ", "q_group": "Customer & Market"},
            {"standard_question_th": "รู้สึกว่าการสะสมคะแนนยุ่งยากหรือไม่ อธิบาย", "q_group": "Customer & Market"},
            {"standard_question_th": "วิธีสะสมแต้ม", "q_group": "Customer & Market"},
            {"standard_question_th": "แต้มปูนตอบโจทย์คุณในด้านใด", "q_group": "Customer & Market"},
            {"standard_question_th": "สิ่งที่ไม่ประทับใจในแต้มปูน", "q_group": "Customer & Market"},
            {"standard_question_th": "รู้สึกว่าการสะสมคะแนนแต้มปูนยุ่งยากหรือไม่ อธิบาย", "q_group": "Customer & Market"},
            {"standard_question_th": "กิจกรรมที่อยากให้เพิ่มในระบบแต้มปูน", "q_group": "Customer & Market"},
            {"standard_question_th": "กิจกรรมที่ดึงดูดการแลกของรางวัลน่าสนใจมากขึ้น", "q_group": "Customer & Market"},
            {"standard_question_th": "สิ่งที่ SCG มีแต่เจ้าอื่นไม่มี", "q_group": "Customer & Market"},
        ],
        "Business & Strategy": [
            {"standard_question_th": "บริษัทรับเหมาก่อสร้าง", "q_group": "Business & Strategy"},
            {"standard_question_th": "ชื่อโครงการในวันที่เข้าสัมภาษณ์", "q_group": "Business & Strategy"},
            {"standard_question_th": "ภาค (ตามที่อยู่)", "q_group": "Business & Strategy"},
            {"standard_question_th": "จังหวัด (ตามที่อยู่)", "q_group": "Business & Strategy"},
            {"standard_question_th": "จังหวัดที่รับบริการ", "q_group": "Business & Strategy"},
            {"standard_question_th": "ร้านประจำที่ซื้อวัสดุก่อสร้าง", "q_group": "Business & Strategy"},
            {"standard_question_th": "มีคนรับช่วงธุรกิจต่อหรือไม่", "q_group": "Business & Strategy"},
            {"standard_question_th": "ธุรกิจอื่นที่ทำควบคู่กัน", "q_group": "Business & Strategy"},
        ],
        "Product & Process": [
            {"standard_question_th": "วิธีการจัดเก็บปูนในไซต์งาน", "q_group": "Product & Process"},
        ],
        "Pain Points & Needs": [
            {"standard_question_th": "ปัญหาที่พบในการทำงานของช่าง", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "ปัญหาที่พบในการจัดซื้อวัสดุก่อสร้าง", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "สิ่งที่อยากให้ SCG พัฒนา", "q_group": "Pain Points & Needs"},
            {"standard_question_th": "สิ่งที่อยากให้ SCG สนับสนุน/ช่วยเหลือ", "q_group": "Pain Points & Needs"},                        
        ],
        "Product & Process": [
            {"standard_question_th": "วิธีคิดค่าบริการงานก่อสร้าง", "q_group": "Product & Process"},
            {"standard_question_th": "มูลค่างานต่อปี", "q_group": "Product & Process"},
            {"standard_question_th": "ร้านประจำที่ซื้อปูน เสือ/SCG", "q_group": "Product & Process"},
            {"standard_question_th": "ปูนเสือ/SCG ที่ซื้อไป นิยมใช้กับงานประเภทใด", "q_group": "Product & Process"},
            {"standard_question_th": "ความถี่ในการสั่งปูน (ครั้ง/สัปดาห์)", "q_group": "Product & Process"},
            {"standard_question_th": "ความถี่ในการเข้าร้านวัสดุก่อสร้าง (ครั้ง/สัปดาห์)", "q_group": "Product & Process"},
            {"standard_question_th": "สินค้าที่มักซื้อคู่กับปูน", "q_group": "Product & Process"},
            {"standard_question_th": "ปริมาณสินค้าที่มักซื้อคู่กับปูน", "q_group": "Product & Process"},
            {"standard_question_th": "สนใจทดลองใช้สินค้า scg หรือไม่", "q_group": "Product & Process"},
            {"standard_question_th": "ปูน หรือสินค้า scg ที่สนใจทดลองใช้", "q_group": "Product & Process"},            
        ],
        # Contractor อาจไม่มี cross-product ก็ได้ — ถ้าไม่มี ก็ลบสองชีตนี้ออก
        "Product List": [
            {"standard_question_th": "ก่อฉาบเท-Grey", "q_group": "Product & Details"},
            {"standard_question_th": "ก่อ-Grey", "q_group": "Product & Details"},
            {"standard_question_th": "ก่อ-Mortar", "q_group": "Product & Details"},
            {"standard_question_th": "ก่อ-Mortar-LW", "q_group": "Product & Details"},
            {"standard_question_th": "ฉาบ-Grey", "q_group": "Product & Details"},
            {"standard_question_th": "ฉาบ-Mortar", "q_group": "Product & Details"},
            {"standard_question_th": "ฉาบ-Mortar-LW", "q_group": "Product & Details"},
            {"standard_question_th": "ฉาบ-Grey-จับเซี๊ยม", "q_group": "Product & Details"},
            {"standard_question_th": "ฉาบ-Mortar-จับเซี๊ยม", "q_group": "Product & Details"},
            {"standard_question_th": "ฉาบบาง-Mortar-สกิมโค้ท", "q_group": "Product & Details"},
            {"standard_question_th": "เทโครงสร้าง-Grey", "q_group": "Product & Details"},
            {"standard_question_th": "เทโครงสร้าง-Mortar", "q_group": "Product & Details"},
            {"standard_question_th": "เทโครงสร้าง-RMC", "q_group": "Product & Details"},
            {"standard_question_th": "เทเสาเอ็น-Grey", "q_group": "Product & Details"},
            {"standard_question_th": "เทเสาเอ็น-Mortar", "q_group": "Product & Details"},
            {"standard_question_th": "เทเสาเอ็น-RMC", "q_group": "Product & Details"},
            {"standard_question_th": "เทปรับพื้น-Grey", "q_group": "Product & Details"},
            {"standard_question_th": "เทปรับพื้น-Mortar", "q_group": "Product & Details"},
            {"standard_question_th": "เทปรับพื้น-RMC", "q_group": "Product & Details"},
            {"standard_question_th": "ปูกระเบื้อง-Mortar-TA", "q_group": "Product & Details"},
            {"standard_question_th": "ปูกระเบื้อง-Mortar-TG", "q_group": "Product & Details"},
            {"standard_question_th": "ผนัง-อิฐมอญ", "q_group": "Product & Details"},
            {"standard_question_th": "ผนัง-อิฐบล็อก", "q_group": "Product & Details"},
            {"standard_question_th": "ผนัง-อิฐมวลเบา", "q_group": "Product & Details"},
            {"standard_question_th": "ผนัง-CLC", "q_group": "Product & Details"},
            {"standard_question_th": "ผนัง-Wall system", "q_group": "Product & Details"},
            {"standard_question_th": "สี-รองพื้น", "q_group": "Product & Details"},
            {"standard_question_th": "สี-สีจริง", "q_group": "Product & Details"},
            {"standard_question_th": "อื่นๆ-Water proof", "q_group": "Product & Details"},
            {"standard_question_th": "อื่นๆ-Non shrink", "q_group": "Product & Details"},
            {"standard_question_th": "อื่นๆ-White", "q_group": "Product & Details"},
        ],
        "Product & Details": [
            {"standard_question_th": "ยี่ห้อ/รุ่น", "q_group": "Product & Details"},
            {"standard_question_th": "ใช้แตกต่างกันอย่างไร?", "q_group": "Product & Details"},
            {"standard_question_th": "ใคร Spec/ ใครเลือก", "q_group": "Product & Details"},
            {"standard_question_th": "ร้านที่ซื้อ", "q_group": "Product & Details"},
            {"standard_question_th": "ปัจจัยการเลือกร้าน", "q_group": "Product & Details"},
            {"standard_question_th": "ปัจจัยเลือกแบรนด์", "q_group": "Product & Details"},
            {"standard_question_th": "ราคา (บาท/ถุง)", "q_group": "Product & Details"},
            {"standard_question_th": "ปริมาณการซื้อต่อครั้ง", "q_group": "Product & Details"},
        ],
    },
}

BUSINESS_TYPES = list(QUESTION_BANK.keys())

# 🧭 เลือก Business Type ก่อน (แทนที่การอัปโหลดไฟล์)
# หัวข้อใหญ่ (จะใหญ่กว่า markdown ปกติ)
st.subheader("🏷️ เลือก BUSINESS TYPE ก่อนเริ่ม")

# ซ่อน label ของ selectbox แล้วใช้หัวข้อด้านบนแทน
biz = st.selectbox(
    "",  # ไม่ใส่ข้อความ
    options=BUSINESS_TYPES,
    index=None,  # <- ยังไม่เลือกอะไร
    placeholder="— เลือก BUSINESS_TYPE —",
    label_visibility="collapsed",
)

# ยังไม่เลือก -> บอกผู้ใช้แล้วหยุดการประมวลผลต่อ
if biz is None:
    st.info("👆 กรุณาเลือก BUSINESS TYPE เพื่อสร้างคำถาม")
    st.stop()

# 📚 แปลง QUESTION_BANK -> sheets_data (โครงเดียวกับไฟล์ Excel เดิม)
def build_sheets_data_from_bank(bank_for_biz: dict) -> dict:
    sheets = {}
    for sheet_name, rows in bank_for_biz.items():
        # rows: list of dicts {"standard_question_th": ..., "q_group": ...}
        df = pd.DataFrame(rows)
        # เผื่อบาง sheet ไม่มี q_group (ไม่ควรเกิด แต่กันไว้)
        if "q_group" not in df.columns:
            df["q_group"] = "N/A"
        # ให้โครงสร้างเหมือนเดิม
        df = df[["standard_question_th", "q_group"]]
        sheets[sheet_name] = df
    return sheets

sheets_data = build_sheets_data_from_bank(QUESTION_BANK[biz])

# ตรวจว่ามี cross-product ไหม
is_cross = "Product List" in sheets_data and "Product & Details" in sheets_data
selected_products, selected_details = [], []

# =========================
#   UI เลือกคำถาม (มาตรฐานก่อน → ค่อย Product)
# =========================

st.subheader("📌 คำถามที่ต้องการในการเก็บข้อมูล")
selected_questions = []
# ลำดับกลุ่มมาตรฐาน (สำหรับหน้าจอเลือกคำถาม)
ORDER_STANDARD_GROUPS = [
    "Respondent Profile",
    "Customer & Market",
    "Business & Strategy",
    "Pain Points & Needs",
    "Product & Process",
    "Special Topic",
]

# วนตามลำดับที่กำหนดไว้
for sheet_name in ORDER_STANDARD_GROUPS:
    if sheet_name in sheets_data and "standard_question_th" in sheets_data[sheet_name].columns:
        df = sheets_data[sheet_name]
        st.markdown(f"<h4 style='margin:6px 0;text-decoration:underline;'>📑 {sheet_name}</h4>", unsafe_allow_html=True)
        for i, row in df.iterrows():
            q = str(row["standard_question_th"])
            if pd.notna(q) and q.strip():
                if st.checkbox(q, key=f"{sheet_name}_{i}"):
                    qty = st.number_input(
                        f"🔢 จำนวน: {q[:30]}",
                        1, 20, 1, 1,
                        key=f"{sheet_name}_{i}_qty"
                    )
                    # group จากแหล่งข้อมูล ถ้าไม่มีให้เป็น N/A (ยังมี fuzzy สำรองตอน export)
                    selected_questions.append({
                        "Question": q.strip(),
                        "Quantity": qty,
                        "Group": row.get("q_group", "N/A")
                    })

# ✍️ Custom Questions (ยังอยู่หลังกลุ่มมาตรฐาน)
with st.expander("✍️ เพิ่มคำถามเอง (Custom Questions) กดที่นี่"):
    custom_q = st.text_input("กรอกคำถามที่ต้องการเพิ่ม", key="custom_question_input")
    custom_q_qty = st.number_input("จำนวนที่ต้องการ Repeat ", 1, 20, 1, 1, key="custom_question_qty")
    custom_q_group = st.selectbox(
        "เลือกกลุ่มคำถามสำหรับคำถามใหม่ (q_group)",
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
    if st.button("➕ เพิ่มคำถามนี้"):
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

# —— หลังจากนั้นค่อย “กลุ่ม Product สำหรับ cross” ——
selected_products, selected_details = [], []
if is_cross:
    st.subheader("🧩 กลุ่ม Product List")

    # Product List มาก่อน
    st.markdown("**📦 Product List**")
    for i, row in sheets_data["Product List"].iterrows():
        q = str(row["standard_question_th"])
        if pd.notna(q) and q.strip():
            if st.checkbox(q, key=f"prod_{i}"):
                qty = st.number_input(f"🔢 จำนวน: {q}", 1, 20, 1, 1, key=f"qty_{i}")
                selected_products.append({"name": q.strip(), "qty": qty})

    # แล้วค่อย Product & Details
    st.markdown("**🧾 Product & Details**")
    for i, row in sheets_data["Product & Details"].iterrows():
        q = str(row["standard_question_th"])
        if pd.notna(q) and q.strip():
            if st.checkbox(q, key=f"detail_{i}"):
                selected_details.append(q.strip())

    with st.expander("➕ เพิ่มคำถามเกี่ยวกับสินค้า (Custom Product Details)"):
        custom_detail = st.text_input("กรอกคำถามเกี่ยวกับสินค้า", key="custom_detail_input")
        if st.button("➕ เพิ่มคำถามเกี่ยวกับสินค้า"):
            if custom_detail.strip():
                st.session_state.custom_product_details.append(custom_detail.strip())
                st.success(f"✅ เพิ่มคำถามสินค้า \"{custom_detail.strip()}\" แล้วเรียบร้อย")
            else:
                st.warning("กรุณากรอกคำถาม")

# เติม custom product details เข้าไป
selected_details += st.session_state.custom_product_details


# =========================
#   GENERATE EXPORT
# =========================
if st.button("📅 สร้างและดาวน์โหลด Excel + PDF"):
    columns, qgroup_row, question_row, pdf_rows = [], [], [], []
    seen_labels.clear()

    # ✅ Group questions (ยังคง logic เดิม + fuzzy สำรองจากคลังเดียวกัน)
    grouped_questions_by_group = {}
    unmatched_questions = []

    for q in selected_questions:
        base_q = q["Question"]
        # ถ้า group ใส่มาแล้ว ใช้เลย; ถ้าไม่ ก็ใช้ find_q_group จาก sheets_data
        group = q.get("Group") if q.get("Group") not in [None, "", "N/A"] else find_q_group(base_q, sheets_data)
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

    # Cross product
    if is_cross and selected_products and selected_details:
        for prod in selected_products:
            for i in range(1, prod["qty"] + 1):
                for detail in selected_details:
                    label = generate_unique_label(f"{prod['name']}-{detail}", i, prod["qty"])
                    columns.append(label)
                    qgroup_row.append("Product & Details")
                    question_row.append(label)
                    pdf_rows.append(["Product & Details", label, ""])

    # ✅ สร้าง DataFrame สำหรับ Excel แนวนอน (หัว 2 แถว)
    header_df = pd.DataFrame([qgroup_row, question_row])
    empty = pd.DataFrame([[""] * len(columns) for _ in range(5)])
    final_df = pd.concat([header_df, empty], ignore_index=True)

    st.markdown("### 📓 ตัวอย่าง (Excel)")
    st.dataframe(final_df.head(5))

    excel_buffer = BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        final_df.to_excel(writer, sheet_name="Survey Template", index=False)
    st.download_button("🔽️ ดาวน์โหลด Excel", data=excel_buffer.getvalue(),
                       file_name="survey_template.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ✅ Preview PDF (ตารางตัวอย่าง)
    st.markdown("### 🔍 ตัวอย่าง (PDF)")
    st.dataframe(pd.DataFrame(pdf_rows[:5], columns=["Group", "Question", "Answer"]))

    # ฟอนต์ไทย (เช็คไฟล์ก่อนเพื่อกันพังตอนรันบนเครื่องที่ไม่มีฟอนต์)
    font_path = os.path.join("font", "THSarabun.ttf")
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont("THSarabun", font_path))
        font_name = "THSarabun"
        font_size = 14
    else:
        font_name = "Helvetica"
        font_size = 10
        st.warning("⚠️ ไม่พบฟอนต์ THSarabun.ttf — จะใช้ Helvetica แทนใน PDF")

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
        ("FONTNAME", (0, 0), (-1, -1), font_name),
        ("FONTSIZE", (0, 0), (-1, -1), font_size),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    doc.build([table])

    st.download_button("🔽️ ดาวน์โหลด PDF", data=pdf_buffer.getvalue(),
                       file_name="survey_questions_structured.pdf",
                       mime="application/pdf")

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

    # ✅ Preview Excel แนวตั้งใน Streamlit
    st.markdown("### 📋 ตัวอย่าง (Excel แนวตั้ง)")
    st.dataframe(df_vertical.head(10))



