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
        return pd.DataFrame(data) if data else pd.DataFrame(columns=['username', 'usage', 'status'])
    except:
        return pd.DataFrame(columns=['username', 'usage', 'status'])

def save_data(df):
    sheet.clear()
    sheet.update([df.columns.values.tolist()] + df.values.tolist())

if 'user_info' not in st.session_state:
    st.session_state.user_info = None
if 'usage_count' not in st.session_state:
    st.session_state.usage_count = 0
if 'is_premium' not in st.session_state:
    st.session_state.is_premium = False

if not st.session_state.user_info:
    st.title("QuickSheet AI Pro 📊")
    st.write("Welcome Hero! Simplify your work with AI.")
    name = st.text_input("Enter your Name/Email to start:")
    if st.button("Start Now 🚀"):
        if name:
            df = get_data()
            user_row = df[df['username'] == name]
            if user_row.empty:
                sheet.append_row([name, 0, "Free"])
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
        st.rerun()
        
    if not st.session_state.is_premium:
        st.sidebar.write(f"Usage: {st.session_state.usage_count}/10")
        payment_url = st.secrets["STRIPE_PAYMENT_LINK"]
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
                genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                model = genai.GenerativeModel('gemini-2.0-flash')
                buffer = io.BytesIO()
                processed_any = False
                
                should_merge = any(word in user_note.lower() for word in ["اجمع", "دمج", "merge", "combine", "واحد", "وحده"])
                
                detailed_prompt = f"""Extract EVERY single detail and column from the provided image(s). 
                Return the data strictly as a JSON list of objects []. 
                If multiple images are provided, combine all rows into ONE single continuous list (Vertical integration).
                Ensure all objects use the same keys (column names) based on the first table found.
                Note: {user_note}
                """

                try:
                    if should_merge:
                        images = [Image.open(f) for f in uploaded_files]
                        response = model.generate_content([detailed_prompt, *images])
                        clean_json = re.search(r'\[.*\]', response.text, re.DOTALL)
                        if clean_json:
                            data = json.loads(clean_json.group())
                            if data:
                                df_final = pd.DataFrame(data)
                                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                                    df_final.to_excel(writer, sheet_name="Combined_Data", index=False)
                                    ws = writer.sheets["Combined_Data"]
                                    for idx, col in enumerate(df_final.columns):
                                        max_len = max(df_final[col].astype(str).map(len).max(), len(str(col))) + 2
                                        ws.column_dimensions[chr(65 + idx)].width = max_len
                                processed_any = True
                    else:
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            for uploaded_file in uploaded_files:
                                img = Image.open(uploaded_file)
                                response = model.generate_content([detailed_prompt, img])
                                clean_json = re.search(r'\[.*\]', response.text, re.DOTALL)
                                if clean_json:
                                    data = json.loads(clean_json.group())
                                    if data:
                                        df_temp = pd.DataFrame(data)
                                        sh_name = f"sheet_{uploaded_file.name[:15]}"
                                        df_temp.to_excel(writer, sheet_name=sh_name, index=False)
                                        ws = writer.sheets[sh_name]
                                        for idx, col in enumerate(df_temp.columns):
                                            max_len = max(df_temp[col].astype(str).map(len).max(), len(str(col))) + 2
                                            ws.column_dimensions[chr(65 + idx)].width = max_len
                                        processed_any = True
                                        st.write(f"✅ {uploaded_file.name} processed")

                    if processed_any:
                        if not st.session_state.is_premium:
                            st.session_state.usage_count += len(uploaded_files)
                            df_all = get_data()
                            df_all.loc[df_all['username'] == st.session_state.user_info['name'], 'usage'] = st.session_state.usage_count
                            save_data(df_all)
                        st.success("SUCCESS! DOWNLOAD YOUR FILE BELOW")
                        st.download_button("Download Excel 📥", buffer.getvalue(), "Data.xlsx")
                    else:
                        st.warning("No data found in the images.")
                except Exception as e:
                    st.error(f"Error: {e}")
