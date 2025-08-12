import streamlit as st
import datetime
import os
import tempfile
from style_loader import load_css
from config import config
from content_analyzer import analyzer
from mr_utils import *
from release_utils import *
import io
from xhtml2pdf import pisa
import pypandoc

def ensure_pandoc_installed():
    """
    Checks if Pandoc is installed and downloads it if it's not.
    This is necessary for pypandoc to function.
    """
    try:
        pypandoc.get_pandoc_path()
    except OSError:
        st.info("Pandoc not found. Downloading and installing for this session...")
        pypandoc.download_pandoc()
        st.success("Pandoc has been installed.")

# Ensure pandoc is available before running the app
ensure_pandoc_installed()

# --- REVISED AND CORRECTED FUNCTION ---
def create_word_document(content: str, version: str) -> io.BytesIO:
    """
    Generates a properly formatted Word document by writing to a temporary file
    and then reading it back into memory. This is required by Pandoc for DOCX output.
    """
    temp_filename = ""
    try:
        # Create a named temporary file that we can write to.
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as temp_doc:
            temp_filename = temp_doc.name

        # Tell pypandoc to use the temporary file as its output.
        pypandoc.convert_text(
            source=content,
            to='docx',
            format='md',
            outputfile=temp_filename,  # This is the crucial part
            extra_args=[f'--metadata=title:Release Notes - {version}']
        )

        # Read the contents of the generated temporary file into a byte buffer.
        with open(temp_filename, 'rb') as f:
            bio = io.BytesIO(f.read())
        
        bio.seek(0)
        return bio

    except ImportError:
        st.error("Required library 'pypandoc-binary' not found. Please run: pip install pypandoc-binary")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred during Word document generation: {e}")
        return None
    finally:
        # CRUCIAL: Clean up the temporary file from the disk.
        if temp_filename and os.path.exists(temp_filename):
            os.remove(temp_filename)


def create_pdf_document(content: str, version: str, styles: str) -> io.BytesIO:
    """Generates a PDF from markdown content in memory using xhtml2pdf."""
    try:
        # Convert markdown to a styled HTML body
        html_body = pypandoc.convert_text(content, 'html', format='md')

        # Combine with a full HTML structure and CSS
        full_html = f"""
        <html>
            <head>
                <style>{styles}</style>
            </head>
            <body>
                <h1>Release Notes - {version}</h1>
                {html_body}
            </body>
        </html>
        """
        
        bio = io.BytesIO()
        
        # Generate the PDF
        pisa_status = pisa.CreatePDF(
            src=io.StringIO(full_html),  # source HTML
            dest=bio                      # destination file-like object
        )

        if pisa_status.err:
            st.error(f"Failed to generate PDF: {pisa_status.err}")
            return None
        
        bio.seek(0)
        return bio
        
    except ImportError:
        st.error("Required libraries for PDF export not found. Please run: pip install xhtml2pdf pypandoc-binary")
        return None
    except Exception as e:
        st.error(f"An unexpected error occurred during PDF generation: {e}")
        return None


