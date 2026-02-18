import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import io
import re
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
client = gspread.authorize(creds)

SHEET_URL = st.secrets["GSHEETS_URL"]
sh = client.open_by_url(SHEET_URL)
worksheet = sh.get_worksheet(0)

def get_data():
    try:
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame(columns=['username', 'usage', 'status'])

def save_data(df):
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())

if 'user' not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("QuickSheet AI Pro 📊")
    name = st.text_input("Enter your Name/Email to start:")
    if st.button("Start Now 🚀"):
        if name:
            df = get_data()
            user_row = df[df['username'] == name]
            if user_row.empty:
                new_user = {"username": name, "usage": 0, "status": "Free"}
                worksheet.append_row([name, 0, "Free"])
                st.session_state.user = new_user
            else:
                st.session_state.user = user_row.iloc[0].to_dict()
            st.rerun()
else:
    user = st.session_state.user
    st.sidebar.write(f"Hello, {user['username']}")
    st.sidebar.info(f"Usage: {user['usage']}/10 | {user['status']}")
    
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()
        
    if user['status'] != "VIP":
        st.sidebar.markdown(f'<a href="{st.secrets["STRIPE_PAYMENT_LINK"]}" target="_blank"><button style="width:100%; background-color:#00d084; color:white; border:none; padding:10px; border-radius:5px; font-weight:bold; cursor:pointer;">Upgrade to VIP 🚀</button></a>', unsafe_allow_html=True)

    files = st.file_uploader("Upload Tables", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
    if st.button("Process 🚀") and files:
        if user['status'] != "VIP" and int(user['usage']) >= 10:
            st.error("Limit reached!")
        else:
            with st.spinner("Analyzing..."):
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel('gemini-1.5-flash')
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    for f in files:
                        img = Image.open(f)
                        resp = model.generate_content(["Extract table to JSON", img])
                        match = re.search(r'\[.*\]', resp.text, re.DOTALL)
                        if match:
                            pd.DataFrame(json.loads(match.group())).to_excel(writer, sheet_name=f.name[:20], index=False)
                
                if user['status'] != "VIP":
                    df_all = get_data()
                    new_usage = int(user['usage']) + len(files)
                    df_all.loc[df_all['username'] == user['username'], 'usage'] = new_usage
                    save_data(df_all)
                    st.session_state.user['usage'] = new_usage
                
                st.download_button("Download Excel 📥", buffer.getvalue(), "Result.xlsx")
