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

sheet = client.open_by_url(st.secrets["GSHEETS_URL"]).sheet1

def get_data():
    try:
        return pd.DataFrame(sheet.get_all_records())
    except:
        return pd.DataFrame(columns=['username', 'usage', 'status'])

def save_data(df):
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

if 'user' not in st.session_state:
    st.session_state.user = None

if not st.session_state.user:
    st.title("QuickSheet AI Pro 📊")
    name = st.text_input("Name/Email:")
    if st.button("Start Now"):
        df = get_data()
        user_row = df[df['username'] == name]
        if user_row.empty:
            new_user = {"username": name, "usage": 0, "status": "Free"}
            sheet.append_row([name, 0, "Free"])
            st.session_state.user = new_user
        else:
            st.session_state.user = user_row.iloc[0].to_dict()
        st.rerun()
else:
    u = st.session_state.user
    st.sidebar.write(f"User: {u['username']}")
    st.sidebar.info(f"Usage: {u['usage']}/10 | {u['status']}")
    
    if st.sidebar.button("Logout"):
        st.session_state.user = None
        st.rerun()

    files = st.file_uploader("Upload Tables", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)
    if st.button("Process") and files:
        if u['status'] != "VIP" and int(u['usage']) >= 10:
            st.error("Limit reached!")
        else:
            with st.spinner("Wait..."):
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
                
                if u['status'] != "VIP":
                    df_all = get_data()
                    new_val = int(u['usage']) + len(files)
                    df_all.loc[df_all['username'] == u['username'], 'usage'] = new_val
                    save_data(df_all)
                    st.session_state.user['usage'] = new_val
                
                st.download_button("Download Excel", buffer.getvalue(), "Result.xlsx")
