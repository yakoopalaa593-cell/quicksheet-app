import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import io
import re
import pandas as pd
import gspread
import time
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

if 'user_info' not in st.session_state:
    st.session_state.user_info = None
if 'usage_count' not in st.session_state:
    st.session_state.usage_count = 0
if 'is_premium' not in st.session_state:
    st.session_state.is_premium = False
if 'current_df' not in st.session_state:
    st.session_state.current_df = None
if 'auto_insight_text' not in st.session_state:
    st.session_state.auto_insight_text = None

if not st.session_state.user_info:
    st.title("QuickSheet AI Pro 📊")
    st.write("Welcome Hero! Simplify your work with AI.")
    name = st.text_input("Enter your Name/Email to start:")
    if st.button("Start Now 🚀"):
        if name:
            df = get_data()
            user_row = df[df['username'] == name]
            if user_row.empty:
                sheet.append_row([name, 0, "Free", ""])
                st.session_state.user_info = {"name": name}
                st.session_state.usage_count = 0
                st.session_state.is_premium = False
            else:
                user_dict = user_row.iloc[0].to_dict()
                st.session_state.user_info = {"name": user_dict['username']}
                st.session_state.usage_count = int(user_dict['usage'])
                st.session_state.is_premium = (user_dict['status'] == "VIP")
            st.rerun()
else:
    st.sidebar.write(f"Hello, {st.session_state.user_info['name']}")
    status = "💎 VIP Premium" if st.session_state.is_premium else "🆓 Free"
    st.sidebar.markdown(f"Status: {status}")
    
    if st.sidebar.button("Logout"):
        st.session_state.user_info = None
        st.session_state.current_df = None
        st.session_state.auto_insight_text = None
        st.rerun()
        
    if not st.session_state.is_premium:
        st.sidebar.write(f"Usage: {st.session_state.usage_count}/10")
        st.sidebar.markdown("---")
        st.sidebar.subheader("Upgrade to VIP 🚀")
        st.sidebar.code("7280146585")
        receipt = st.sidebar.file_uploader("Upload Transfer Screenshot", type=['png', 'jpg', 'jpeg'])
        if st.sidebar.button("Confirm Payment ✅"):
            if receipt:
                st.sidebar.success("Receipt sent!")
                df = get_data()
                df.loc[df['username'] == st.session_state.user_info['name'], 'receipt_img'] = "Pending Verification"
                save_data(df)
            else:
                st.sidebar.error("Upload receipt first.")

    st.title("📊 QuickSheet AI - Business")
    
    if not st.session_state.is_premium and st.session_state.usage_count >= 10:
        st.error("Trial ended.")
        uploaded_files = None
    else:
        uploaded_files = st.file_uploader("Upload tables", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

    if uploaded_files:
        user_note = st.text_input("Write a note to AI (optional)")
        if st.button("Process Now 🚀"):
            with st.spinner('AI is analyzing everything...'):
                try:
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    model = genai.GenerativeModel('gemini-2.0-flash')
                    
                    detailed_prompt = f"""
                    EXTRACT EVERYTHING. Act as a high-precision data auditor.
                    1. Mandatory Fields: Look for (Date, Receipt Number, Phone, Address, Customer Name, Total Amount).
                    2. Table Rows: Extract every item, quantity, and price.
                    3. Format: Return a flat JSON list []. 
                    4. IMPORTANT: Repeat the 'Date', 'Receipt Number', and 'Customer' info in EVERY row object.
                    5. Clean Numeric Data: For prices/totals, remove (IQD, $, commas) but keep the raw number.
                    6. User Note: {user_note}
                    Return ONLY raw JSON.
                    """

                    all_data = []
                    for uploaded_file in uploaded_files:
                        img = Image.open(uploaded_file)
                        response = model.generate_content([detailed_prompt, img])
                        clean_json = re.search(r'\[.*\]', response.text, re.DOTALL)
                        if clean_json:
                            data = json.loads(clean_json.group())
                            if data: all_data.extend(data)
                        time.sleep(1)
                    
                    if all_data:
                        st.session_state.current_df = pd.DataFrame(all_data)
                        
                        try:
                            insight_model = genai.GenerativeModel('gemini-2.0-flash')
                            insight_prompt = f"Data: {st.session_state.current_df.to_string()}\nGive 3 quick insights in Iraqi dialect for the Hero. Focus on totals."
                            insight_res = insight_model.generate_content(insight_prompt)
                            st.session_state.auto_insight_text = insight_res.text
                        except:
                            st.session_state.auto_insight_text = "التحليل راح يجهز بعد شوية، كمل شغلك يا بطل."

                        if not st.session_state.is_premium:
                            st.session_state.usage_count += len(uploaded_files)
                            df_db = get_data()
                            df_db.loc[df_db['username'] == st.session_state.user_info['name'], 'usage'] = st.session_state.usage_count
                            save_data(df_db)
                        st.success("Full Analysis Complete!")
                except Exception as e:
                    st.error(f"Error: {e}")

    if st.session_state.current_df is not None:
        st.divider()
        st.subheader("Auto Insights 💡")
        if st.session_state.auto_insight_text:
            st.info(st.session_state.auto_insight_text)

        st.subheader("Interactive Data Chat 💬")
        st.dataframe(st.session_state.current_df, use_container_width=True)
        
        chat_input = st.chat_input("Command AI (e.g., 'اجمع الاجمالي')")
        if chat_input:
            with st.spinner('Updating...'):
                try:
                    chat_model = genai.GenerativeModel('gemini-2.0-flash')
                    chat_prompt = f"""
                    Update the pandas DataFrame 'df' based on: {chat_input}.
                    Columns: {list(st.session_state.current_df.columns)}.
                    
                    STRICT INSTRUCTIONS for the Hero:
                    1. For any math/sum: First remove non-numeric characters using:
                       df['col'] = df['col'].astype(str).str.replace(r'[^\d.]', '', regex=True)
                    2. Convert to numeric: df['col'] = pd.to_numeric(df['col'], errors='coerce').fillna(0)
                    3. If 'اجمع' (sum) is asked: Append a SINGLE row at the bottom.
                    4. Return ONLY valid python code starting with 'df = '.
                    """
                    chat_res = chat_model.generate_content(chat_prompt)
                    clean_code = chat_res.text.replace('```python', '').replace('```', '').strip()
                    ldict = {'df': st.session_state.current_df.copy(), 'pd': pd}
                    exec(clean_code, globals(), ldict)
                    st.session_state.current_df = ldict['df']
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            st.session_state.current_df.to_excel(writer, index=False, sheet_name="Sheet1")
            ws = writer.sheets["Sheet1"]
            for idx, col in enumerate(st.session_state.current_df.columns):
                max_len = max(st.session_state.current_df[col].astype(str).map(len).max(), len(str(col))) + 2
                ws.column_dimensions[chr(65 + idx)].width = max_len
        
        st.download_button("Download Final Excel 📥", buffer.getvalue(), "QuickSheet_Full_Analysis.xlsx")
