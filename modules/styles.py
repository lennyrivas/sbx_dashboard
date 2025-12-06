# modules/styles.py
# Минимальные стили БЕЗ конфликта с системными темами Streamlit

import streamlit as st

def inject_css():
    """Минимальные стили - только кнопки и заметки"""
    st.markdown("""
    <style>
      /* Только скругленные кнопки и заметки */
      .stButton > button, 
      .stDownloadButton > button { 
        border-radius: 6px !important; 
      }
      
      /* Маленькие заметки */
      .small-note { 
        color: #9fb0c8 !important; 
        font-size: 0.9em !important; 
      }
      
      /* Кнопка удаления */
      .delete-btn { 
        background-color: #ff4b4b !important; 
        color: white !important; 
        border: none !important; 
        padding: 4px 8px !important; 
        border-radius: 4px !important; 
        cursor: pointer !important; 
      }
      
      .delete-btn:hover { 
        background-color: #ff3333 !important; 
      }
    </style>
    """, unsafe_allow_html=True)
