import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import io
import re
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

info = dict(st.secrets["gcp_service_account"])
info["private_key"] = info["private_key"].replace("\\n", "\n")

scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(info, scopes=scope)
client = gspread.authorize(creds)

SHEET_URL = st.secrets["GSHEETS_URL"]
sheet = client.open_by_url(SHEET_URL).sheet1

def get_data():
    try:
        data = sheet.get_all_records()
        return pd.DataFrame(data) if data else pd.DataFrame(columns=['username', 'usage', 'status', 'receipt_img'])
    except:
        return pd.DataFrame(columns=['username', 'usage', 'status', 'receipt_img'])

def save_data(df):
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

def perform_validation(df):
    errors = []
    cols = df.columns.tolist()
    qty_col = next((c for c in cols if any(x in c for x in ['كمية', 'الكمية', 'Qty'])), None)
    price_col = next((c for c in cols if any(x in c for x in ['سعر', 'السعر', 'Price'])), None)
    total_col = next((c for c in cols if any(x in c for x in ['اجمالي', 'الإجمالي', 'Total'])), None)
    if qty_col and price_col and total_col:
        for index, row in df.iterrows():
            try:
                q = float(re.sub(r'[^\d.]', '', str(row[qty_col])))
                p = float(re.sub(r'[^\d.]', '', str(row[price_col])))
                t = float(re.sub(r'[^\d.]', '', str(row[total_col])))
                if abs((q * p) - t) > 1: errors.append(index)
            except: continue
    return errors

def show_insights(df):
    st.subheader("📊 التحليل الفوري الذكي")
    col1, col2, col3 = st.columns(3)
    total_val = 0
    total_col = next((c for c in df.columns if any(x in c for x in ['اجمالي', 'الإجمالي', 'Total'])), None)
    item_col = next((c for c in df.columns if any(x in c for x in ['مادة', 'المادة', 'Item'])), None)
    if total_col:
        total_val = pd.to_numeric(df[total_col].astype(str).replace(r'[^\d.]', '', regex=True), errors='coerce').sum()
    with col1: st.metric("إجمالي المبالغ", f"{total_val:,.0f} د.ع")
    with col2: 
        if item_col: st.metric("أكثر مادة تكراراً", str(df[item_col].value_counts().idxmax()))
    with col3: st.metric("عدد القيود", len(df))

if 'user_info' not in st.session_state: st.session_state.user_info = None
if 'usage_count' not in st.session_state: st.session_state.usage_count = 0
if 'is_premium' not in st.session_state: st.session_state.is_premium = False

if not st.session_state.user_info:
    st.title("QuickSheet AI Pro 📊")
    name = st.text_input("Enter your Name/Email to start:")
    if st.button("Start Now 🚀"):
        if name:
            df = get_data()
            user_row = df[df['username'] == name]
            if user_row.empty:
                sheet.append_row([name, 0, "Free", ""])
                st.session_state.user_info, st.session_state.usage_count, st.session_state.is_premium = {"name": name}, 0, False
            else:
                user_dict = user_row.iloc[0].to_dict()
                st.session_state.user_info, st.session_state.usage_count, st.session_state.is_premium = {"name": user_dict['username']}, int(user_dict['usage']), (user_dict['status'] == "VIP")
            st.rerun()
else:
    st.sidebar.write(f"Hello, {st.session_state.user_info['name']}")
    if st.sidebar.button("Logout"):
        st.session_state.user_info = None
        st.rerun()
    if not st.session_state.is_premium:
        st.sidebar.write(f"Usage: {st.session_state.usage_count}/10")
        receipt = st.sidebar.file_uploader("Upload Transfer Screenshot", type=['png', 'jpg', 'jpeg'])
        if st.sidebar.button("Confirm Payment ✅") and receipt:
            df = get_data()
            df.loc[df['username'] == st.session_state.user_info['name'], 'receipt_img'] = "Pending Verification"
            save_data(df)

st.title("📊 QuickSheet AI - Business")
uploaded_files = st.file_uploader("Upload tables", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

if uploaded_files:
    if not st.session_state.is_premium and st.session_state.usage_count >= 10:
        st.error("Trial ended. Upgrade to continue.")
    else:
        user_note = st.text_input("Write a note to AI (optional)")
        if st.button("Process Now 🚀"):
            with st.spinner('AI is analyzing...'):
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel('gemini-2.0-flash')
                buffer = io.BytesIO()
                processed_any = False
                should_merge = any(word in user_note.lower() for word in ["اجمع", "دمج", "merge", "combine", "واحد", "وحده"])
                detailed_prompt = f"Extract ALL table data from image(s). Structure as a flat JSON list of objects []. Ensure every row has all columns (Date, Name, Price, etc.). Use null for missing. Note: {user_note}. Return ONLY raw JSON."

                try:
                    dfs_to_process = []
                    if should_merge:
                        images = [Image.open(f) for f in uploaded_files]
                        response = model.generate_content([detailed_prompt, *images])
                        clean_json = re.search(r'\[.*\]', response.text, re.DOTALL)
                        if clean_json: dfs_to_process.append(("Combined_Data", pd.DataFrame(json.loads(clean_json.group()))))
                    else:
                        for f in uploaded_files:
                            response = model.generate_content([detailed_prompt, Image.open(f)])
                            clean_json = re.search(r'\[.*\]', response.text, re.DOTALL)
                            if clean_json: dfs_to_process.append((f"sheet_{f.name[:10]}", pd.DataFrame(json.loads(clean_json.group()))))

                    if dfs_to_process:
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            for sheet_name, df in dfs_to_process:
                                df.to_excel(writer, sheet_name=sheet_name, index=False)
                                ws = writer.sheets[sheet_name]
                                for idx, col in enumerate(df.columns):
                                    max_len = max(df[col].astype(str).map(len).max(), len(str(col))) + 2
                                    ws.column_dimensions[chr(65 + idx)].width = max_len
                                if sheet_name == "Combined_Data" or len(dfs_to_process) == 1:
                                    error_indices = perform_validation(df)
                                    show_insights(df)
                                    st.dataframe(df.style.apply(lambda x: ['background-color: #ffcccc' if x.name in error_indices else '' for _ in x], axis=1))
                                processed_any = True

                        if processed_any:
                            if not st.session_state.is_premium:
                                st.session_state.usage_count += len(uploaded_files)
                                df_all = get_data()
                                df_all.loc[df_all['username'] == st.session_state.user_info['name'], 'usage'] = st.session_state.usage_count
                                save_data(df_all)
                            st.success("SUCCESS! DOWNLOAD YOUR FILE BELOW")
                            st.download_button("Download Excel 📥", buffer.getvalue(), "Data.xlsx")
                except Exception as e: st.error(f"Error: {e}")
