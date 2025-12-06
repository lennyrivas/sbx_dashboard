# modules/settings.py
# Настройки типов паллет

import streamlit as st
from modules.ui_strings import STR

def init_settings():
    """Инициализация настроек по умолчанию"""
    defaults = {
        "cartons": ["83090", "676", "568", "ZC", "826", "3807486", 
                   "PRZEKLADKI CIETE", "RAMKA IPUV", "TCM-ECE", "TKAS"],
        "pallets_frames": [],
        "other_packaging": []
    }
    
    for key, default_list in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_list.copy()
    
    return defaults

def render_settings_tab():
    """Вкладка настроек"""
    st.header(STR["settings"])
    
    # 3 колонки для каждого типа
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.subheader(STR["settings_cartons"])
        edit_cartons(st.session_state.cartons)
    
    with col2:
        st.subheader(STR["settings_pallets"])
        edit_pallets_frames(st.session_state.pallets_frames)
    
    with col3:
        st.subheader(STR["settings_other"])
        edit_other(st.session_state.other_packaging)

def edit_cartons(carton_list):
    """Редактирование списка картонов"""
    edit_list("cartons", carton_list, "Dodaj prefix kartonu")

def edit_pallets_frames(pallet_list):
    """Редактирование списка палет/рам"""
    edit_list("pallets_frames", pallet_list, "Dodaj prefix palety/ramy")

def edit_other(other_list):
    """Редактирование списка других упаковок"""
    edit_list("other_packaging", other_list, "Dodaj prefix innego")

def edit_list(list_key, current_list, placeholder):
    """Универсальный редактор списка"""
    
    # Поле ввода нового префикса
    new_item = st.text_input(
        placeholder, 
        placeholder=placeholder,
        key=f"new_{list_key}"
    )
    
    if st.button(STR["add_prefix"], key=f"add_{list_key}"):
        if new_item.strip():
            current_list.append(new_item.strip().upper())
            st.session_state[list_key] = current_list.copy()
            st.rerun()
    
    # Текущий список с возможностью удаления
    st.markdown("**Aktualna lista:**")
    for i, item in enumerate(current_list):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.code(item)
        with col2:
            if st.button(f"🗑️", key=f"del_{list_key}_{i}"):
                current_list.pop(i)
                st.session_state[list_key] = current_list.copy()
                st.rerun()
