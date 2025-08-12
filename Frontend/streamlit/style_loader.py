import streamlit as st
import os

def load_css(file_name):
    """
    Load CSS from external file and inject it into Streamlit app
    """
    try:
        with open(file_name, 'r') as f:
            css = f.read()
        st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"CSS file '{file_name}' not found. Please ensure the file exists in the same directory.")
    except Exception as e:
        st.error(f"Error loading CSS file: {e}")

def load_css_from_string(css_string):
    """
    Load CSS from string (fallback method)
    """
    st.markdown(f'<style>{css_string}</style>', unsafe_allow_html=True)