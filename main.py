import streamlit as st
import google.generativeai as genai
from PIL import Image
import json
import os
from dotenv import load_dotenv
import io
import re
import pandas as pd

load_dotenv()

PAYMENT_LINK = os.getenv("STRIPE_PAYMENT_LINK", "https://buy.stripe.com/test_4gMfZi6HC68raRc0VZdZ601")

if 'user_info' not in st.session_state:
    st.session_state.user_info = None
if 'usage_count' not in st.session_state:
    st.session_state.usage_count = 0
if 'is_premium' not in st.session_state:
    st.session_state.is_premium = False

def login():
    st.title("QuickSheet AI Pro 📊")
    st.write("Welcome Hero! Simplify your work with AI.")
    if st.button("Start Free Trial"):
        st.session_state.user_info = {"name": "AGENT"}
        st.rerun()

if not st.session_state.user_info:
    login()
else:
    st.sidebar.write(f"Hello, {st.session_state.user_info['name']}")
    status = "💎WELCOME IN VIP Premium" if st.session_state.is_premium else "🆓 Free"
    st.sidebar.markdown(f"Status: {status}")
    if st.sidebar.button("Logout"):
        st.session_state.user_info = None
        st.rerun()
        
    if not st.session_state.is_premium:
        st.sidebar.write(f"Usage: {st.session_state.usage_count}/10")
        st.sidebar.markdown(f'<a href="{PAYMENT_LINK}" target="_blank"><button style="width: 100%; background-color: #00d084; color: white; padding: 10px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">Upgrade to Premium 🚀</button></a>', unsafe_allow_html=True)
        if st.sidebar.button("I already paid ✅"):
            st.session_state.is_premium = True
            st.rerun()

    st.title("📊 QuickSheet AI - Business")

    uploaded_files = st.file_uploader("Upload tables", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

    if not st.session_state.is_premium and st.session_state.usage_count >= 10:
        st.error("Trial ended. Upgrade to continue.")
    else:
        user_note = ""
        if uploaded_files:
            user_note = st.text_input("write a note to AI")
            
        if st.button("Process Now 🚀"):
            if not uploaded_files:
                st.error("Please upload images first.")
            elif not st.session_state.is_premium and (st.session_state.usage_count + len(uploaded_files) > 10):
                st.warning("Limit reached!")
            else:
                with st.spinner('AI is analyzing...'):
                    all_results = []
                    user_prompt = f"""
                    Extract all data from this image into a JSON list of objects.
                    Each object represents a row in the table.
                    Ensure all objects have the same keys (headers).
                    Return ONLY the raw JSON. No markdown code blocks, no preamble.
                    User note: {user_note}
                    """
                    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
                    model = genai.GenerativeModel('gemini-2.0-flash')
                    buffer = io.BytesIO()
                    
                    try:
                        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                            for uploaded_file in uploaded_files:
                                try:
                                    img = Image.open(uploaded_file)
                                    response = model.generate_content([user_prompt, img])
                                    clean_json = re.sub(r'```json|```', '', response.text).strip()
                                    data = json.loads(clean_json)
                                    
                                    df_temp = pd.DataFrame(data if isinstance(data, list) else [data])
                                    sheet_name = f"sheet_{uploaded_file.name[:20]}"
                                    df_temp.to_excel(writer, sheet_name=sheet_name, index=False)
                                    
                                    if isinstance(data, list): all_results.extend(data)
                                    else: all_results.append(data)
                                    
                                    
                                    st.write(f"✅ {uploaded_file.name} processed")
                                except Exception as e:
                                    st.error(f"Error with {uploaded_file.name}: {e}")
                        
                        if not st.session_state.is_premium:
                            st.session_state.usage_count += len(uploaded_files)
                            
                        st.success("VERY GOOD JOB AGENT")
                        st.download_button(
                            label="Download Excel 📥",
                            data=buffer.getvalue(),
                            file_name="Multi_Page_Data.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except Exception as e:
                        st.error(f"Excel Error: {e}")
                                    