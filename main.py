import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import io
import re
import pandas as pd
from streamlit_gsheets import GSheetsConnection

API_KEY = st.secrets["GEMINI_API_KEY"]
SHEET_URL = st.secrets["GSHEETS_URL"]

conn = st.connection("gsheets", type=GSheetsConnection)

def get_data():
    try:
        return conn.read(spreadsheet=SHEET_URL, ttl=0)
    except:
        return pd.DataFrame(columns=['username', 'usage', 'status'])

def save_data(df):
    conn.update(spreadsheet=SHEET_URL, data=df)

if 'user_info' not in st.session_state:
    st.session_state.user_info = None
if 'usage_count' not in st.session_state:
    st.session_state.usage_count = 0
if 'is_premium' not in st.session_state:
    st.session_state.is_premium = False

def login():
    st.title("QuickSheet AI Pro 📊")
    st.write("Welcome Hero! Simplify your work with AI.")
    name = st.text_input("Enter your Name/Email to start:")
    if st.button("Start Now 🚀"):
        if name:
            df = get_data()
            user_row = df[df['username'] == name]
            if user_row.empty:
                new_user = pd.DataFrame([{"username": name, "usage": 0, "status": "Free"}])
                df = pd.concat([df, new_user], ignore_index=True)
                save_data(df)
                st.session_state.user_info = {"name": name}
                st.session_state.usage_count = 0
                st.session_state.is_premium = False
            else:
                user_dict = user_row.iloc[0].to_dict()
                st.session_state.user_info = {"name": user_dict['username']}
                st.session_state.usage_count = int(user_dict['usage'])
                st.session_state.is_premium = (user_dict['status'] == "VIP")
            st.rerun()

if not st.session_state.user_info:
    login()
else:
    st.sidebar.write(f"Hello, {st.session_state.user_info['name']}")
    status = "💎 VIP Premium" if st.session_state.is_premium else "🆓 Free"
    st.sidebar.markdown(f"Status: {status}")
    
    if st.sidebar.button("Logout"):
        st.session_state.user_info = None
        st.rerun()
        
    if not st.session_state.is_premium:
        st.sidebar.write(f"Usage: {st.session_state.usage_count}/10")
        payment_url = "https://buy.stripe.com/test_4gMfZi6HC68raRc0VZdZ601"
        st.sidebar.markdown(f'<a href="{payment_url}" target="_blank"><button style="width: 100%; background-color: #00d084; color: white; padding: 10px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">Upgrade to Premium 🚀</button></a>', unsafe_allow_html=True)
        if st.sidebar.button("I already paid ✅"):
            df = get_data()
            df.loc[df['username'] == st.session_state.user_info['name'], 'status'] = "VIP"
            save_data(df)
            st.session_state.is_premium = True
            st.rerun()

    st.title("📊 QuickSheet AI - Business")
    uploaded_files = st.file_uploader("Upload tables", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

    if not st.session_state.is_premium and st.session_state.usage_count >= 10:
        st.error("Trial ended. Upgrade to continue.")
    else:
        user_note = st.text_input("Write a note to AI (optional)") if uploaded_files else ""
            
        if st.button("Process Now 🚀"):
            if not uploaded_files:
                st.error("Please upload images first.")
            else:
                with st.spinner('AI is analyzing...'):
                    genai.configure(api_key=API_KEY)
                    model = genai.GenerativeModel('gemini-2.0-flash')
                    buffer = io.BytesIO()
                    
                    try:
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            for uploaded_file in uploaded_files:
                                img = Image.open(uploaded_file)
                                prompt = f"Extract ALL data to JSON. Note: {user_note}"
                                response = model.generate_content([prompt, img])
                                clean_json = re.search(r'\[.*\]', response.text, re.DOTALL)
                                
                                if clean_json:
                                    data = json.loads(clean_json.group())
                                    df_temp = pd.DataFrame(data)
                                    sheet_name = f"sheet_{uploaded_file.name[:15]}"
                                    df_temp.to_excel(writer, sheet_name=sheet_name, index=False)
                                    
                                    worksheet = writer.sheets[sheet_name]
                                    for col in worksheet.columns:
                                        max_len = max([len(str(cell.value) or "") for cell in col])
                                        worksheet.column_dimensions[col[0].column_letter].width = max_len + 2
                                    st.write(f"✅ {uploaded_file.name} processed")

                        if not st.session_state.is_premium:
                            st.session_state.usage_count += len(uploaded_files)
                            df_all = get_data()
                            df_all.loc[df_all['username'] == st.session_state.user_info['name'], 'usage'] = st.session_state.usage_count
                            save_data(df_all)
                            
                        st.success("SUCCESS! DOWNLOAD YOUR FILE BELOW")
                        st.download_button("Download Excel 📥", buffer.getvalue(), "Data.xlsx")
                    except Exception as e:
                        st.error(f"Error: {e}")
