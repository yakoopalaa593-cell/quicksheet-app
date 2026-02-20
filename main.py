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

if 'user_info' not in st.session_state:
    st.session_state.user_info = None
if 'usage_count' not in st.session_state:
    st.session_state.usage_count = 0
if 'is_premium' not in st.session_state:
    st.session_state.is_premium = False
if 'current_df' not in st.session_state:
    st.session_state.current_df = None

if not st.session_state.user_info:
    st.set_page_config(page_title="QuickSheet AI Pro", layout="wide")
    
    st.title("🚀 QuickSheet AI Pro")
    st.subheader("إيكو يرحب بك! حول وصولاتك الورقية إلى تقارير ذكية بثوانٍ")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("🎯 **دقة عالية**\nاستخراج البيانات بذكاء اصطناعي متطور.")
    with col2:
        st.success("📊 **تحليل تلقائي**\nAuto Insights تشرح لك الأرقام فوراً.")
    with col3:
        st.warning("💬 **دردشة ذكية**\nتحدث مع بياناتك واطلب منها ما تشاء.")

    st.divider()
    
    st.write("### 💳 اختر خطتك المناسبة")
    p_col1, p_col2 = st.columns(2)
    with p_col1:
        st.markdown("""
        **الخطة المجانية (Free)**
        - 10 محاولات تحليل.
        - استخراج الجداول الأساسية.
        - دعم فني محدود.
        - **السعر: 0$**
        """)
    with p_col2:
        st.markdown("""
        **خطة المحترفين (VIP) 💎**
        - محاولات غير محدودة.
        - دمج الصور المتعددة (Smart Merge).
        - تحليل Auto Insights متقدم.
        - **السعر: 25$ / شهرياً**
        """)
    
    st.divider()
    
    st.write("### 🔑 تسجيل الدخول للبدء")
    name = st.text_input("أدخل اسمك أو بريدك الإلكتروني:")
    if st.button("دخول إلى النظام 🚀"):
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
    st.sidebar.write(f"أهلاً بك يا بطل، {st.session_state.user_info['name']}")
    status = "💎 VIP Premium" if st.session_state.is_premium else "🆓 Free"
    st.sidebar.markdown(f"الحالة: {status}")
    
    if st.sidebar.button("تسجيل الخروج"):
        st.session_state.user_info = None
        st.session_state.current_df = None
        st.rerun()
        
    if not st.session_state.is_premium:
        st.sidebar.write(f"الاستخدام: {st.session_state.usage_count}/10")
        st.sidebar.markdown("---")
        st.sidebar.subheader("ترقية إلى VIP 🚀")
        st.sidebar.write("الاشتراك: $25 / شهرياً")
        st.sidebar.write("حول على رقم الكي كارد:")
        st.sidebar.code("7280146585")
        receipt = st.sidebar.file_uploader("ارفع صورة التحويل", type=['png', 'jpg', 'jpeg'])
        if st.sidebar.button("تأكيد الدفع ✅"):
            if receipt:
                st.sidebar.success("تم إرسال الإيصال! سيتم تفعيل الـ VIP قريباً.")
                df = get_data()
                df.loc[df['username'] == st.session_state.user_info['name'], 'receipt_img'] = "Pending Verification"
                save_data(df)
            else:
                st.sidebar.error("يرجى رفع الإيصال أولاً.")

    st.title("📊 لوحة تحكم QuickSheet")
    
    if not st.session_state.is_premium and st.session_state.usage_count >= 10:
        st.error("انتهت الفترة التجريبية. يرجى الترقية للاستمرار.")
        uploaded_files = None
    else:
        uploaded_files = st.file_uploader("ارفع الجداول أو الصور", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

    if uploaded_files:
        user_note = st.text_input("أضف ملاحظة للذكاء الاصطناعي (اختياري)")
        if st.button("بدء التحليل 🚀"):
            with st.spinner('جاري التحليل...'):
                try:
                    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                    model = genai.GenerativeModel('gemini-2.0-flash')
                    should_merge = any(word in user_note.lower() for word in ["اجمع", "دمج", "merge", "combine", "واحد", "وحده"])
                    
                    detailed_prompt = f"""
                    Act as a professional data entry expert. Extract ALL information from the image(s).
                    1. Identify headers, rows, and labels.
                    2. Structure as a flat JSON list of objects [].
                    3. Include all metadata in every row object.
                    4. Use the exact labels found in the image.
                    5. If multiple images, combine rows into one continuous list.
                    Special Note: {user_note} 
                    Return ONLY raw JSON.
                    """

                    if should_merge:
                        images = [Image.open(f) for f in uploaded_files]
                        response = model.generate_content([detailed_prompt, *images])
                        clean_json = re.search(r'\[.*\]', response.text, re.DOTALL)
                        if clean_json:
                            data = json.loads(clean_json.group())
                            if data: st.session_state.current_df = pd.DataFrame(data)
                    else:
                        all_data = []
                        for uploaded_file in uploaded_files:
                            img = Image.open(uploaded_file)
                            response = model.generate_content([detailed_prompt, img])
                            clean_json = re.search(r'\[.*\]', response.text, re.DOTALL)
                            if clean_json:
                                data = json.loads(clean_json.group())
                                if data: all_data.extend(data)
                        if all_data: st.session_state.current_df = pd.DataFrame(all_data)

                    if st.session_state.current_df is not None:
                        if not st.session_state.is_premium:
                            st.session_state.usage_count += len(uploaded_files)
                            df_db = get_data()
                            df_db.loc[df_db['username'] == st.session_state.user_info['name'], 'usage'] = st.session_state.usage_count
                            save_data(df_db)
                        st.success("تم التحليل بنجاح!")
                except Exception as e:
                    st.error(f"Error: {e}")

    if st.session_state.current_df is not None:
        st.divider()
        st.subheader("💡 تحليلات تلقائية (Auto Insights)")
        with st.expander("عرض ملخص الذكاء الاصطناعي", expanded=True):
            try:
                insight_model = genai.GenerativeModel('gemini-2.0-flash')
                insight_prompt = f"""
                As an Iraqi Business Assistant named Echo, provide a 3-bullet point summary of this data in polite Iraqi dialect.
                Data: {st.session_state.current_df.to_string()}
                Focus on: Total sum, highest value, and patterns. Be encouraging.
                """
                insight_res = insight_model.generate_content(insight_prompt)
                st.info(insight_res.text)
            except:
                st.write("التحليل التلقائي غير متوفر حالياً.")

        st.subheader("💬 الدردشة التفاعلية")
        st.dataframe(st.session_state.current_df, use_container_width=True)
        
        chat_input = st.chat_input("اطلب من الذكاء الاصطناعي تعديل الجدول (مثلاً: رتب حسب السعر)")
        if chat_input:
            with st.spinner('جاري التعديل...'):
                try:
                    chat_model = genai.GenerativeModel('gemini-2.0-flash')
                    chat_prompt = f"""
                    Update the pandas DataFrame 'df' based on: {chat_input}.
                    Columns: {list(st.session_state.current_df.columns)}.
                    STRICT: Use pd.to_numeric for math. Append ONE total row if asked for sum.
                    Return ONLY valid python code starting with 'df = '.
                    """
                    chat_res = chat_model.generate_content(chat_prompt)
                    clean_code = chat_res.text.replace('```python', '').replace('```', '').strip()
                    ldict = {'df': st.session_state.current_df.copy(), 'pd': pd}
                    exec(clean_code, globals(), ldict)
                    st.session_state.current_df = ldict['df']
                    st.rerun()
                except Exception as e:
                    st.error(f"خطأ: يرجى التأكد من اسم العمود. {e}")

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            st.session_state.current_df.to_excel(writer, index=False, sheet_name="Sheet1")
            ws = writer.sheets["Sheet1"]
            for idx, col in enumerate(st.session_state.current_df.columns):
                max_len = max(st.session_state.current_df[col].astype(str).map(len).max(), len(str(col))) + 2
                ws.column_dimensions[chr(65 + idx)].width = max_len
        
        st.download_button("تحميل ملف إكسيل 📥", buffer.getvalue(), "QuickSheet_Analysis.xlsx")
