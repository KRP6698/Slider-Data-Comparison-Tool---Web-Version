"""
Slider Data Comparison Tool - Web Version (Streamlit)
Western Digital - Quality Control
Version: 3.0 - Web Edition with Fuzzy Matching
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
import io
import difflib
import json

# ตั้งค่าหน้าเว็บ
st.set_page_config(
    page_title="Slider Data Comparison Tool - WD",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stAlert {
        padding: 1rem;
        border-radius: 0.5rem;
    }
    .highlight-box {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #667eea;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 0.5rem;
        text-align: center;
    }
    .urgent-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)


def clean_serial(serial):
    """ทำความสะอาด serial number"""
    if not serial:
        return ""
    serial_str = str(serial).strip().upper()
    if ',' in serial_str:
        serial_str = serial_str.split(',')[0].strip()
    return serial_str[:10]


def find_closest_match(target, candidates, cutoff=0.6):
    """หา serial ที่ใกล้เคียงที่สุด"""
    if not candidates:
        return None, 0.0

    matches = difflib.get_close_matches(target, candidates, n=1, cutoff=cutoff)
    if matches:
        match = matches[0]
        ratio = difflib.SequenceMatcher(None, target, match).ratio()
        return match, ratio
    return None, 0.0


def highlight_diff(s1, s2):
    """แสดงความแตกต่างระหว่าง 2 strings"""
    diff = []
    max_len = max(len(s1), len(s2))
    s1_padded = s1.ljust(max_len)
    s2_padded = s2.ljust(max_len)

    for i in range(max_len):
        if i < len(s1) and i < len(s2):
            if s1[i] == s2[i]:
                diff.append('✓')
            else:
                diff.append('✗')
        else:
            diff.append('✗')
    return ''.join(diff)


def get_char_differences(s1, s2):
    """หาตำแหน่งที่ตัวอักษรต่างกัน"""
    differences = []
    max_len = max(len(s1), len(s2))
    s1_padded = s1.ljust(max_len, ' ')
    s2_padded = s2.ljust(max_len, ' ')

    for i in range(max_len):
        if s1_padded[i] != s2_padded[i]:
            differences.append(f"Pos{i + 1}: '{s1_padded[i]}' vs '{s2_padded[i]}'")

    return ' | '.join(differences) if differences else 'Perfect match'


def read_master_file(uploaded_file):
    """อ่าน Master file"""
    file_ext = Path(uploaded_file.name).suffix.lower()

    try:
        if file_ext == '.txt':
            content = uploaded_file.getvalue().decode('utf-8-sig')
            serials = set(
                clean_serial(line)
                for line in content.split('\n')
                if clean_serial(line)
            )
        elif file_ext == '.csv':
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            serials = set(
                clean_serial(serial)
                for serial in df.iloc[:, 0].dropna().astype(str)
                if clean_serial(serial)
            )
        elif file_ext in ['.xlsx', '.xls']:
            df = pd.read_excel(uploaded_file)
            serials = set(
                clean_serial(serial)
                for serial in df.iloc[:, 0].dropna().astype(str)
                if clean_serial(serial)
            )
        else:
            st.error(f"❌ Unsupported file format: {file_ext}")
            return set()

        return serials
    except Exception as e:
        st.error(f"❌ Error reading master file: {str(e)}")
        return set()


def read_measurement_file(uploaded_file):
    """อ่าน Measurement file"""
    file_ext = Path(uploaded_file.name).suffix.lower()

    try:
        if file_ext == '.csv':
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            serials = set(
                clean_serial(serial)
                for serial in df.iloc[:, 1].dropna().astype(str)
                if clean_serial(serial)
            )
        elif file_ext in ['.xlsx', '.xls']:
            df = pd.read_excel(uploaded_file)
            serials = set(
                clean_serial(serial)
                for serial in df.iloc[:, 1].dropna().astype(str)
                if clean_serial(serial)
            )
        else:
            st.error(f"❌ Unsupported file format: {file_ext}")
            return set()

        return serials
    except Exception as e:
        st.error(f"❌ Error reading measurement file: {str(e)}")
        return set()


def create_excel_report(result, master_filename, measurement_filename):
    """สร้าง Excel report"""
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Summary sheet
        potential_typos = len([d for d in result.get('missing_details', []) if d['similarity'] >= 80])

        summary_data = {
            'Metric': [
                'Report Generated',
                'Master File',
                'Measurement File',
                'Comparison Method',
                '',
                'Total Master Sliders',
                'Total Measurement Sliders',
                'Matched Sliders',
                'Match Percentage',
                'Missing Sliders',
                'Extra Sliders',
                '',
                'Potential Typos (≥80% similar)',
                'Need Review (50-79% similar)',
                'Not Found (<50% similar)',
                '',
                'Status'
            ],
            'Value': [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                master_filename,
                measurement_filename,
                'First 10 characters + Fuzzy Matching',
                '',
                result['total_master'],
                result['total_measurement'],
                result['matched_count'],
                f"{result['match_percentage']}%",
                result['missing_count'],
                result['extra_count'],
                '',
                potential_typos,
                len([d for d in result.get('missing_details', []) if 50 <= d['similarity'] < 80]),
                len([d for d in result.get('missing_details', []) if d['similarity'] < 50]),
                '',
                '🚨 ALERT - Check Potential Typos' if potential_typos > 0 else
                '⚠️ WARNING - Missing items found' if result['missing_count'] > 0 else
                '✅ OK - All matched'
            ]
        }
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='Summary', index=False)

        # Missing (Detailed)
        if result.get('missing_details'):
            missing_data = []
            for i, detail in enumerate(result['missing_details'], 1):
                action = ''
                if detail['similarity'] >= 80:
                    action = '🚨 URGENT: Verify - likely a typo'
                elif detail['similarity'] >= 50:
                    action = '⚠️ CHECK: Similar serial exists'
                else:
                    action = '❌ NOT FOUND in CSV'

                missing_data.append({
                    'No.': i,
                    'Master Serial': detail['master_serial'],
                    'Closest CSV': detail['closest_csv'],
                    'Similarity %': detail['similarity'],
                    'Diff Pattern': detail['diff_pattern'],
                    'Exact Differences': detail.get('char_differences', ''),
                    'Status': detail['status'],
                    'Action Required': action
                })

            df_missing = pd.DataFrame(missing_data)
            df_missing.to_excel(writer, sheet_name='Missing (Detailed)', index=False)

        # Extra (Detailed)
        if result.get('extra_details'):
            extra_data = []
            for i, detail in enumerate(result['extra_details'], 1):
                action = ''
                if detail['similarity'] >= 80:
                    action = '🚨 URGENT: Verify - might be misplaced'
                elif detail['similarity'] >= 50:
                    action = '⚠️ CHECK: Similar serial exists'
                else:
                    action = '➕ NEW: Not in Master'

                extra_data.append({
                    'No.': i,
                    'CSV Serial': detail['csv_serial'],
                    'Closest Master': detail['closest_master'],
                    'Similarity %': detail['similarity'],
                    'Diff Pattern': detail['diff_pattern'],
                    'Exact Differences': detail.get('char_differences', ''),
                    'Status': detail['status'],
                    'Action Required': action
                })

            df_extra = pd.DataFrame(extra_data)
            df_extra.to_excel(writer, sheet_name='Extra (Detailed)', index=False)

        # Potential Typos
        potential_typos_list = [d for d in result.get('missing_details', []) if d['similarity'] >= 80]
        if potential_typos_list:
            typo_data = []
            for i, detail in enumerate(potential_typos_list, 1):
                typo_data.append({
                    'Priority': i,
                    'Master Serial': detail['master_serial'],
                    'CSV Serial': detail['closest_csv'],
                    'Match %': detail['similarity'],
                    'Differences': detail.get('char_differences', ''),
                    'Action': '🔍 URGENT: Verify immediately',
                    'Recommendation': 'Likely typo or data entry error'
                })

            df_typos = pd.DataFrame(typo_data)
            df_typos.to_excel(writer, sheet_name='⚠️ URGENT - Potential Typos', index=False)

    output.seek(0)
    return output


def main():
    """Main function"""

    # Header
    st.markdown("""
        <div style='text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 2rem; border-radius: 1rem; margin-bottom: 2rem;'>
            <h1 style='color: white; margin: 0;'>🔍 Slider Data Comparison Tool</h1>
            <p style='color: white; margin: 0.5rem 0 0 0; font-size: 1.2rem;'>
                Western Digital - Quality Control | Web Version 3.0
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.image("https://via.placeholder.com/200x80/667eea/ffffff?text=WD+Logo", use_column_width=True)
        st.markdown("---")
        st.markdown("### 📋 Instructions")
        st.markdown("""
        1. Upload **Master File** (Text/CSV/Excel)
        2. Upload **Measurement File** (CSV/Excel)
        3. Click **Compare Data**
        4. Download detailed Excel report
        """)
        st.markdown("---")
        st.markdown("### ℹ️ About")
        st.markdown("""
        **Version:** 3.0 Web Edition  
        **Features:**
        - ✅ Fuzzy Matching
        - ✅ Side-by-Side Comparison
        - ✅ Typo Detection
        - ✅ Detailed Excel Report
        """)
        st.markdown("---")
        st.markdown("### 🌐 System Requirements")
        st.markdown("""
        - Modern web browser
        - Internet connection
        - Works on all OS (including Windows XP)
        """)

    # Main content
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📄 Master File")
        master_file = st.file_uploader(
            "Upload Master File (Text/CSV/Excel)",
            type=['txt', 'csv', 'xlsx', 'xls'],
            key='master',
            help="Select the master reference file"
        )
        if master_file:
            st.success(f"✅ {master_file.name}")

    with col2:
        st.markdown("### 📊 Measurement File")
        measurement_file = st.file_uploader(
            "Upload Measurement File (CSV/Excel)",
            type=['csv', 'xlsx', 'xls'],
            key='measurement',
            help="Select the measurement comparison file"
        )
        if measurement_file:
            st.success(f"✅ {measurement_file.name}")

    st.markdown("---")

    # Compare button
    if st.button("🔍 Compare Data with Fuzzy Matching", type="primary", use_container_width=True):
        if not master_file or not measurement_file:
            st.error("❌ Please upload both files!")
            return

        with st.spinner("🔄 Processing data... Please wait..."):
            # Read files
            master_serials = read_master_file(master_file)
            measurement_serials = read_measurement_file(measurement_file)

            if not master_serials or not measurement_serials:
                st.error("❌ Failed to read files. Please check file format.")
                return

            # Compare
            missing_sliders = master_serials - measurement_serials
            extra_sliders = measurement_serials - master_serials
            matched_sliders = master_serials & measurement_serials

            # Analyze missing sliders
            missing_details = []
            measurement_list = list(measurement_serials)

            for missing_serial in sorted(missing_sliders):
                closest_match, similarity = find_closest_match(missing_serial, measurement_list, cutoff=0.5)

                if closest_match and similarity >= 0.5:
                    diff_pattern = highlight_diff(missing_serial, closest_match)
                    char_diff = get_char_differences(missing_serial, closest_match)
                    missing_details.append({
                        'master_serial': missing_serial,
                        'closest_csv': closest_match,
                        'similarity': round(similarity * 100, 1),
                        'diff_pattern': diff_pattern,
                        'char_differences': char_diff,
                        'status': 'POTENTIAL_MATCH' if similarity >= 0.8 else 'SIMILAR'
                    })
                else:
                    missing_details.append({
                        'master_serial': missing_serial,
                        'closest_csv': 'NOT_FOUND',
                        'similarity': 0.0,
                        'diff_pattern': '',
                        'char_differences': '',
                        'status': 'MISSING'
                    })

            # Analyze extra sliders
            extra_details = []
            master_list = list(master_serials)

            for extra_serial in sorted(extra_sliders):
                closest_match, similarity = find_closest_match(extra_serial, master_list, cutoff=0.5)

                if closest_match and similarity >= 0.5:
                    diff_pattern = highlight_diff(extra_serial, closest_match)
                    char_diff = get_char_differences(extra_serial, closest_match)
                    extra_details.append({
                        'csv_serial': extra_serial,
                        'closest_master': closest_match,
                        'similarity': round(similarity * 100, 1),
                        'diff_pattern': diff_pattern,
                        'char_differences': char_diff,
                        'status': 'POTENTIAL_MATCH' if similarity >= 0.8 else 'SIMILAR'
                    })
                else:
                    extra_details.append({
                        'csv_serial': extra_serial,
                        'closest_master': 'NOT_FOUND',
                        'similarity': 0.0,
                        'diff_pattern': '',
                        'char_differences': '',
                        'status': 'EXTRA'
                    })

            # Results
            result = {
                'total_master': len(master_serials),
                'total_measurement': len(measurement_serials),
                'matched_count': len(matched_sliders),
                'missing_count': len(missing_sliders),
                'extra_count': len(extra_sliders),
                'missing_details': missing_details,
                'extra_details': extra_details,
                'match_percentage': round((len(matched_sliders) / len(master_serials) * 100),
                                          2) if master_serials else 0
            }

        # Display results
        st.markdown("---")
        st.markdown("## 📊 Comparison Results")

        # Metrics
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            st.metric("Total Master", result['total_master'])
        with col2:
            st.metric("Total Measurement", result['total_measurement'])
        with col3:
            st.metric("✅ Matched", result['matched_count'],
                      delta=f"{result['match_percentage']}%")
        with col4:
            st.metric("❌ Missing", result['missing_count'],
                      delta="Warning" if result['missing_count'] > 0 else "OK",
                      delta_color="inverse")
        with col5:
            st.metric("➕ Extra", result['extra_count'])

        # Potential typos alert
        potential_typos = [d for d in missing_details if d['similarity'] >= 80]
        if potential_typos:
            st.markdown("""
                <div class='urgent-box'>
                    <h3 style='margin: 0; color: #856404;'>🚨 URGENT: Potential Typos Detected!</h3>
                    <p style='margin: 0.5rem 0 0 0;'>
                        Found <strong>{}</strong> serial(s) with ≥80% similarity. These are likely data entry errors!
                    </p>
                </div>
            """.format(len(potential_typos)), unsafe_allow_html=True)

            st.markdown("### ⚠️ Potential Typos (Priority)")
            typo_df = pd.DataFrame([
                {
                    'Master Serial': d['master_serial'],
                    'CSV Serial': d['closest_csv'],
                    'Similarity %': d['similarity'],
                    'Differences': d['char_differences']
                }
                for d in potential_typos
            ])
            st.dataframe(typo_df, use_container_width=True)

        # Missing sliders
        if missing_details:
            st.markdown("### ❌ Missing Sliders (Detailed)")
            missing_df = pd.DataFrame([
                {
                    'Master Serial': d['master_serial'],
                    'Closest in CSV': d['closest_csv'],
                    'Similarity %': d['similarity'],
                    'Status': d['status']
                }
                for d in missing_details[:20]
            ])
            st.dataframe(missing_df, use_container_width=True)

            if len(missing_details) > 20:
                st.info(f"ℹ️ Showing first 20 of {len(missing_details)} missing items. Download Excel for full list.")

        # Extra sliders
        if extra_details:
            st.markdown("### ➕ Extra Sliders (Detailed)")
            extra_df = pd.DataFrame([
                {
                    'CSV Serial': d['csv_serial'],
                    'Closest in Master': d['closest_master'],
                    'Similarity %': d['similarity'],
                    'Status': d['status']
                }
                for d in extra_details[:20]
            ])
            st.dataframe(extra_df, use_container_width=True)

            if len(extra_details) > 20:
                st.info(f"ℹ️ Showing first 20 of {len(extra_details)} extra items. Download Excel for full list.")

        # Download button
        st.markdown("---")
        excel_data = create_excel_report(result, master_file.name, measurement_file.name)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        st.download_button(
            label="📥 Download Detailed Excel Report",
            data=excel_data,
            file_name=f"slider_comparison_report_{timestamp}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )

        # Summary message
        if result['missing_count'] == 0:
            st.success("✅ All sliders matched successfully!")
        elif potential_typos:
            st.warning(
                f"⚠️ {result['missing_count']} missing slider(s) detected. {len(potential_typos)} likely typo(s)!")
        else:
            st.warning(f"⚠️ {result['missing_count']} missing slider(s) detected.")

    # Footer
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; color: #666; font-size: 0.9rem;'>
            <p>© 2025 Western Digital Corporation. All rights reserved.</p>
            <p>Slider Data Comparison Tool v3.0 | For internal use only</p>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()