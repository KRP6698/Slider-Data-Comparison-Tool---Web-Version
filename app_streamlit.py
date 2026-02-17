"""
Slider Data Comparison Tool - Web Version (Streamlit)
Western Digital - Quality Control
Version: 3.1 - Enhanced CSV Column Detection
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
import io
import difflib
import re

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
    .success-box {
        background-color: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)


def clean_serial(serial):
    """ทำความสะอาด serial number"""
    if not serial or pd.isna(serial):
        return ""

    serial_str = str(serial).strip().upper()

    # ลบ whitespace ส่วนเกิน
    serial_str = re.sub(r'\s+', '', serial_str)

    # แยก suffix ออก (ถ้ามี comma)
    if ',' in serial_str:
        serial_str = serial_str.split(',')[0].strip()

    # เอา 10 ตัวแรก
    return serial_str[:10] if len(serial_str) >= 8 else serial_str


def detect_serial_column(df):
    """ตรวจจับ column ที่มี serial number"""

    # Keywords ที่บ่งบอกว่าเป็น serial column
    serial_keywords = ['serial', 'slider', 'sn', 'part', 'number']
    exclude_keywords = ['probe', 'date', 'time', 'tester', 'result', 'status']

    st.write("🔍 **Detecting serial column...**")

    # วิธีที่ 1: ตรวจสอบจาก column name
    for idx, col in enumerate(df.columns):
        col_lower = str(col).lower()

        # ข้าม column ที่มี exclude keywords
        if any(ex in col_lower for ex in exclude_keywords):
            continue

        # ตรวจสอบ serial keywords
        if any(kw in col_lower for kw in serial_keywords):
            st.success(f"✅ Found serial column: **{col}** (Column {idx})")
            return idx, col

    # วิธีที่ 2: ตรวจสอบจาก pattern ของข้อมูล
    st.info("🔍 No keyword match, analyzing data patterns...")

    for idx, col in enumerate(df.columns):
        # ดึงตัวอย่างข้อมูล 50 แถวแรก
        sample_data = df[col].dropna().head(50).astype(str)

        if len(sample_data) == 0:
            continue

        # นับจำนวนที่ตรงกับ pattern
        # Pattern: ขึ้นต้นด้วยตัวอักษร 1-3 ตัว ตามด้วยตัวเลขและตัวอักษร รวม 8-15 ตัว
        valid_count = sum(
            1 for s in sample_data
            if re.match(r'^[A-Z]{1,3}[A-Z0-9]{7,14}$', s.strip().upper().split(',')[0])
        )

        match_rate = valid_count / len(sample_data)

        st.write(f"  - Column {idx} ({col}): {match_rate * 100:.1f}% match rate")

        # ถ้าตรงกับ pattern มากกว่า 70% ถือว่าเป็น serial column
        if match_rate >= 0.7:
            st.success(f"✅ Detected serial column: **{col}** (Column {idx}) - {match_rate * 100:.1f}% pattern match")
            return idx, col

    # ถ้าไม่เจอ ใช้ column 0 หรือ column ที่ user เลือก
    st.warning("⚠️ Could not auto-detect serial column, using first column")
    return 0, df.columns[0]


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
            differences.append(f"Pos{i + 1}: '{s1_padded[i].strip()}' → '{s2_padded[i].strip()}'")

    return ' | '.join(differences) if differences else 'No differences'


def read_master_file(uploaded_file):
    """อ่าน Master file (Text/CSV/Excel)"""
    file_ext = Path(uploaded_file.name).suffix.lower()

    st.write(f"📄 **Reading Master File:** {uploaded_file.name}")

    try:
        if file_ext == '.txt':
            # อ่าน Text file
            content = uploaded_file.getvalue().decode('utf-8-sig', errors='ignore')

            # แยกทีละบรรทัด
            lines = content.split('\n')

            serials = set()
            skipped = []

            for line_num, line in enumerate(lines, 1):
                cleaned = clean_serial(line)

                # กรองบรรทัดว่าง, header, หรือข้อมูลไม่ใช่ serial
                if not cleaned:
                    continue
                if len(cleaned) < 8:
                    skipped.append(f"Line {line_num}: '{line.strip()}' (too short)")
                    continue
                if cleaned.lower() in ['serial', 'slider', 'sn', 'partnumber']:
                    skipped.append(f"Line {line_num}: '{line.strip()}' (header)")
                    continue

                serials.add(cleaned)

            st.success(f"✅ Found {len(serials)} valid serials from Text file")

            if skipped:
                with st.expander(f"⚠️ Skipped {len(skipped)} lines (click to view)"):
                    for skip in skipped[:20]:
                        st.text(skip)
                    if len(skipped) > 20:
                        st.text(f"... and {len(skipped) - 20} more")

            return serials, "Text File (Line by line)"

        elif file_ext == '.csv':
            # อ่าน CSV
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            st.write(f"  - Shape: {df.shape[0]} rows × {df.shape[1]} columns")
            st.write(f"  - Columns: {', '.join(map(str, df.columns.tolist()))}")

            # ตรวจจับ serial column
            serial_col_idx, serial_col_name = detect_serial_column(df)

            # ดึง serials
            serials = set(
                clean_serial(serial)
                for serial in df.iloc[:, serial_col_idx].dropna().astype(str)
                if clean_serial(serial) and len(clean_serial(serial)) >= 8
            )

            st.success(f"✅ Found {len(serials)} valid serials from column '{serial_col_name}'")

            return serials, f"CSV - Column: {serial_col_name}"

        elif file_ext in ['.xlsx', '.xls']:
            # อ่าน Excel
            df = pd.read_excel(uploaded_file)
            st.write(f"  - Shape: {df.shape[0]} rows × {df.shape[1]} columns")
            st.write(f"  - Columns: {', '.join(map(str, df.columns.tolist()))}")

            # ตรวจจับ serial column
            serial_col_idx, serial_col_name = detect_serial_column(df)

            # ดึง serials
            serials = set(
                clean_serial(serial)
                for serial in df.iloc[:, serial_col_idx].dropna().astype(str)
                if clean_serial(serial) and len(clean_serial(serial)) >= 8
            )

            st.success(f"✅ Found {len(serials)} valid serials from column '{serial_col_name}'")

            return serials, f"Excel - Column: {serial_col_name}"

        else:
            st.error(f"❌ Unsupported file format: {file_ext}")
            return set(), "Unknown"

    except Exception as e:
        st.error(f"❌ Error reading master file: {str(e)}")
        st.exception(e)
        return set(), "Error"


def read_measurement_file(uploaded_file):
    """อ่าน Measurement file (CSV/Excel)"""
    file_ext = Path(uploaded_file.name).suffix.lower()

    st.write(f"📊 **Reading Measurement File:** {uploaded_file.name}")

    try:
        if file_ext == '.csv':
            # อ่าน CSV
            df = pd.read_csv(uploaded_file, encoding='utf-8-sig')
            st.write(f"  - Shape: {df.shape[0]} rows × {df.shape[1]} columns")
            st.write(f"  - Columns: {', '.join(map(str, df.columns.tolist()))}")

        elif file_ext in ['.xlsx', '.xls']:
            # อ่าน Excel
            df = pd.read_excel(uploaded_file)
            st.write(f"  - Shape: {df.shape[0]} rows × {df.shape[1]} columns")
            st.write(f"  - Columns: {', '.join(map(str, df.columns.tolist()))}")

        else:
            st.error(f"❌ Unsupported file format: {file_ext}")
            return set(), "Unknown"

        # ตรวจจับ serial column
        serial_col_idx, serial_col_name = detect_serial_column(df)

        # ดึง serials
        serials = set(
            clean_serial(serial)
            for serial in df.iloc[:, serial_col_idx].dropna().astype(str)
            if clean_serial(serial) and len(clean_serial(serial)) >= 8
        )

        st.success(f"✅ Found {len(serials)} valid serials from column '{serial_col_name}'")

        return serials, f"Column: {serial_col_name}"

    except Exception as e:
        st.error(f"❌ Error reading measurement file: {str(e)}")
        st.exception(e)
        return set(), "Error"


def create_excel_report(result, master_filename, measurement_filename):
    """สร้าง Excel report แบบละเอียด"""
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # ===== Sheet 1: Summary =====
        potential_typos = len([d for d in result.get('missing_details', []) if d['similarity'] >= 80])

        summary_data = {
            'Metric': [
                'Report Generated',
                'Master File',
                'Measurement File',
                'Master Source',
                'Measurement Source',
                'Comparison Method',
                '',
                'Total Master Sliders',
                'Total Measurement Sliders',
                'Matched Sliders',
                'Match Percentage',
                'Missing Sliders',
                'Extra Sliders',
                '',
                '🚨 Potential Typos (≥80% similar)',
                '⚠️ Need Review (50-79% similar)',
                '❌ Not Found (<50% similar)',
                '',
                'Status'
            ],
            'Value': [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                master_filename,
                measurement_filename,
                result.get('master_source', 'N/A'),
                result.get('measurement_source', 'N/A'),
                'First 10 characters + Fuzzy Matching (difflib)',
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
                '🚨 CRITICAL - Check Potential Typos!' if potential_typos > 0 else
                '⚠️ WARNING - Missing items found' if result['missing_count'] > 0 else
                '✅ PASS - All matched'
            ]
        }
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, sheet_name='Summary', index=False)

        # Auto-adjust column widths
        worksheet = writer.sheets['Summary']
        worksheet.column_dimensions['A'].width = 35
        worksheet.column_dimensions['B'].width = 50

        # ===== Sheet 2: Missing (Detailed) =====
        if result.get('missing_details'):
            missing_data = []
            for i, detail in enumerate(result['missing_details'], 1):
                action = ''
                priority = ''

                if detail['similarity'] >= 80:
                    action = '🚨 URGENT: Verify immediately - likely a typo'
                    priority = 'HIGH'
                elif detail['similarity'] >= 50:
                    action = '⚠️ CHECK: Similar serial exists in CSV'
                    priority = 'MEDIUM'
                else:
                    action = '❌ NOT FOUND in CSV file'
                    priority = 'LOW'

                missing_data.append({
                    'No.': i,
                    'Priority': priority,
                    'Master Serial (Text File)': detail['master_serial'],
                    'Closest Match in CSV': detail['closest_csv'],
                    'Similarity %': detail['similarity'],
                    'Visual Pattern': detail['diff_pattern'],
                    'Character Differences': detail.get('char_differences', ''),
                    'Status': detail['status'],
                    '⚠️ Action Required': action
                })

            df_missing = pd.DataFrame(missing_data)
            df_missing.to_excel(writer, sheet_name='Missing (Detailed)', index=False)

            # Auto-adjust column widths
            worksheet = writer.sheets['Missing (Detailed)']
            for idx, col in enumerate(df_missing.columns):
                max_length = max(
                    df_missing[col].astype(str).map(len).max(),
                    len(str(col))
                )
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)

        # ===== Sheet 3: Extra (Detailed) =====
        if result.get('extra_details'):
            extra_data = []
            for i, detail in enumerate(result['extra_details'], 1):
                action = ''

                if detail['similarity'] >= 80:
                    action = '🚨 CHECK: Very similar to Master - might be misplaced'
                elif detail['similarity'] >= 50:
                    action = '⚠️ REVIEW: Similar serial exists in Master'
                else:
                    action = '➕ NEW: Not found in Master file'

                extra_data.append({
                    'No.': i,
                    'CSV Serial (Measurement)': detail['csv_serial'],
                    'Closest Match in Master': detail['closest_master'],
                    'Similarity %': detail['similarity'],
                    'Visual Pattern': detail['diff_pattern'],
                    'Character Differences': detail.get('char_differences', ''),
                    'Status': detail['status'],
                    '⚠️ Action Required': action
                })

            df_extra = pd.DataFrame(extra_data)
            df_extra.to_excel(writer, sheet_name='Extra (Detailed)', index=False)

            # Auto-adjust column widths
            worksheet = writer.sheets['Extra (Detailed)']
            for idx, col in enumerate(df_extra.columns):
                max_length = max(
                    df_extra[col].astype(str).map(len).max(),
                    len(str(col))
                )
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)

        # ===== Sheet 4: 🚨 URGENT - Potential Typos =====
        potential_typos_list = [d for d in result.get('missing_details', []) if d['similarity'] >= 80]
        if potential_typos_list:
            typo_data = []
            for i, detail in enumerate(potential_typos_list, 1):
                # Visual comparison
                master_serial = detail['master_serial']
                csv_serial = detail['closest_csv']
                pattern = detail['diff_pattern']

                visual = f"{master_serial}\n{csv_serial}\n{pattern}"

                typo_data.append({
                    'Priority': i,
                    '⚠️ Master Serial (Text)': master_serial,
                    '📊 CSV Serial (Closest)': csv_serial,
                    'Match %': detail['similarity'],
                    'Visual Comparison': visual,
                    'Exact Differences': detail.get('char_differences', ''),
                    '🚨 Action': '🔍 URGENT: Verify this mismatch immediately',
                    'Recommendation': 'Likely a typo or data entry error - High priority to fix'
                })

            df_typos = pd.DataFrame(typo_data)
            df_typos.to_excel(writer, sheet_name='🚨 URGENT - Potential Typos', index=False)

            # Format urgent sheet
            worksheet = writer.sheets['🚨 URGENT - Potential Typos']
            for idx, col in enumerate(df_typos.columns):
                max_length = max(
                    df_typos[col].astype(str).map(len).max(),
                    len(str(col))
                )
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 60)

            # Set row height for visual comparison
            for row in range(2, len(df_typos) + 2):
                worksheet.row_dimensions[row].height = 45

        # ===== Sheet 5: Missing (Simple List) =====
        if result.get('missing_serials'):
            df_missing_simple = pd.DataFrame({
                'No.': range(1, len(result['missing_serials']) + 1),
                'Serial Number (Missing from CSV)': sorted(result['missing_serials'])
            })
            df_missing_simple.to_excel(writer, sheet_name='Missing (Simple List)', index=False)

        # ===== Sheet 6: Extra (Simple List) =====
        if result.get('extra_serials'):
            df_extra_simple = pd.DataFrame({
                'No.': range(1, len(result['extra_serials']) + 1),
                'Serial Number (Extra in CSV)': sorted(result['extra_serials'])
            })
            df_extra_simple.to_excel(writer, sheet_name='Extra (Simple List)', index=False)

    output.seek(0)
    return output
def check_password():
    """Returns `True` if user had correct password."""

    def password_entered():
        """Checks whether password entered is correct."""
        if st.session_state["password"] in st.secrets["passwords"].values():
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password
        st.text_input(
            "🔐 Enter WD Access Password",
            type="password",
            on_change=password_entered,
            key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error
        st.text_input(
            "🔐 Enter WD Access Password",
            type="password",
            on_change=password_entered,
            key="password"
        )
        st.error("❌ Incorrect password")
        return False
    else:
        # Password correct
        return True


# ใส่ใน main()
def main():
    if not check_password():
        st.stop()

    # ... โค้ดที่เหลือ
    """Main function"""
    # Header
    st.markdown("""
        <div style='text-align: center; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                    padding: 2rem; border-radius: 1rem; margin-bottom: 2rem;'>
            <h1 style='color: white; margin: 0;'>🔍 Slider Data Comparison Tool</h1>
            <p style='color: white; margin: 0.5rem 0 0 0; font-size: 1.2rem;'>
                Western Digital - Quality Control | Web Version 3.1
            </p>
            <p style='color: white; margin: 0.3rem 0 0 0; font-size: 0.9rem; opacity: 0.9;'>
                Enhanced CSV Column Detection & Fuzzy Matching
            </p>
        </div>
    """, unsafe_allow_html=True)

    # Sidebar
    with st.sidebar:
        st.markdown("### 📋 Instructions")
        st.markdown("""
        1. **Upload Master File**
           - Text: One serial per line
           - CSV/Excel: Auto-detect serial column

        2. **Upload Measurement File**
           - CSV/Excel: Auto-detect serial column

        3. **Click Compare Data**

        4. **Download Excel Report**
           - Missing serials (Text → CSV)
           - Potential typos (≥80% match)
           - Side-by-side comparison
        """)

        st.markdown("---")
        st.markdown("### 🎯 Features")
        st.markdown("""
        - ✅ Auto-detect serial columns
        - ✅ Fuzzy matching (typo detection)
        - ✅ Side-by-side comparison
        - ✅ Detailed Excel report (6 sheets)
        - ✅ Support Windows XP+ (via browser)
        """)

        st.markdown("---")
        st.markdown("### 💡 Tips")
        st.markdown("""
        **Text File:**
        - One serial per line
        - Example:
          ```
          B72AE6F13C
          SYC12281-P
          A1234567BC
          ```

        **CSV/Excel:**
        - Will auto-detect serial column
        - Keywords: serial, slider, SN
        - Or pattern-based detection
        """)

    # Main content
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 📄 Master File (Reference)")
        master_file = st.file_uploader(
            "Upload Master File",
            type=['txt', 'csv', 'xlsx', 'xls'],
            key='master',
            help="Text file (one serial per line) or CSV/Excel"
        )
        if master_file:
            st.success(f"✅ {master_file.name}")
            st.caption(f"Size: {master_file.size:,} bytes")

    with col2:
        st.markdown("### 📊 Measurement File (To Compare)")
        measurement_file = st.file_uploader(
            "Upload Measurement File",
            type=['csv', 'xlsx', 'xls'],
            key='measurement',
            help="CSV or Excel file with measurement data"
        )
        if measurement_file:
            st.success(f"✅ {measurement_file.name}")
            st.caption(f"Size: {measurement_file.size:,} bytes")

    st.markdown("---")

    # Compare button
    if st.button("🔍 Compare Data with Fuzzy Matching", type="primary", use_container_width=True):
        if not master_file or not measurement_file:
            st.error("❌ Please upload both files!")
            return

        try:
            with st.spinner("🔄 Processing data... Please wait..."):

                # Read Master file
                st.markdown("### 📂 File Processing")

                with st.expander("📄 Master File Analysis", expanded=True):
                    master_serials, master_source = read_master_file(master_file)

                with st.expander("📊 Measurement File Analysis", expanded=True):
                    measurement_serials, measurement_source = read_measurement_file(measurement_file)

                if not master_serials or not measurement_serials:
                    st.error("❌ Failed to read files or no valid serials found.")
                    return

                st.markdown("---")
                st.markdown("### 🔄 Comparison Analysis")

                # Compare
                missing_sliders = master_serials - measurement_serials
                extra_sliders = measurement_serials - master_serials
                matched_sliders = master_serials & measurement_serials

                st.write(f"✅ Matched: {len(matched_sliders)} serials")
                st.write(f"❌ Missing (in Master but not in CSV): {len(missing_sliders)} serials")
                st.write(f"➕ Extra (in CSV but not in Master): {len(extra_sliders)} serials")

                # Analyze missing sliders
                with st.spinner("🔍 Analyzing missing serials with fuzzy matching..."):
                    missing_details = []
                    measurement_list = list(measurement_serials)

                    progress_bar = st.progress(0)
                    for idx, missing_serial in enumerate(sorted(missing_sliders)):
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

                        # Update progress
                        progress_bar.progress((idx + 1) / len(missing_sliders))

                    progress_bar.empty()

                # Analyze extra sliders
                with st.spinner("🔍 Analyzing extra serials..."):
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
                    'missing_serials': list(missing_sliders),
                    'extra_serials': list(extra_sliders),
                    'missing_details': missing_details,
                    'extra_details': extra_details,
                    'master_source': master_source,
                    'measurement_source': measurement_source,
                    'match_percentage': round((len(matched_sliders) / len(master_serials) * 100),
                                              2) if master_serials else 0
                }

            # Display results
            st.markdown("---")
            st.markdown("## 📊 Comparison Results")

            # Metrics
            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric("📄 Total Master", result['total_master'])
            with col2:
                st.metric("📊 Total Measurement", result['total_measurement'])
            with col3:
                st.metric("✅ Matched", result['matched_count'],
                          delta=f"{result['match_percentage']}%")
            with col4:
                st.metric("❌ Missing", result['missing_count'],
                          delta="⚠️ Check" if result['missing_count'] > 0 else "✅ OK",
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
                            Found <strong>{}</strong> serial(s) with ≥80% similarity. 
                            These are <strong>likely data entry errors</strong> that need immediate attention!
                        </p>
                    </div>
                """.format(len(potential_typos)), unsafe_allow_html=True)

                st.markdown("#### 🚨 Potential Typos (High Priority)")
                typo_df = pd.DataFrame([
                    {
                        '📄 Master Serial (Text)': d['master_serial'],
                        '📊 CSV Serial (Closest)': d['closest_csv'],
                        'Match %': f"{d['similarity']}%",
                        'Pattern': d['diff_pattern'],
                        'Differences': d['char_differences']
                    }
                    for d in potential_typos
                ])
                st.dataframe(typo_df, use_container_width=True, height=min(len(potential_typos) * 35 + 38, 400))

            elif result['missing_count'] == 0:
                st.markdown("""
                    <div class='success-box'>
                        <h3 style='margin: 0; color: #155724;'>✅ Perfect Match!</h3>
                        <p style='margin: 0.5rem 0 0 0;'>
                            All serials from Master file were found in Measurement file.
                        </p>
                    </div>
                """, unsafe_allow_html=True)

            # Missing sliders (show first 50)
            if missing_details and result['missing_count'] > 0:
                st.markdown("---")
                st.markdown("#### ❌ Missing Serials (In Master but NOT in CSV)")

                # Group by status
                high_priority = [d for d in missing_details if d['similarity'] >= 80]
                medium_priority = [d for d in missing_details if 50 <= d['similarity'] < 80]
                not_found = [d for d in missing_details if d['similarity'] < 50]

                st.write(f"- 🚨 **High Priority (≥80% similar):** {len(high_priority)} items")
                st.write(f"- ⚠️ **Medium Priority (50-79% similar):** {len(medium_priority)} items")
                st.write(f"- ❌ **Not Found (<50% similar):** {len(not_found)} items")

                display_limit = st.slider("Show first N items:", 10, min(len(missing_details), 100), 50, 10)

                missing_df = pd.DataFrame([
                    {
                        '📄 Master Serial': d['master_serial'],
                        '📊 Closest in CSV': d['closest_csv'],
                        'Match %': f"{d['similarity']}%",
                        'Status': d['status'],
                        'Differences': d.get('char_differences', '')[:50] + '...' if len(
                            d.get('char_differences', '')) > 50 else d.get('char_differences', '')
                    }
                    for d in missing_details[:display_limit]
                ])
                st.dataframe(missing_df, use_container_width=True, height=400)

                if len(missing_details) > display_limit:
                    st.info(
                        f"ℹ️ Showing {display_limit} of {len(missing_details)} missing items. Download Excel for complete list.")

            # Extra sliders (show first 50)
            if extra_details and result['extra_count'] > 0:
                st.markdown("---")
                st.markdown("#### ➕ Extra Serials (In CSV but NOT in Master)")

                display_limit = min(50, len(extra_details))

                extra_df = pd.DataFrame([
                    {
                        '📊 CSV Serial': d['csv_serial'],
                        '📄 Closest in Master': d['closest_master'],
                        'Match %': f"{d['similarity']}%",
                        'Status': d['status']
                    }
                    for d in extra_details[:display_limit]
                ])
                st.dataframe(extra_df, use_container_width=True, height=400)

                if len(extra_details) > display_limit:
                    st.info(
                        f"ℹ️ Showing first {display_limit} of {len(extra_details)} extra items. Download Excel for complete list.")

            # Download button
            st.markdown("---")
            st.markdown("### 📥 Download Report")

            with st.spinner("📝 Generating detailed Excel report..."):
                excel_data = create_excel_report(result, master_file.name, measurement_file.name)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            col1, col2, col3 = st.columns([1, 2, 1])

            with col2:
                st.download_button(
                    label="📥 Download Detailed Excel Report (6 Sheets)",
                    data=excel_data,
                    file_name=f"slider_comparison_report_{timestamp}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True
                )

            st.markdown("""
                <div style='background: #e7f3ff; padding: 1rem; border-radius: 0.5rem; border-left: 4px solid #2196F3;'>
                    <strong>📋 Report Contents:</strong>
                    <ul style='margin: 0.5rem 0 0 1.5rem;'>
                        <li><strong>Summary:</strong> Overview & statistics</li>
                        <li><strong>Missing (Detailed):</strong> Side-by-side comparison with closest matches</li>
                        <li><strong>Extra (Detailed):</strong> Extra serials analysis</li>
                        <li><strong>🚨 URGENT - Potential Typos:</strong> High-priority items (≥80% match)</li>
                        <li><strong>Missing (Simple List):</strong> Quick reference list</li>
                        <li><strong>Extra (Simple List):</strong> Quick reference list</li>
                    </ul>
                </div>
            """, unsafe_allow_html=True)

            # Summary message
            st.markdown("---")
            if result['missing_count'] == 0:
                st.success("✅ **PASS:** All sliders matched successfully!")
            elif potential_typos:
                st.error(
                    f"🚨 **CRITICAL:** {result['missing_count']} missing slider(s) detected. **{len(potential_typos)} likely typo(s)** require immediate attention!")
            else:
                st.warning(f"⚠️ **WARNING:** {result['missing_count']} missing slider(s) detected.")

        except Exception as e:
            st.error(f"❌ **Error during comparison:** {str(e)}")
            st.exception(e)

    # Footer
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; color: #666; font-size: 0.9rem; padding: 2rem 0;'>
            <p style='margin: 0;'>© 2025 Western Digital Corporation. All rights reserved.</p>
            <p style='margin: 0.5rem 0 0 0;'>
                <strong>Slider Data Comparison Tool v3.1</strong> | 
                Enhanced CSV Detection & Fuzzy Matching | 
                For internal use only
            </p>
            <p style='margin: 0.5rem 0 0 0; font-size: 0.8rem; opacity: 0.8;'>
                Supports: Windows XP/7/8/10/11, macOS, Linux (via any modern browser)
            </p>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()