# Set page config
st.set_page_config(
    page_title="codeClarity - Documentation Portal",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load CSS styles
load_css('styles.css')

def render_sidebar_with_worldline_logo():
    """Render sidebar with Worldline logo and Code Clarity text"""
    try:
        from PIL import Image
        import base64
        
        worldline_logo = Image.open("assets/worldline.png")
        buffer = io.BytesIO()
        worldline_logo.save(buffer, format="PNG")
        logo_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        st.sidebar.markdown(f"""
        <div style="text-align: center; margin: -2rem -1rem 15px -1rem; padding: 0;">
            <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 10px;">
                <img src="data:image/png;base64,{logo_base64}" 
                     style="height: 120px; width: auto; max-width: 280px; object-fit: contain;" 
                     alt="Worldline Logo">
            </div>
            <h2 style="color: #FFFFFF; font-size: 1.6rem; font-weight: 600; 
                       margin: 0; text-align: center; letter-spacing: 0.5px;">
                Code Clarity
            </h2>
        </div>
        """, unsafe_allow_html=True)
        
    except Exception:
        st.sidebar.markdown("""
        <div style="text-align: center; margin: -2rem -1rem 15px -1rem; padding: 0;">
            <h2 style="color: #FFFFFF; margin: 0; font-size: 1.6rem;">Code Clarity</h2>
        </div>
        """, unsafe_allow_html=True)

def render_main_header_with_product_branding():
    """Render main header with codeClarity logo and Documentation Portal text"""
    try:
        from PIL import Image
        import base64
        
        main_logo = Image.open("assets/codeclarity.png")
        buffer = io.BytesIO()
        main_logo.save(buffer, format="PNG")
        logo_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        st.markdown(f'''
        <div class="main-header-custom">
            <img src="data:image/png;base64,{logo_base64}" 
                 class="main-logo-custom" 
                 alt="codeClarity Logo">
            <h1 class="main-portal-heading-custom">Documentation Portal</h1>
        </div>
        ''', unsafe_allow_html=True)
        
    except Exception:
        st.markdown('''
        <div class="main-header-custom">
            <h1 class="main-portal-heading-custom">Documentation Portal</h1>
        </div>
        ''', unsafe_allow_html=True)

def main():
    """Main application function"""
    
    render_main_header_with_product_branding()
    render_sidebar_with_worldline_logo()

    content_type = st.sidebar.radio(
        "Select Content Type",
        ["Release Notes", "MR Documentation"]
    )

    if content_type == "MR Documentation":
        render_mr_documentation_section()
    else:
        render_release_notes_section()

    render_footer()

def render_mr_documentation_section():
    """Render the MR Documentation section"""
    
    releases = get_release_versions_for_mr()
    
    if releases:
        selected_release = st.sidebar.selectbox("Select Release Tag", releases)
        
        if selected_release:
            mrs = get_mrs_for_release(selected_release)
            
            if mrs:
                mr_options = {mr["display_name"]: mr for mr in mrs}
                selected_mr_name = st.sidebar.selectbox("Select Merge Request", list(mr_options.keys()))
                
                if selected_mr_name:
                    selected_mr = mr_options[selected_mr_name]
                    mr_content = get_mr_documentation_content(selected_mr["path"])
                    
                    if mr_content:
                        display_mr_content(mr_content, selected_mr, selected_release)
                    else:
                        st.error("Could not retrieve MR documentation content.")
            else:
                st.info(f"No MRs found for release {selected_release}")
        else:
            st.info("Please select a release tag to view MR documentation")
    else:
        st.markdown('''
        <div class="documentation-wrapper">
            <div class="no-content-message">
                <h2>🔀 No MR Documentation Available</h2>
                <p>No releases with MR documentation found in the repository.</p>
            </div>
        </div>
        ''', unsafe_allow_html=True)

def render_release_notes_section():
    """Render the Release Notes section"""
    
    releases = get_release_versions()
    
    if releases:
        selected_version = st.sidebar.selectbox("Select Version", releases)
        
        if selected_version:
            release_notes = get_release_notes_content(selected_version)
            
            if release_notes:
                display_release_notes(release_notes, selected_version)
            else:
                display_no_release_notes(selected_version)
    else:
        st.markdown('''
        <div class="documentation-wrapper">
            <div class="no-content-message">
                <h2>📦 No Releases Available</h2>
                <p>No release versions found in the repository.</p>
            </div>
        </div>
        ''', unsafe_allow_html=True)

def display_release_notes(release_notes: str, selected_version: str):
    """
    Displays release notes with release overview, header and separator.
    """
    
    cleaned_content = '\n'.join([line for line in release_notes.split('\n') if line.strip()])
    
    st.markdown('<div class="documentation-wrapper">', unsafe_allow_html=True)
    st.markdown('<div class="documentation-container">', unsafe_allow_html=True)
    
    # --- ANALYZE RELEASE CONTENT ---
    analysis = analyzer.analyze_release_content(release_notes, selected_version)
    
    # --- RELEASE OVERVIEW SECTION ---
    st.markdown(f'''
    <div class="release-overview-card">
        <h2>📋 Release Overview</h2>
        <p class="overview-summary">{analysis['summary']}</p>
        <div class="overview-metadata">
            <span>Released on {analysis['release_date']} • {analysis['release_type']}</span>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    # --- ADD HORIZONTAL LINE BETWEEN SECTIONS ---
    # --- CLEAN HR WITH NO TOP MARGIN ---
    st.markdown(
        "<hr style='margin:0!important;padding:0!important;border:none!important;border-top:1px solid rgba(255,255,255,0.1)!important;height:1px!important;'>", 
        unsafe_allow_html=True
    )
    
    # --- HEADER SECTION WITH WIDER TITLE COLUMN ---
    col1, col2, col3, col4, col5, col6 = st.columns([
        4.5,  # Title (increased from 3.5)
        1.5,  # Flexible spacer (reduced from 2)
        0.8,  # Export label
        1,    # PDF button
        1,    # Word button
        0.8   # Version badge
    ])

    with col1:
        st.markdown('<h1>📚 Release Documentation</h1>', unsafe_allow_html=True)
    
    with col2:
        st.empty()

    with col3:
        st.markdown('<div class="export-label">Export:</div>', unsafe_allow_html=True)
    
    # Prepare file data (same as before)
    word_data = create_word_document(release_notes, selected_version)
    pdf_data = None
    try:
        with open('styles.css', 'r') as f:
            pdf_styles = f.read()
        pdf_data = create_pdf_document(release_notes, selected_version, pdf_styles)
    except FileNotFoundError:
        pdf_data = create_pdf_document(release_notes, selected_version, "")

    with col4:
        if pdf_data:
            st.download_button(
                label="PDF", data=pdf_data,
                file_name=f"Release-Notes-{selected_version}.pdf", mime="application/pdf",
                use_container_width=True, key="pdf_final"
            )

    with col5:
        if word_data:
            st.download_button(
                label="Word", data=word_data,
                file_name=f"Release-Notes-{selected_version}.docx", mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True, key="word_final"
            )

    with col6:
        st.markdown(f'<div class="version-badge">{selected_version}</div>', unsafe_allow_html=True)

    # --- CLEAN HR WITH MINIMAL MARGIN ---
    # --- CLEAN HR WITH NO TOP MARGIN ---
    st.markdown(
        "<hr style='margin:0!important;padding:0!important;border:none!important;border-top:1px solid rgba(255,255,255,0.1)!important;height:1px!important;'>", 
        unsafe_allow_html=True
    )

    # --- DOCUMENT CONTENT ---
    st.markdown('<div class="doc-content">', unsafe_allow_html=True)
    st.markdown(cleaned_content, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def display_mr_content(mr_content: str, selected_mr: dict, selected_release: str):
    """Display MR documentation content"""
    
    st.markdown('<div class="documentation-wrapper">', unsafe_allow_html=True)
    st.markdown('<div class="documentation-container">', unsafe_allow_html=True)
    
    # --- HEADER SECTION WITH WIDER TITLE COLUMN ---
    col1, col2, col3, col4, col5, col6 = st.columns([
        4.5,  # Title (increased from 3.5)
        1.5,  # Flexible spacer (reduced from 2)
        0.8,  # Export label (empty for MR)
        1,    # Empty (no PDF button for MR)
        1,    # Empty (no Word button for MR)
        0.8   # Version badge
    ])

    with col1:
        st.markdown('<h1>🔀 MR Documentation</h1>', unsafe_allow_html=True)
    
    with col2:
        st.empty()

    with col3:
        st.empty()  # No export label for MR
    
    with col4:
        st.empty()  # No PDF button for MR

    with col5:
        st.empty()  # No Word button for MR

    with col6:
        st.markdown(f'<div class="version-badge">{selected_release}</div>', unsafe_allow_html=True)

    # --- CLEAN HR WITH NO TOP MARGIN ---
    st.markdown(
        "<hr style='margin:0!important;padding:0!important;border:none!important;border-top:1px solid rgba(255,255,255,0.1)!important;height:1px!important;'>", 
        unsafe_allow_html=True
    )
    
    # --- DOCUMENT CONTENT WITH MORE MR INFO ---
    st.markdown('<div class="doc-content">', unsafe_allow_html=True)
    
    # Enhanced MR information section
    col_info1, col_info2 = st.columns(2)
    
    with col_info1:
        st.markdown(f"**📝 File:** `{selected_mr['filename']}`")
        st.markdown(f"**📅 Created:** {selected_mr.get('created', 'Unknown')}")
        if 'created_time' in selected_mr:
            # Add timezone to time (assuming UTC, you can change as needed)
            st.markdown(f"**⏰ Time:** {selected_mr['created_time']} UTC")
        
    with col_info2:
        st.markdown(f"**🔑 SHA:** `{selected_mr.get('sha', 'Unknown')[:8]}`")
        if 'branch' in selected_mr:
            st.markdown(f"**🌿 Source Branch:** `{selected_mr['branch']}`")
        # Removed Type field as requested
    
    # Removed the shortsha-branch heading as requested
    st.markdown("---")
    
    # MR content
    st.markdown(mr_content, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def display_no_release_notes(selected_version: str):
    """Display message when no release notes are found"""
    
    st.markdown(f'''
    <div class="documentation-wrapper">
        <div class="no-content-message">
            <h2>📄 Documentation Not Available</h2>
            <p>Release notes for version <strong>{selected_version}</strong> could not be located.</p>
        </div>
    </div>
    ''', unsafe_allow_html=True)
    
    with st.expander("🔍 Technical Details", expanded=False):
        st.markdown('<div class="debug-info">', unsafe_allow_html=True)
        files = list_files_in_release(selected_version)
        if files:
            st.write("**Available files:**")
            for file in files:
                st.write(f"• {file}")
        else:
            st.write("No files found in release directory.")
        st.markdown('</div>', unsafe_allow_html=True)

def render_footer():
    """Render application footer"""
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            "<center>codeClarity v1.0 | Powered by Worldline</center>", 
            unsafe_allow_html=True
        )

def safe_main():
    """Main function with error handling"""
    try:
        main()
    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        st.error("Please check your configuration and try again.")
        
        with st.expander("Error Details"):
            import traceback
            st.code(traceback.format_exc())

if __name__ == "__main__":
    safe_main()