# modules/styles.py
# Module for injecting custom CSS styles into the Streamlit application.
# Модуль для внедрения пользовательских стилей CSS в приложение Streamlit.

import streamlit as st

def inject_css():
    # Injects custom CSS to override or extend default Streamlit styles.
    # Внедряет пользовательский CSS для переопределения или расширения стандартных стилей Streamlit.
    # Uses st.markdown with unsafe_allow_html=True to render <style> tags.
    # Использует st.markdown с unsafe_allow_html=True для рендеринга тегов <style>.
    
    st.markdown("""
    <style>
      /* General Button Styling */
      /* Общая стилизация кнопок */
      /* Applies rounded corners to standard buttons and download buttons. */
      /* Применяет скругленные углы к стандартным кнопкам и кнопкам скачивания. */
      .stButton > button, 
      .stDownloadButton > button { 
        border-radius: 6px !important; 
      }
      
      /* Small Note Styling */
      /* Стилизация маленьких заметок */
      /* Custom class for small, gray text (often used for captions). */
      /* Пользовательский класс для мелкого серого текста (часто используется для подписей). */
      .small-note { 
        color: #9fb0c8 !important; 
        font-size: 0.9em !important; 
      }
      
      /* Delete Button Styling */
      /* Стилизация кнопки удаления */
      /* Custom class for red action buttons (e.g., removing items). */
      /* Пользовательский класс для красных кнопок действий (например, удаление элементов). */
      .delete-btn { 
        background-color: #ff4b4b !important; 
        color: white !important; 
        border: none !important; 
        padding: 4px 8px !important; 
        border-radius: 4px !important; 
        cursor: pointer !important; 
      }
      
      /* Hover effect for delete button */
      /* Эффект наведения для кнопки удаления */
      .delete-btn:hover { 
        background-color: #ff3333 !important; 
      }
    </style>
    """, unsafe_allow_html=True)
